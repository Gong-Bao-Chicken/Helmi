"""Crawl retailer product pages (Geizhals, Galaxus, etc.) for helmet protection tech."""

import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import httpx
from bs4 import BeautifulSoup

from ..crawlers.price_sources import is_geizhals_product_url
from ..crawlers.stealth_fetch import is_geizhals_html, stealth_get
from ..paths import RETAILER_PROTECTION_CACHE_PATH
from .manufacturer_protection import analyze_protection_html, html_to_text, model_slug_tokens

RETAILER_CACHE_PATH = RETAILER_PROTECTION_CACHE_PATH

RETAILER_SOURCES = frozenset(
    {"geizhals", "geizhals_at", "galaxus", "idealo", "amazon_de", "bike24", "toppreise"}
)
SOURCE_PRIORITY = ("geizhals", "galaxus", "idealo", "toppreise", "bike24", "amazon_de")

MIPS_VARIANT_RANK = {
    "air_node": 90,
    "evolve": 85,
    "integra_split": 80,
    "integra_fuse": 79,
    "integra_tx": 78,
    "integra": 75,
    "spherical": 70,
    "air": 60,
    "standard": 10,
}


def load_retailer_protection_cache(path: Path | None = None) -> dict[str, dict[str, Any]]:
    path = path or RETAILER_CACHE_PATH
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_retailer_protection_cache(
    cache: dict[str, dict[str, Any]],
    path: Path | None = None,
) -> None:
    path = path or RETAILER_CACHE_PATH
    path.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _normalize_source(source: str | None) -> str | None:
    if not source:
        return None
    lowered = source.lower()
    if lowered.startswith("geizhals"):
        return "geizhals"
    return lowered


def collect_retailer_product_urls(
    helmet: dict[str, Any],
    *,
    price_cache_entry: dict[str, Any] | None = None,
) -> list[tuple[str, str]]:
    seen: set[str] = set()
    ranked: list[tuple[int, str, str]] = []

    def add(source: str | None, url: str | None) -> None:
        normalized = _normalize_source(source)
        if not normalized or normalized not in RETAILER_SOURCES:
            return
        if not url or url in seen:
            return
        if normalized == "geizhals" and not is_geizhals_product_url(url):
            return
        seen.add(url)
        priority = SOURCE_PRIORITY.index(normalized) if normalized in SOURCE_PRIORITY else 99
        ranked.append((priority, normalized, url))

    for listing in (helmet.get("listings") or {}).values():
        if not isinstance(listing, dict):
            continue
        add(listing.get("source"), listing.get("url"))
        for offer in listing.get("sources") or []:
            if isinstance(offer, dict):
                add(offer.get("source"), offer.get("url"))

    current = helmet.get("current_price") or {}
    for detail in current.get("source_details") or []:
        if isinstance(detail, dict):
            add(detail.get("source"), detail.get("url"))

    if price_cache_entry:
        for offer in price_cache_entry.get("offers") or []:
            if isinstance(offer, dict):
                add(offer.get("source"), offer.get("url"))
        for history in price_cache_entry.get("history") or []:
            for offer in history.get("offers") or []:
                if isinstance(offer, dict):
                    add(offer.get("source"), offer.get("url"))

    ranked.sort(key=lambda item: (item[0], len(item[2])))
    return [(source, url) for _, source, url in ranked]


def extract_geizhals_product_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    parts: list[str] = []

    title = soup.select_one("h1")
    if title:
        parts.append(title.get_text(" ", strip=True))

    meta = soup.select_one('meta[name="description"]')
    if meta and meta.get("content"):
        parts.append(meta["content"])

    for el in soup.select("[class*=spec], .specs, .specifications"):
        text = el.get_text(" ", strip=True)
        if text and len(text) > 12:
            parts.append(text)

    for label in ("Besonderheiten", "Produkteigenschaften", "Einsatzbereich"):
        match = re.search(
            rf"{label}\s+([^|<]+?)(?:\s+Alle\s+Produkteigenschaften|\s+Beliebteste|$)",
            html_to_text(html),
            re.I,
        )
        if match:
            parts.append(f"{label} {match.group(1).strip()}")

    return " ".join(parts)


