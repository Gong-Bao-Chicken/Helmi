"""Crawl manufacturer sites for helmet protection technology (MIPS variants, etc.)."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urljoin, urlparse

import httpx

from protection_tech import (
    MIPS_VARIANT_LABELS,
    classify_protection_tech,
    extract_protection_from_text,
)


def manufacturer_search_url(brand: str, model: str, brands: dict[str, dict]) -> str | None:
    brand_info = brands.get(brand.lower(), {})
    template = brand_info.get("search_url")
    if not template:
        return None
    return template.format(query=quote_plus(model))

SCRIPT_DIR = Path(__file__).resolve().parent
PROTECTION_CACHE_PATH = SCRIPT_DIR / "manufacturer_protection_cache.json"

SKIP_URL_FRAGMENTS = (
    "Search-ShowAjax",
    "javascript:",
    "#",
    "?prefn",
    "?srule=",
    "?pmin=",
    "/search?",
    "/cart",
    "/account",
    "/login",
)


def load_protection_cache(path: Path | None = None) -> dict[str, dict[str, Any]]:
    path = path or PROTECTION_CACHE_PATH
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_protection_cache(cache: dict[str, dict[str, Any]], path: Path | None = None) -> None:
    path = path or PROTECTION_CACHE_PATH
    path.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def html_to_text(html: str) -> str:
    cleaned = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.I | re.S)
    cleaned = re.sub(r"<style[^>]*>.*?</style>", " ", cleaned, flags=re.I | re.S)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _url_is_skippable(href: str) -> bool:
    lowered = href.lower()
    return any(fragment.lower() in lowered for fragment in SKIP_URL_FRAGMENTS)


SIGNIFICANT_SHORT_TOKENS = frozenset({"rs", "pro", "3k", "2x", "4x", "lt", "xl", "io"})


def model_slug_tokens(model: str) -> list[str]:
    tokens = [token for token in re.split(r"[^a-z0-9]+", model.lower()) if token]
    noise = {"helmet", "mips", "carbon", "bike", "mtb", "road"}
    return [
        token
        for token in tokens
        if token not in noise and (len(token) > 2 or token in SIGNIFICANT_SHORT_TOKENS)
    ]


def _model_fully_mentioned(model: str, text: str | None) -> bool:
    if not text:
        return False
    tokens = model_slug_tokens(model)
    if not tokens:
        return False
    lowered = text.lower()
    return all(token in lowered for token in tokens)


def _url_matches_model(href: str, model: str) -> bool:
    tokens = model_slug_tokens(model)
    if not tokens:
        return False
    lowered = href.lower()
    return all(token in lowered for token in tokens)


def score_product_url(href: str, model: str, *, brand: str = "") -> int:
    if not href or _url_is_skippable(href):
        return -100

    href_lower = href.lower()
    tokens = model_slug_tokens(model)
    if not tokens:
        return -100

    token_hits = sum(1 for token in tokens if token in href_lower)
    if token_hits == 0:
        return -100

    score = token_hits * 8
    if token_hits == len(tokens):
        score += 25
    slug = "-".join(tokens)
    if slug and slug in href_lower.replace("_", "-"):
        score += 15
    elif token_hits >= min(2, len(tokens)):
        score += 10
    if tokens[0] in href_lower:
        score += 6

    if "/product/" in href_lower:
        score += 12
    if "/helmets/" in href_lower or re.search(r"/helmet[s]?/", href_lower):
        score += 6

    if "moto" in href_lower and any(
        token in model.lower() for token in ("speedframe", "proframe", "dropframe", "crossframe")
    ):
        score -= 30

    if brand and brand.lower().replace(" ", "") in href_lower.replace("-", "").replace("_", ""):
        score += 2

    return score


def collect_product_url_candidates(html: str, base_url: str, model: str, *, brand: str = "") -> list[str]:
    seen: set[str] = set()
    ranked: list[tuple[int, str]] = []

    for match in re.finditer(r'href=["\']([^"\']+)["\']', html, re.I):
        href = match.group(1).strip()
        if href.startswith("#"):
            continue
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in ("http", "https"):
            continue
        normalized = parsed._replace(fragment="", query="").geturl()
        if normalized in seen:
            continue
        seen.add(normalized)

        score = score_product_url(normalized, model, brand=brand)
        if score <= 0:
            continue
        ranked.append((score, normalized))

    ranked.sort(key=lambda item: (-item[0], len(item[1])))
    return [url for _, url in ranked]


def pick_best_product_url(html: str, base_url: str, model: str, *, brand: str = "") -> str | None:
    candidates = collect_product_url_candidates(html, base_url, model, brand=brand)
    if not candidates:
        return None

    best = candidates[0]
    for candidate in candidates[:12]:
        if _url_matches_model(candidate, model):
            return candidate
    if _url_matches_model(best, model):
        return best
    return best if _model_fully_mentioned(model, best) else candidates[0]


def extract_sku_product_urls(html: str, base_url: str, model: str) -> list[str]:
    tokens = model_slug_tokens(model)
    if not tokens:
        return []

    urls: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r'href=["\']([^"\']*?/product/[^"\']+)["\']', html, re.I):
        href = urljoin(base_url, match.group(1))
        href_lower = href.lower()
        if not _url_matches_model(href, model):
            continue
        normalized = urlparse(href)._replace(fragment="").geturl()
        if normalized in seen:
            continue
        seen.add(normalized)
        urls.append(normalized)
    return urls


def page_has_protection_signals(html: str) -> bool:
    text = html_to_text(html)
    signals = extract_protection_from_text(text)
    return bool(
        signals.get("mips_variant")
        or signals.get("spin")
        or signals.get("sweet_2vi")
        or signals.get("wavecel")
        or signals.get("koroyd")
    )


def analyze_protection_html(
    html: str,
    *,
    product_url: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    text = html_to_text(html)
    if model and not _model_fully_mentioned(model, text) and not _url_matches_model(product_url or "", model):
        return {
            "fetched": True,
            "product_url": product_url,
            "mips_variant": None,
            "mips_label": None,
            "protection_tech": None,
            "snippet": None,
            "error": "model_mismatch",
        }

    signals = extract_protection_from_text(text)
    features = {
        "mips_standard": bool(signals.get("mips_variant") and signals["mips_variant"] != "spherical"),
        "mips_spherical": signals.get("mips_variant") == "spherical",
        "spin": bool(signals.get("spin")),
        "sweet_2vi": bool(signals.get("sweet_2vi")),
        "wavecel": bool(signals.get("wavecel")),
        "koroyd": bool(signals.get("koroyd")),
    }
    if signals.get("mips_variant") == "spherical":
        features["mips_standard"] = False

    synthetic = {"features": features, "protection": {"mips_variant": signals.get("mips_variant")}}
    protection_tech = classify_protection_tech(synthetic)

    mips_variant = signals.get("mips_variant")
    snippet = signals.get("snippet")
    if not snippet and mips_variant:
        match = re.search(rf".{{0,60}}mips.{{0,80}}", text, re.I)
        snippet = match.group(0).strip() if match else None

    return {
        "fetched": True,
        "product_url": product_url,
        "mips_variant": mips_variant,
        "mips_label": MIPS_VARIANT_LABELS.get(mips_variant) if mips_variant else None,
        "protection_tech": protection_tech,
        "snippet": snippet,
        "spin": signals.get("spin"),
        "sweet_2vi": signals.get("sweet_2vi"),
        "wavecel": signals.get("wavecel"),
        "koroyd": signals.get("koroyd"),
        "error": None,
    }


def fetch_manufacturer_protection_page(
    client: httpx.Client,
    search_url: str,
    *,
    brand: str,
    model: str,
    website: str | None = None,
) -> dict[str, Any]:
    response = client.get(search_url, follow_redirects=True)
    response.raise_for_status()
    html = response.text
    base_url = str(response.url)

    product_url = pick_best_product_url(html, base_url, model, brand=brand)
    pages_to_try: list[str] = []

    if product_url and product_url.rstrip("/") != base_url.rstrip("/"):
        pages_to_try.append(product_url)
    elif product_url:
        pages_to_try.append(product_url)

    if not pages_to_try:
        pages_to_try.append(base_url)

    last_result: dict[str, Any] | None = None
    for url in pages_to_try:
        page_response = client.get(url, follow_redirects=True)
        page_response.raise_for_status()
        page_html = page_response.text
        page_url = str(page_response.url)

        subcategory = pick_best_product_url(page_html, page_url, model, brand=brand)
        if subcategory and subcategory.rstrip("/") != page_url.rstrip("/") and _url_matches_model(subcategory, model):
            sub_response = client.get(subcategory, follow_redirects=True)
            sub_response.raise_for_status()
            page_html = sub_response.text
            page_url = str(sub_response.url)

        result = analyze_protection_html(
            page_html,
            product_url=page_url,
            model=model,
        )
        last_result = result
        if result.get("error") == "model_mismatch":
            continue
        if page_has_protection_signals(page_html) and _model_fully_mentioned(model, html_to_text(page_html)):
            return result

        for sku_url in extract_sku_product_urls(page_html, page_url, model)[:5]:
            sku_response = client.get(sku_url, follow_redirects=True)
            sku_response.raise_for_status()
            sku_result = analyze_protection_html(
                sku_response.text,
                product_url=str(sku_response.url),
                model=model,
            )
            last_result = sku_result
            if sku_result.get("error") == "model_mismatch":
                continue
            if page_has_protection_signals(sku_response.text):
                return sku_result
            time.sleep(0.25)

    if last_result:
        if not last_result.get("mips_variant") and not last_result.get("protection_tech"):
            last_result["protection_tech"] = "none"
        if last_result.get("mips_variant"):
            return last_result

    if website:
        from retailer_protection import resolve_product_url_via_site_search

        resolved = resolve_product_url_via_site_search(
            client,
            brand=brand,
            model=model,
            website=website,
        )
        if resolved:
            page_response = client.get(resolved, follow_redirects=True)
            page_response.raise_for_status()
            site_result = analyze_protection_html(
                page_response.text,
                product_url=str(page_response.url),
                model=model,
            )
            if site_result.get("mips_variant"):
                site_result["source"] = "manufacturer_site_search"
                return site_result
            if last_result is None:
                last_result = site_result

    if last_result:
        if not last_result.get("mips_variant") and not last_result.get("protection_tech"):
            last_result["protection_tech"] = "none"
        return last_result

    return {
        "fetched": True,
        "product_url": product_url,
        "mips_variant": None,
        "mips_label": None,
        "protection_tech": "none",
        "snippet": None,
        "error": "no_protection_signals",
    }


def crawl_helmet_protection(
    helmet: dict[str, Any],
    brands: dict[str, dict],
    client: httpx.Client,
    *,
    force: bool = False,
    cache: dict[str, dict[str, Any]] | None = None,
    fetch_delay_s: float = 0.75,
) -> dict[str, Any]:
    cache = cache if cache is not None else load_protection_cache()
    helmet_id = helmet["id"]
    if not force and helmet_id in cache and cache[helmet_id].get("fetched"):
        return cache[helmet_id]

    search_url = manufacturer_search_url(helmet["brand"], helmet["model"], brands)
    if not search_url:
        entry = {
            "fetched": False,
            "mips_variant": None,
            "protection_tech": None,
            "error": "no_search_url",
        }
        cache[helmet_id] = entry
        return entry

    brand_info = brands.get(helmet["brand"].lower(), {})
    website = brand_info.get("website")

    try:
        entry = fetch_manufacturer_protection_page(
            client,
            search_url,
            brand=helmet["brand"],
            model=helmet["model"],
            website=website,
        )
        entry["source"] = "manufacturer_crawl"
        cache[helmet_id] = entry
        time.sleep(fetch_delay_s)
        return entry
    except httpx.HTTPError as exc:
        entry = {
            "fetched": False,
            "mips_variant": None,
            "protection_tech": None,
            "error": str(exc),
        }
        cache[helmet_id] = entry
        return entry


def manufacturer_protection_lookup_entries(
    cache: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    for helmet_id, entry in cache.items():
        variant = entry.get("mips_variant")
        if not entry.get("fetched") or not variant:
            continue
        entries[helmet_id] = {
            "variant": variant,
            "source": entry.get("source") or "manufacturer_crawl",
            "product_url": entry.get("product_url"),
            "snippet": entry.get("snippet"),
        }
    return entries


def merge_manufacturer_cache_into_lookup(
    lookup: dict[str, Any],
    cache: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    merged = {
        "meta": dict(lookup.get("meta", {})),
        "helmets": dict(lookup.get("helmets", {})),
        "patterns": list(lookup.get("patterns", [])),
    }
    for helmet_id, entry in manufacturer_protection_lookup_entries(cache).items():
        merged["helmets"][helmet_id] = entry
    return merged


def apply_manufacturer_protection_crawl(
    helmets: list[dict[str, Any]],
    brands: dict[str, dict],
    *,
    client: httpx.Client | None = None,
    cache_only: bool = False,
    helmet_ids: set[str] | None = None,
    fetch_delay_s: float = 0.75,
) -> dict[str, int]:
    cache = load_protection_cache()
    stats = {"cached": 0, "fetched": 0, "skipped": 0, "detected": 0, "errors": 0}

    targets = helmets
    if helmet_ids:
        targets = [helmet for helmet in helmets if helmet["id"] in helmet_ids]

    for helmet in targets:
        helmet_id = helmet["id"]
        if cache_only:
            if helmet_id in cache:
                stats["cached"] += 1
                if cache[helmet_id].get("mips_variant"):
                    stats["detected"] += 1
            else:
                stats["skipped"] += 1
            continue

        if client is None:
            stats["skipped"] += 1
            continue

        had_cache = helmet_id in cache and cache[helmet_id].get("fetched")
        entry = crawl_helmet_protection(
            helmet,
            brands,
            client,
            cache=cache,
            fetch_delay_s=fetch_delay_s,
        )
        if had_cache:
            stats["cached"] += 1
        else:
            stats["fetched"] += 1

        if entry.get("error"):
            stats["errors"] += 1
        elif entry.get("mips_variant"):
            stats["detected"] += 1

    if client is not None or stats["cached"]:
        save_protection_cache(cache)

    return stats


def write_cache_to_mips_lookup(
    cache: dict[str, dict[str, Any]],
    lookup_path: Path | None = None,
) -> int:
    from protection_tech import MIPS_LOOKUP_PATH, load_mips_lookup

    lookup_path = lookup_path or MIPS_LOOKUP_PATH
    lookup = load_mips_lookup(lookup_path)
    updated = 0
    for helmet_id, entry in manufacturer_protection_lookup_entries(cache).items():
        existing = lookup["helmets"].get(helmet_id)
        new_entry = {
            "variant": entry["variant"],
            "source": "manufacturer",
            "note": entry.get("snippet") or entry.get("product_url"),
        }
        if existing != new_entry:
            lookup["helmets"][helmet_id] = new_entry
            updated += 1
    lookup_path.write_text(json.dumps(lookup, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return updated
