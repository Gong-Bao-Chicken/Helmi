"""Fetch Virginia Tech bicycle helmet ratings and enrich with manufacturer metadata."""

import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import httpx

from .enrich.aero import load_aero_ratings, merge_aero_ratings
from .enrich.aero_sources import aero_sources_for_filters, aero_tiers_for_filters
from .enrich.manufacturer_protection import (
    PROTECTION_CACHE_PATH,
    apply_manufacturer_protection_crawl,
    load_protection_cache,
)
from .enrich.protection_tech import (
    apply_protection_to_all,
    mips_variants_for_filters,
    protection_groups_for_filters,
    protection_technologies_for_filters,
)
from .enrich.ratings import (
    RATING_SOURCES,
    finalize_all_ratings,
    merge_extra_ratings,
    rating_sources_for_filters,
    value_ratio_from_ratings,
    vt_rating_block,
)
from .enrich.retailer_protection import (
    RETAILER_CACHE_PATH,
    apply_retailer_protection_crawl,
    load_retailer_protection_cache,
)
from .enrich.styles import STYLE_CACHE_PATH, apply_style_verifications, infer_style, refine_helmet_styles
from .paths import (
    AERO_RATINGS_PATH,
    BRANDS_PATH,
    EU_BRANDS_PATH,
    EXTRA_RATINGS_PATH,
    EXTRA_RATINGS_RAW_PATH,
    HELMETS_JSON_PATH,
)
from .steps.extra_ratings import run_fetch_extra_ratings

VT_DATA_URL = "https://www.helmet.beam.vt.edu/js/bicycleData.js"
VT_IMAGE_BASE = "https://www.helmet.beam.vt.edu/images/bicycle/"
DEFAULT_OUTPUT = HELMETS_JSON_PATH

USER_AGENT = "HelmetCompare/0.1 (+https://github.com/local/helmet-compare; research prototype)"


def slugify(*parts: str) -> str:
    text = "-".join(parts).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def parse_vt_js(js_text: str) -> list[dict]:
    if "bicycleDataRaw" not in js_text:
        raise ValueError("Unexpected VT data format: bicycleDataRaw not found")

    start = js_text.index("[")
    end = js_text.rindex("]") + 1
    array_text = js_text[start:end]
    json_text = re.sub(
        r"([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*:)",
        r'\1"\2"\3',
        array_text,
    )
    return json.loads(json_text)


def parse_usd_cost(cost: str | None) -> float | None:
    if not cost:
        return None
    match = re.search(r"[\d.]+", cost.replace(",", ""))
    return float(match.group()) if match else None


def extract_features(model: str, certifications: str) -> dict[str, bool]:
    model_lower = model.lower()
    cert_upper = certifications.upper()
    combined = f"{model} {certifications}".lower()

    spherical = bool(re.search(r"spherical", combined, re.I))
    mips_in_name = bool(re.search(r"mips", combined, re.I))
    mips_standard = mips_in_name and not spherical
    mips_spherical = spherical
    wavecel = bool(re.search(r"wavecel", combined, re.I))
    spin = bool(re.search(r"\bspin\b", combined, re.I))
    sweet_2vi = bool(re.search(r"\b2vi\b", combined, re.I))
    koroyd = "koroyd" in combined

    rotational_protection = mips_standard or mips_spherical or wavecel or spin or sweet_2vi

    return {
        "mips_standard": mips_standard,
        "mips_spherical": mips_spherical,
        "wavecel": wavecel,
        "spin": spin,
        "sweet_2vi": sweet_2vi,
        "koroyd": koroyd,
        "rotational_protection": rotational_protection,
        "nta8776": "NTA" in cert_upper or "NTA" in model.upper(),
        "asia_fit": "asia fit" in model_lower,
        "round_fit": "round fit" in model_lower,
    }