def extract_galaxus_product_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    parts: list[str] = []

    for selector in (
        '[data-test="product-title"]',
        "h1",
        '[data-test="product-description"]',
        '[data-test="specifications"]',
        '[data-test="product-specifications"]',
    ):
        for el in soup.select(selector):
            text = el.get_text(" ", strip=True)
            if text:
                parts.append(text)

    for row in soup.select("dl, table tr"):
        text = row.get_text(" ", strip=True)
        if text and len(text) < 240:
            parts.append(text)

    return " ".join(parts)


def extract_retailer_product_text(html: str, source: str) -> str:
    if source == "geizhals":
        return extract_geizhals_product_text(html)
    if source == "galaxus":
        return extract_galaxus_product_text(html)
    return html_to_text(html)


def variant_rank(variant: str | None) -> int:
    if not variant:
        return 0
    return MIPS_VARIANT_RANK.get(variant, 5)


def protection_result_from_html(
    html: str,
    *,
    product_url: str,
    model: str,
    source: str,
) -> dict[str, Any]:
    text = extract_retailer_product_text(html, source)
    result = analyze_protection_html(
        html,
        product_url=product_url,
        model=model,
    )
    if result.get("error") == "model_mismatch":
        signals = analyze_protection_html(
            f"<p>{text}</p>",
            product_url=product_url,
            model=None,
        )
        if signals.get("mips_variant"):
            result = signals
            result["product_url"] = product_url
            result["error"] = None

    result["source"] = source
    result["fetched"] = True
    return result


def fetch_retailer_product_page(url: str, source: str) -> tuple[int, str]:
    if source == "geizhals":
        status, html = stealth_get(url, validator=is_geizhals_html)
        return status, html or ""
    status, html = stealth_get(url)
    return status, html or ""


