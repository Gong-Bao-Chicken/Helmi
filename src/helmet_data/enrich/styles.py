"""Helmet style inference and manufacturer cross-checks."""

import json
import re
import time
from typing import Any
from urllib.parse import quote_plus

import httpx

from ..paths import STYLE_CACHE_PATH

AERO_MODEL_TOKENS = (
    "aero",
    "evade",
    "ballista",
    "gamechanger",
    "game changer",
    "cadence plus",
    "cadence+",
    "centric plus",
    "split mips",
    "overtake",
    "moventor",
    "protone",
    "ventral air",
    "codatronca",
    "air star",
    "kudo",
    "vento kineticore",
    "vento kineti",
    "trenta",
    "cytal",
    "falconer aero",
    "rivale",
)

KIDS_TOKENS = ("kid", "child", "youth", "junior", "teen")
# Assigned when nothing in the name or manufacturer text names a style; kept apart from
# Urban so the city category isn't padded with helmets of unknown type.
UNCLASSIFIED = "Unclassified"

STYLE_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    # Kids first: a kids' MTB helmet is chosen as a kids' helmet.
    ("Kids", KIDS_TOKENS),
    ("Full-Face", ("full-face", "full face", "fullface", "downhill", "bmx")),
    ("Mountain", ("mountain", "mtb", "trail", "enduro", "cross-country", " xc ", "rockrider")),
    ("Aero", AERO_MODEL_TOKENS),
    ("Road", ("road", "racer", "racing", "peloton")),
    ("Multi-sport", ("multi-sport", "multisport", "multi sport", "all-around", "all around")),
    ("Urban", ("urban", "commuter", "city", "lifestyle", "skate")),
]

COMPATIBLE_STYLE_PAIRS = {
    frozenset({"Road", "Aero"}),
    frozenset({"Urban", "Multi-sport"}),
    frozenset({"Mountain", "Multi-sport"}),
    frozenset({"Mountain", "Full-Face"}),
    frozenset({"Kids", "Urban"}),
}


def is_aero_helmet(brand: str, model: str) -> bool:
    text = f"{brand} {model}".lower()
    return any(token in text for token in AERO_MODEL_TOKENS)


def is_kids_helmet(brand: str, model: str) -> bool:
    text = f"{brand} {model}".lower()
    return any(token in text for token in KIDS_TOKENS)


def infer_style(brand: str, model: str, *, default: str = UNCLASSIFIED) -> str:
    text = f"{brand} {model}".lower()
    for style, tokens in STYLE_PATTERNS:
        if any(token in text for token in tokens):
            return style
    return default


def infer_style_from_text(text: str, *, brand: str = "", model: str = "") -> str | None:
    combined = f"{brand} {model} {text}".lower()
    if not combined.strip():
        return None

    matches: list[str] = []
    for style, tokens in STYLE_PATTERNS:
        if any(token in combined for token in tokens):
            matches.append(style)

    if not matches:
        return None
    priority = ["Kids", "Full-Face", "Mountain", "Aero", "Road", "Multi-sport", "Urban"]
    for style in priority:
        if style in matches:
            return style
    return matches[0]


def styles_compatible(assigned: str, manufacturer: str | None) -> bool | None:
    if manufacturer is None:
        return None
    if assigned == manufacturer:
        return True
    return frozenset({assigned, manufacturer}) in COMPATIBLE_STYLE_PAIRS


def refine_helmet_styles(helmets: list[dict]) -> None:
    """Reclassify kids' helmets into Kids, and road and misclassified urban helmets into Aero."""
    for helmet in helmets:
        meta = helmet.setdefault("style_meta", {})
        meta.setdefault("assigned", helmet.get("style"))
        meta.setdefault("source", meta.get("source") or "unknown")

        if helmet["style"] != "Kids" and is_kids_helmet(helmet["brand"], helmet["model"]):
            meta["vt_style"] = meta.get("vt_style") or helmet["style"]
            helmet["style"] = "Kids"
            meta["assigned"] = "Kids"
            meta["source"] = f"{meta['source']}_kids"
            continue

        if helmet["style"] not in ("Road", "Urban"):
            continue
        if is_aero_helmet(helmet["brand"], helmet["model"]):
            meta["vt_style"] = meta.get("vt_style") or helmet["style"]
            helmet["style"] = "Aero"
            meta["assigned"] = "Aero"
            meta["source"] = "virginia_tech_refined"


def _manufacturer_search_url(brand: str, model: str, brands: dict[str, dict]) -> str | None:
    brand_info = brands.get(brand.lower(), {})
    query = quote_plus(f"{brand} {model}")
    search_url = brand_info.get("search_url", "").format(query=query) if brand_info else None
    return search_url or None