def feature_labels(features: dict[str, bool]) -> list[str]:
    labels = {
        "mips_standard": "MIPS",
        "mips_spherical": "MIPS Spherical",
        "wavecel": "WaveCel",
        "spin": "POC SPIN",
        "sweet_2vi": "Sweet Protection 2Vi",
        "koroyd": "Koroyd",
        "nta8776": "NTA 8776",
        "asia_fit": "Asia Fit",
        "round_fit": "Round Fit",
    }
    skip = {"rotational_protection"}
    return [labels[key] for key, enabled in features.items() if enabled and key not in skip]


def load_eu_brands() -> set[str]:
    if not EU_BRANDS_PATH.exists():
        return set()
    brands = json.loads(EU_BRANDS_PATH.read_text(encoding="utf-8"))
    aliases = {
        "abus": "abus",
        "100 percent": "100 percent",
        "scott": "scott",
        "leatt": "leatt",
        "giant/liv": "giant/liv",
        "kali": "kali",
        "giro": "giro",
        "poc": "poc",
        "met": "met",
    }
    normalized = {brand.lower() for brand in brands}
    for alias, _target in aliases.items():
        if alias in normalized:
            normalized.add(alias)
    return normalized


def is_eu_brand(brand: str, eu_brands: set[str]) -> bool:
    return brand.lower() in eu_brands


def is_eu_version(features: dict[str, bool]) -> bool:
    return not features["asia_fit"] and not features["round_fit"]


def is_european_market(brand: str, features: dict[str, bool], eu_brands: set[str]) -> bool:
    return is_eu_brand(brand, eu_brands) and is_eu_version(features)


def load_brands() -> dict[str, dict]:
    if not BRANDS_PATH.exists():
        return {}
    raw = json.loads(BRANDS_PATH.read_text(encoding="utf-8"))
    by_lower = {name.lower(): info for name, info in raw.items()}
    aliases = {
        "abus": "Abus",
        "100 percent": "100%",
        "scott": "Scott",
        "leatt": "Leatt",
        "giant/liv": "Liv",
        "kali": "Kali Protectives",
        "bell sports": "Bell",
        "trek": "Trek",
    }
    for alias, target in aliases.items():
        target_info = raw.get(target) or by_lower.get(target.lower())
        if target_info:
            by_lower[alias] = target_info
    return by_lower


def manufacturer_links(brand: str, model: str, brands: dict[str, dict]) -> dict:
    brand_info = brands.get(brand.lower(), {})
    query = quote_plus(f"{brand} {model}")
    search_url = brand_info.get("search_url", "").format(query=query) if brand_info else None
    return {
        "website": brand_info.get("website"),
        "search_url": search_url or None,
    }


def extract_meta_from_html(html: str) -> dict[str, str | None]:
    def meta(property_name: str) -> str | None:
        patterns = [
            rf'<meta[^>]+property=["\']{property_name}["\'][^>]+content=["\']([^"\']+)["\']',
            rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']{property_name}["\']',
            rf'<meta[^>]+name=["\']{property_name}["\'][^>]+content=["\']([^"\']+)["\']',
            rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']{property_name}["\']',
        ]
        for pattern in patterns:
            match = re.search(pattern, html, re.I)
            if match:
                return match.group(1).strip()
        return None

    title_match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
    return {
        "title": meta("og:title") or (title_match.group(1).strip() if title_match else None),
        "description": meta("og:description") or meta("description"),
        "image": meta("og:image"),
    }


def fetch_manufacturer_meta(
    client: httpx.Client,
    search_url: str | None,
    cache: dict[str, dict],
    cache_key: str,
) -> dict:
    if cache_key in cache:
        return cache[cache_key]

    result = {
        "fetched": False,
        "title": None,
        "description": None,
        "image": None,
        "error": None,
    }

    if not search_url:
        result["error"] = "no_search_url"
        cache[cache_key] = result
        return result

    try:
        response = client.get(search_url, follow_redirects=True)
        response.raise_for_status()
        meta = extract_meta_from_html(response.text)
        result.update(meta)
        result["fetched"] = True
    except httpx.HTTPError as exc:
        result["error"] = str(exc)

    cache[cache_key] = result
    return result