def best_protection_result(results: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [entry for entry in results if entry.get("fetched") and not entry.get("error")]
    if not candidates:
        return None

    def sort_key(entry: dict[str, Any]) -> tuple[int, int]:
        variant = entry.get("mips_variant")
        source = entry.get("source") or ""
        source_rank = SOURCE_PRIORITY.index(source) if source in SOURCE_PRIORITY else 99
        return (-variant_rank(variant), source_rank)

    return sorted(candidates, key=sort_key)[0]


def crawl_helmet_retailer_protection(
    helmet: dict[str, Any],
    *,
    client: httpx.Client | None = None,
    force: bool = False,
    cache: dict[str, dict[str, Any]] | None = None,
    fetch_delay_s: float = 0.5,
    max_urls: int = 3,
    price_cache_entry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    del client  # retailer pages use stealth_get (curl_cffi for Geizhals TLS)
    cache = cache if cache is not None else load_retailer_protection_cache()
    helmet_id = helmet["id"]
    if not force and helmet_id in cache and cache[helmet_id].get("fetched"):
        return cache[helmet_id]

    urls = collect_retailer_product_urls(helmet, price_cache_entry=price_cache_entry)[:max_urls]
    if not urls:
        entry = {
            "fetched": False,
            "mips_variant": None,
            "protection_tech": None,
            "error": "no_product_urls",
        }
        cache[helmet_id] = entry
        return entry

    results: list[dict[str, Any]] = []
    errors: list[str] = []
    for source, url in urls:
        try:
            status, html = fetch_retailer_product_page(url, source)
            if status != 200 or len(html) < 5_000:
                errors.append(f"{source}:{status}")
                continue
            results.append(
                protection_result_from_html(
                    html,
                    product_url=url,
                    model=helmet["model"],
                    source=source,
                )
            )
        except Exception as exc:  # noqa: BLE001 — collect per-source failures
            errors.append(f"{source}:{exc}")
        time.sleep(fetch_delay_s)

    best = best_protection_result(results)
    if best:
        entry = {
            "fetched": True,
            "product_url": best.get("product_url"),
            "mips_variant": best.get("mips_variant"),
            "mips_label": best.get("mips_label"),
            "protection_tech": best.get("protection_tech"),
            "snippet": best.get("snippet"),
            "source": f"retailer_{best.get('source')}",
            "sources_tried": [item.get("source") for item in results],
            "error": None,
        }
    else:
        entry = {
            "fetched": True,
            "mips_variant": None,
            "protection_tech": "none",
            "error": errors[0] if errors else "no_protection_signals",
            "sources_tried": [source for source, _ in urls],
        }

    cache[helmet_id] = entry
    return entry


def resolve_product_url_via_site_search(
    client: httpx.Client,
    *,
    brand: str,
    model: str,
    website: str,
) -> str | None:
    """Find a manufacturer product page when on-site search is JS-rendered."""
    domain = urlparse(website).netloc
    if not domain:
        return None

    tokens = model_slug_tokens(model)
    if not tokens:
        return None

    query = f"site:{domain} {brand} {model} helmet"
    search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    try:
        response = client.post(
            search_url,
            data={"q": query, "b": "", "kl": "wt-wt"},
            headers={
                "User-Agent": client.headers.get("User-Agent", "Mozilla/5.0"),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            follow_redirects=True,
            timeout=20.0,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        return None

    candidates: list[tuple[int, str]] = []
    for match in re.finditer(r"uddg=([^&\"]+)", response.text):
        href = unquote(match.group(1))
        if domain not in href:
            continue
        href_lower = href.lower()
        if not all(token in href_lower for token in tokens):
            continue
        score = sum(8 for token in tokens if token in href_lower)
        if re.search(r"/p/\d+|/product/", href_lower):
            score += 20
        if "helmet" in href_lower or "helm" in href_lower:
            score += 6
        candidates.append((score, href.split("?")[0]))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (-item[0], len(item[1])))
    return candidates[0][1]


def retailer_protection_lookup_entries(
    cache: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    for helmet_id, entry in cache.items():
        variant = entry.get("mips_variant")
        if not entry.get("fetched") or not variant:
            continue
        entries[helmet_id] = {
            "variant": variant,
            "source": entry.get("source") or "retailer",
            "product_url": entry.get("product_url"),
            "snippet": entry.get("snippet"),
        }
    return entries


def merge_retailer_cache_into_lookup(
    lookup: dict[str, Any],
    cache: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    merged = {
        "meta": dict(lookup.get("meta", {})),
        "helmets": dict(lookup.get("helmets", {})),
        "patterns": list(lookup.get("patterns", [])),
    }
    for helmet_id, entry in retailer_protection_lookup_entries(cache).items():
        existing = merged["helmets"].get(helmet_id)
        if existing and variant_rank(existing.get("variant")) >= variant_rank(entry.get("variant")):
            continue
        merged["helmets"][helmet_id] = entry
    return merged


def apply_retailer_protection_crawl(
    helmets: list[dict[str, Any]],
    *,
    client: httpx.Client | None = None,
    cache_only: bool = False,
    helmet_ids: set[str] | None = None,
    fetch_delay_s: float = 0.5,
) -> dict[str, int]:
    cache = load_retailer_protection_cache()
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

        if client is None and not collect_retailer_product_urls(helmet):
            stats["skipped"] += 1
            continue

        had_cache = helmet_id in cache and cache[helmet_id].get("fetched")
        entry = crawl_helmet_retailer_protection(
            helmet,
            client=client,
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

    if not cache_only:
        save_retailer_protection_cache(cache)

    return stats


def quote_plus(value: str) -> str:
    from urllib.parse import quote_plus as _quote_plus

    return _quote_plus(value)