def _load_style_cache() -> dict[str, dict[str, Any]]:
    if not STYLE_CACHE_PATH.exists():
        return {}
    return json.loads(STYLE_CACHE_PATH.read_text(encoding="utf-8"))


def _save_style_cache(cache: dict[str, dict[str, Any]]) -> None:
    STYLE_CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _model_tokens(model: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", model.lower()) if len(token) > 2]


def _model_mentioned(model: str, text: str | None) -> bool:
    if not text:
        return False
    lowered = text.lower()
    tokens = _model_tokens(model)
    if not tokens:
        return False
    hits = sum(1 for token in tokens if token in lowered)
    return hits >= min(2, len(tokens))


def _extract_product_url(html: str, search_url: str, model: str) -> str | None:
    from urllib.parse import urljoin

    og_url = re.search(
        r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)["\']',
        html,
        re.I,
    )
    if og_url and _model_mentioned(model, og_url.group(1)):
        return og_url.group(1)

    tokens = _model_tokens(model)[:3]
    for match in re.finditer(r'href=["\']([^"\']+)["\']', html, re.I):
        href = match.group(1)
        if "helmet" not in href.lower() and not any(token in href.lower() for token in tokens):
            continue
        if href.startswith("#") or href.startswith("javascript:"):
            continue
        return urljoin(search_url, href)
    return None


def _fetch_manufacturer_style(
    client: httpx.Client,
    search_url: str,
    *,
    model: str,
) -> dict[str, Any]:
    from ..build import extract_meta_from_html

    response = client.get(search_url, follow_redirects=True)
    response.raise_for_status()
    html = response.text
    product_url = _extract_product_url(html, str(response.url), model)
    if product_url and product_url != str(response.url):
        try:
            product_response = client.get(product_url, follow_redirects=True)
            product_response.raise_for_status()
            html = product_response.text
        except httpx.HTTPError:
            pass

    meta = extract_meta_from_html(html)
    text = " ".join(filter(None, [meta.get("title"), meta.get("description")]))
    inferred = infer_style_from_text(text, model=model) if _model_mentioned(model, text) else None
    return {
        "fetched": True,
        "title": meta.get("title"),
        "description": meta.get("description"),
        "manufacturer_style": inferred,
        "product_url": product_url,
        "error": None,
    }


def apply_style_verifications(
    helmets: list[dict],
    brands: dict[str, dict],
    *,
    client: httpx.Client | None = None,
    cache_only: bool = False,
    fetch_delay_s: float = 0.5,
) -> dict[str, int]:
    """Cross-check assigned helmet style against manufacturer page text."""
    cache = _load_style_cache()
    stats = {"cached": 0, "fetched": 0, "skipped": 0, "matched": 0, "mismatch": 0, "unknown": 0}

    for helmet in helmets:
        meta = helmet.setdefault("style_meta", {})
        meta["assigned"] = helmet.get("style")
        assigned = helmet.get("style")
        cache_key = helmet["id"]
        entry = cache.get(cache_key)

        if entry is None and client is not None and not cache_only:
            search_url = _manufacturer_search_url(helmet["brand"], helmet["model"], brands)
            if not search_url:
                entry = {"fetched": False, "manufacturer_style": None, "error": "no_search_url"}
                cache[cache_key] = entry
                stats["skipped"] += 1
            else:
                try:
                    entry = _fetch_manufacturer_style(client, search_url, model=helmet["model"])
                    cache[cache_key] = entry
                    stats["fetched"] += 1
                    time.sleep(fetch_delay_s)
                except httpx.HTTPError as exc:
                    entry = {
                        "fetched": False,
                        "manufacturer_style": None,
                        "error": str(exc),
                    }
                    cache[cache_key] = entry
                    stats["skipped"] += 1
        elif entry is not None:
            stats["cached"] += 1
        else:
            meta["manufacturer_verified"] = False
            meta["manufacturer_style"] = None
            meta["manufacturer_match"] = None
            stats["unknown"] += 1
            continue

        manufacturer_style = entry.get("manufacturer_style")
        match = styles_compatible(assigned, manufacturer_style)
        meta["manufacturer_verified"] = bool(entry.get("fetched"))
        meta["manufacturer_style"] = manufacturer_style
        meta["manufacturer_match"] = match
        meta["manufacturer_title"] = entry.get("title")
        if entry.get("error"):
            meta["manufacturer_error"] = entry["error"]

        if match is True:
            stats["matched"] += 1
        elif match is False:
            stats["mismatch"] += 1
        else:
            stats["unknown"] += 1

    if client is not None or stats["cached"]:
        _save_style_cache(cache)

    return stats