def empty_features() -> dict[str, bool]:
    return {
        "mips_standard": False,
        "mips_spherical": False,
        "wavecel": False,
        "spin": False,
        "sweet_2vi": False,
        "koroyd": False,
        "rotational_protection": False,
        "nta8776": False,
        "asia_fit": False,
        "round_fit": False,
    }


BRAND_ALIASES = {
    "btwin": "Btwin",
    "b'twin": "Btwin",
    "decathlon": "Decathlon",
    "van rysel": "Van Rysel",
}


def vt_image_url(photo: str | None, slug: str) -> str:
    """VT serves photos at /images/bicycle/<photo> (photo field of bicycleData.js)."""
    filename = (photo or "").strip() or f"{slug}.jpg"
    return f"{VT_IMAGE_BASE}{filename}"


def normalize_brand(brand: str) -> str:
    return BRAND_ALIASES.get(brand.strip().lower().replace("’", "'"), brand.strip())


def parse_name_brand_model(name: str) -> tuple[str, str]:
    cleaned = re.sub(r"\s+", " ", name).strip()
    parts = cleaned.split(" ", 1)
    if len(parts) == 1:
        return cleaned, cleaned
    return normalize_brand(parts[0]), parts[1]


def rating_block_from_unmatched(entry: dict) -> dict[str, Any]:
    source = entry["source"]
    if source == "certimoov":
        return {
            "score": entry["score"],
            "stars": entry["stars"],
            "test_year": entry.get("test_year"),
            "url": entry.get("url"),
            "impact_scores": entry.get("impact_scores", {}),
            "rank_pct": None,
        }
    if source == "folksam":
        return {
            "recommended": entry.get("recommended"),
            "overall_result_pct": entry.get("overall_result_pct"),
            "grade": entry.get("grade"),
            "segment": entry.get("segment"),
            "test_year": entry.get("test_year"),
            "url": entry.get("url"),
            "rank_pct": None,
        }
    if source == "nsw_helmet_star":
        return {
            "stars": entry.get("stars"),
            "category": entry.get("category"),
            "price_band": entry.get("price_band"),
            "test_year": entry.get("test_year"),
            "url": entry.get("url"),
            "rank_pct": None,
        }
    return {}


def normalize_brand_names(helmets: list[dict]) -> None:
    """Pick one display spelling per brand (case-insensitive)."""
    from collections import Counter

    tallies: dict[str, Counter[str]] = {}
    for helmet in helmets:
        brand = helmet["brand"].strip()
        key = brand.lower()
        tallies.setdefault(key, Counter())[brand] += 1

    canonical = {key: counts.most_common(1)[0][0] for key, counts in tallies.items()}
    for helmet in helmets:
        helmet["brand"] = canonical[helmet["brand"].strip().lower()]
        helmet["brand_key"] = helmet["brand"].lower()
        helmet["search_text"] = f"{helmet['brand']} {helmet['model']}".lower()


def standalone_from_unmatched(entry: dict, eu_brands: set[str]) -> dict | None:
    source = entry.get("source")
    if source not in RATING_SOURCES:
        return None

    if source == "certimoov":
        brand = normalize_brand(entry.get("brand", ""))
        model = entry.get("model", "")
        if not brand:  # current CERTIMOOV pages only have a combined "<Brand> <Model>" title
            brand, model = parse_name_brand_model(model)
    elif source == "folksam":
        brand, model = parse_name_brand_model(entry.get("name", ""))
    elif source == "nsw_helmet_star":
        brand, model = parse_name_brand_model(entry.get("model", ""))
    else:
        return None

    if not brand or not model:
        return None

    features = extract_features(model, "")
    eu_brand = is_eu_brand(brand, eu_brands)
    eu_version = is_eu_version(features)
    helmet_id = f"extra-{entry.get('slug') or slugify(brand, model)}"
    rating_block = rating_block_from_unmatched(entry)
    stars = rating_block.get("stars", 0) or 0

    source_urls = {
        "certimoov": entry.get("url"),
        "folksam": entry.get("url"),
        "nsw_helmet_star": entry.get("url"),
    }

    inferred_style = infer_style(brand, model)
    return {
        "id": helmet_id,
        "brand": brand,
        "model": model,
        "search_text": f"{brand} {model}".lower(),
        "catalog": "extra_only",
        "primary_rating_source": source,
        "score": rating_block.get("score"),
        "stars": stars,
        "ratings": {source: rating_block},
        "style": inferred_style,
        "style_meta": {
            "assigned": inferred_style,
            "source": "inferred",
        },
        "test_year": rating_block.get("test_year"),
        "certifications": "",
        "score_low_impact": None,
        "score_high_impact": None,
        "price_at_test_usd": None,
        "price_at_test_label": None,
        "value_ratio": None,
        "image_url": entry.get("image_url"),
        "features": features,
        "feature_labels": feature_labels(features),
        "eu_brand": eu_brand,
        "eu_version": eu_version,
        "european_market": is_european_market(brand, features, eu_brands),
        "listings": market_listings(),
        "manufacturer": {
            "website": None,
            "search_url": None,
            "fetched": False,
            "title": None,
            "description": None,
            "image": None,
            "error": "extra_only",
        },
        "source": {
            "name": RATING_SOURCES[source]["label"],
            "url": source_urls.get(source) or RATING_SOURCES[source]["url"],
        },
    }


def _unmatched_dedupe_key(standalone: dict) -> tuple:
    """CERTIMOOV publishes some tests twice (slug ``foo`` and ``foo-0``) with identical data."""
    source = standalone["primary_rating_source"]
    block = dict(standalone["ratings"][source])
    block.pop("url", None)
    name = re.sub(r"[^a-z0-9]+", "", f"{standalone['brand']} {standalone['model']}".lower())
    return source, name, json.dumps(block, sort_keys=True)


def append_unmatched_helmets(helmets: list[dict], unmatched: list[dict], eu_brands: set[str]) -> int:
    existing_ids = {helmet["id"] for helmet in helmets}
    seen_keys: set[tuple] = set()
    added = 0
    for entry in unmatched:
        standalone = standalone_from_unmatched(entry, eu_brands)
        if not standalone or standalone["id"] in existing_ids:
            continue
        key = _unmatched_dedupe_key(standalone)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        helmets.append(standalone)
        existing_ids.add(standalone["id"])
        added += 1
    return added


def load_unmatched_extra_ratings() -> list[dict]:
    if not EXTRA_RATINGS_RAW_PATH.exists():
        return []
    payload = json.loads(EXTRA_RATINGS_RAW_PATH.read_text(encoding="utf-8"))
    return payload.get("unmatched", [])


def empty_market_listing(currency: str, source: str) -> dict:
    return {
        "price": None,
        "currency": currency,
        "rating": None,
        "review_count": None,
        "url": None,
        "source": source,
        "fetched_at": None,
    }


def market_listings() -> dict:
    return {
        "de": empty_market_listing("EUR", "amazon_de"),
        "at": empty_market_listing("EUR", "geizhals_at"),
        "ch": empty_market_listing("CHF", "galaxus"),
    }


def enrich_helmet(
    raw: dict,
    brands: dict[str, dict],
    eu_brands: set[str],
    client: httpx.Client | None,
    manufacturer_cache: dict[str, dict],
    fetch_manufacturer: bool,
) -> dict:
    brand = raw["brand"]
    model = raw["model"]
    certifications = raw.get("certifications", "")
    features = extract_features(model, certifications)
    links = manufacturer_links(brand, model, brands)

    manufacturer_meta = {
        "fetched": False,
        "title": None,
        "description": None,
        "image": None,
        "error": "skipped",
    }

    if fetch_manufacturer and client is not None:
        cache_key = slugify(brand, model)
        manufacturer_meta = fetch_manufacturer_meta(
            client,
            links.get("search_url"),
            manufacturer_cache,
            cache_key,
        )
        time.sleep(0.75)

    price = parse_usd_cost(raw.get("cost"))
    vt_score = raw["score"]
    vt_block = vt_rating_block(
        score=vt_score,
        test_year=raw.get("date"),
        score_low=raw.get("low"),
        score_high=raw.get("high"),
    )
    value_ratio = None

    return {
        "id": slugify(brand, model),
        "brand": brand,
        "brand_key": brand.lower(),
        "model": model,
        "search_text": f"{brand} {model}".lower(),
        "score": vt_score,
        "ratings": {
            "virginia_tech": vt_block,
        },
        "style": raw["style"],
        "style_meta": {
            "assigned": raw["style"],
            "source": "virginia_tech",
            "vt_style": raw["style"],
        },
        "test_year": raw.get("date"),
        "certifications": certifications,
        "score_low_impact": raw.get("low"),
        "score_high_impact": raw.get("high"),
        "price_at_test_usd": price,
        "price_at_test_label": raw.get("cost"),
        "value_ratio": value_ratio,
        "image_url": vt_image_url(raw.get("photo"), slugify(brand, model)),
        "features": features,
        "feature_labels": feature_labels(features),
        "eu_brand": is_eu_brand(brand, eu_brands),
        "eu_version": is_eu_version(features),
        "european_market": is_european_market(brand, features, eu_brands),
        "listings": market_listings(),
        "manufacturer": {
            **links,
            **manufacturer_meta,
        },
        "source": {
            "name": "Virginia Tech Helmet Lab",
            "url": "https://www.helmet.beam.vt.edu/bicycle-helmet-ratings.html",
        },
    }


def fetch_vt_data(client: httpx.Client, *, attempts: int = 4) -> list[dict]:
    """Fetch bicycleData.js, retrying transient network/TLS errors (VT drops TLS now and then)."""
    for attempt in range(1, attempts + 1):
        try:
            response = client.get(VT_DATA_URL)
            response.raise_for_status()
            return parse_vt_js(response.text)
        except httpx.HTTPError as exc:
            if attempt == attempts:
                raise
            wait = 2**attempt
            print(
                f"  VT fetch failed ({type(exc).__name__}: {exc}); retry {attempt}/{attempts - 1} in {wait}s"
            )
            time.sleep(wait)
    raise AssertionError("unreachable")


def build_dataset(
    fetch_manufacturer: bool,
    *,
    skip_extra_ratings: bool = False,
    verify_styles: bool = False,
    verify_styles_cache_only: bool = False,
    crawl_manufacturer_protection: bool = False,
    manufacturer_protection_cache_only: bool = False,
    crawl_retailer_protection: bool = False,
    retailer_protection_cache_only: bool = False,
) -> dict:
    brands = load_brands()
    eu_brands = load_eu_brands()
    manufacturer_cache: dict[str, dict] = {}

    with httpx.Client(
        timeout=20.0,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        raw_helmets = fetch_vt_data(client)
        helmets = []
        for raw in raw_helmets:
            helmets.append(
                enrich_helmet(
                    raw,
                    brands,
                    eu_brands,
                    client if fetch_manufacturer else None,
                    manufacturer_cache,
                    fetch_manufacturer,
                )
            )

    extra_merged = 0
    extra_meta = None
    extra_only_added = 0
    if not skip_extra_ratings and EXTRA_RATINGS_PATH.exists():
        extra = json.loads(EXTRA_RATINGS_PATH.read_text(encoding="utf-8"))
        extra_meta = extra.get("meta")
        extra_merged = merge_extra_ratings(helmets, extra.get("matches", []))

    if not skip_extra_ratings:
        extra_only_added = append_unmatched_helmets(helmets, load_unmatched_extra_ratings(), eu_brands)

    finalize_all_ratings(helmets)

    aero_stats: dict[str, Any] = {}
    if AERO_RATINGS_PATH.exists():
        aero_stats = merge_aero_ratings(helmets, load_aero_ratings(AERO_RATINGS_PATH))

    protection_crawl_stats: dict[str, int] = {}
    manufacturer_protection_cache = load_protection_cache()
    if crawl_manufacturer_protection or manufacturer_protection_cache_only or PROTECTION_CACHE_PATH.exists():
        with httpx.Client(
            timeout=30.0,
            headers={"User-Agent": USER_AGENT},
        ) as protection_client:
            protection_crawl_stats = apply_manufacturer_protection_crawl(
                helmets,
                brands,
                client=protection_client
                if crawl_manufacturer_protection and not manufacturer_protection_cache_only
                else None,
                cache_only=manufacturer_protection_cache_only or not crawl_manufacturer_protection,
            )
        manufacturer_protection_cache = load_protection_cache()

    retailer_crawl_stats: dict[str, int] = {}
    retailer_protection_cache = load_retailer_protection_cache()
    if crawl_retailer_protection or retailer_protection_cache_only or RETAILER_CACHE_PATH.exists():
        with httpx.Client(
            timeout=30.0,
            headers={"User-Agent": USER_AGENT},
        ) as retailer_client:
            retailer_crawl_stats = apply_retailer_protection_crawl(
                helmets,
                client=retailer_client
                if crawl_retailer_protection and not retailer_protection_cache_only
                else None,
                cache_only=retailer_protection_cache_only or not crawl_retailer_protection,
            )
        retailer_protection_cache = load_retailer_protection_cache()

    protection_stats = apply_protection_to_all(
        helmets,
        manufacturer_cache=manufacturer_protection_cache,
        retailer_cache=retailer_protection_cache,
    )

    for helmet in helmets:
        price_usd = helmet.get("price_at_test_usd")
        helmet["value_ratio"] = value_ratio_from_ratings(helmet.get("ratings", {}), price_usd)

    normalize_brand_names(helmets)
    refine_helmet_styles(helmets)

    style_verify_stats: dict[str, int] = {}
    if verify_styles or verify_styles_cache_only or STYLE_CACHE_PATH.exists():
        with httpx.Client(
            timeout=20.0,
            headers={"User-Agent": USER_AGENT},
        ) as verify_client:
            style_verify_stats = apply_style_verifications(
                helmets,
                brands,
                client=verify_client if verify_styles and not verify_styles_cache_only else None,
                cache_only=verify_styles_cache_only or not verify_styles,
            )

    meta_extra: dict = {"extra_ratings_merged": extra_merged, "extra_only_count": extra_only_added}
    if aero_stats:
        meta_extra["aero_ratings_matched"] = aero_stats.get("matched", 0)
        meta_extra["aero_ratings_total"] = aero_stats.get("total_entries", 0)
        meta_extra["helmets_with_aero"] = aero_stats.get("helmets_with_aero", 0)
        meta_extra["aero_catalog_stubs_added"] = aero_stats.get("extra_added", 0)
        if aero_stats.get("by_source"):
            meta_extra["aero_by_source"] = aero_stats["by_source"]
        if aero_stats.get("unmatched_names"):
            meta_extra["aero_ratings_unmatched"] = aero_stats["unmatched_names"]
    if extra_meta:
        meta_extra["extra_ratings_sources"] = extra_meta.get("sources", {})
        meta_extra["extra_ratings_match_count"] = extra_meta.get("match_count")

    helmets.sort(
        key=lambda item: (
            item["score"] if item["score"] is not None else float("inf"),
            item["brand"],
            item["model"],
        )
    )
    eu_market_helmets = [helmet for helmet in helmets if helmet["european_market"]]

    return {
        "meta": {
            "generated_at": datetime.now(UTC).isoformat(),
            "source_url": VT_DATA_URL,
            "helmet_count_total": len(helmets),
            "helmet_count_european_market": len(eu_market_helmets),
            "helmet_count_vt_catalog": len(helmets) - extra_only_added,
            "manufacturer_fetch_enabled": fetch_manufacturer,
            "note": (
                "price_at_test_usd is the US retail price at the time of VT testing, "
                "not a current market price."
            ),
            "extra_ratings_merged": extra_merged,
            **meta_extra,
            **({"style_verification": style_verify_stats} if style_verify_stats else {}),
            **({"manufacturer_protection": protection_crawl_stats} if protection_crawl_stats else {}),
            **({"retailer_protection": retailer_crawl_stats} if retailer_crawl_stats else {}),
            **({"mips_detection": protection_stats} if protection_stats.get("mips_detected") else {}),
        },
        "filters": {
            "rating_sources": rating_sources_for_filters(),
            "presentation_modes": [
                {"key": "virginia_tech", "label": "Virginia Tech"},
                {"key": "folksam", "label": "Folksam"},
                {"key": "certimoov", "label": "CERTIMOOV"},
                {"key": "nsw_helmet_star", "label": "NSW Helmet STAR"},
                {"key": "fused", "label": "Fused (all sources)"},
            ],
            "styles": sorted({helmet["style"] for helmet in helmets}),
            "brands_all": sorted({helmet["brand"] for helmet in helmets}),
            "brands_eu": sorted({helmet["brand"] for helmet in helmets if helmet["eu_brand"]}),
            "protection_groups": protection_groups_for_filters(),
            "protection_technologies": protection_technologies_for_filters(helmets),
            "mips_variants": mips_variants_for_filters(),
            "markets": [
                {"key": "de", "label": "Germany", "currency": "EUR"},
                {"key": "at", "label": "Austria", "currency": "EUR"},
                {"key": "ch", "label": "Switzerland", "currency": "CHF"},
            ],
            "aero_tiers": aero_tiers_for_filters(),
            "aero_sources": aero_sources_for_filters(),
        },
        "helmets": helmets,
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_build(
    *,
    output: Path = DEFAULT_OUTPUT,
    fetch_manufacturer: bool = False,
    fetch_extra_ratings: bool = False,
    skip_extra_ratings: bool = False,
    verify_styles: bool = False,
    verify_styles_cache_only: bool = False,
    crawl_manufacturer_protection: bool = False,
    manufacturer_protection_cache_only: bool = False,
    crawl_retailer_protection: bool = False,
    retailer_protection_cache_only: bool = False,
) -> dict:
    """Build helmets.json from Virginia Tech data plus cached enrichments (formerly fetch_helmets.py)."""
    if fetch_extra_ratings:
        run_fetch_extra_ratings()

    dataset = build_dataset(
        fetch_manufacturer=fetch_manufacturer,
        skip_extra_ratings=skip_extra_ratings,
        verify_styles=verify_styles,
        verify_styles_cache_only=verify_styles_cache_only,
        crawl_manufacturer_protection=crawl_manufacturer_protection,
        manufacturer_protection_cache_only=manufacturer_protection_cache_only,
        crawl_retailer_protection=crawl_retailer_protection,
        retailer_protection_cache_only=retailer_protection_cache_only,
    )

    write_json(output, dataset)

    print(f"Wrote {len(dataset['helmets'])} helmets to {output}")
    print(
        f"European market: {dataset['meta']['helmet_count_european_market']} "
        f"of {dataset['meta']['helmet_count_total']}"
    )
    if not fetch_manufacturer:
        print("Tip: pass --fetch-manufacturer to enrich with vendor page metadata.")
    return dataset
