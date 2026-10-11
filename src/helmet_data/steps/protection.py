"""Crawl manufacturer websites for helmet protection technology."""

import json
import sys
from pathlib import Path

import httpx

from ..build import USER_AGENT, load_brands
from ..enrich.manufacturer_protection import (
    PROTECTION_CACHE_PATH,
    crawl_helmet_protection,
    load_protection_cache,
    save_protection_cache,
    write_cache_to_mips_lookup,
)
from ..enrich.retailer_protection import (
    crawl_helmet_retailer_protection,
    load_retailer_protection_cache,
    save_retailer_protection_cache,
)
from ..paths import HELMETS_JSON_PATH, PRICE_CACHE_PATH

DEFAULT_HELMETS = HELMETS_JSON_PATH


def load_helmets(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("helmets", [])


def run_fetch_protection(
    *,
    helmets_path: Path = DEFAULT_HELMETS,
    helmet_ids: list[str] | None = None,
    brand: str | None = None,
    all_missing: bool = False,
    limit: int | None = None,
    force: bool = False,
    write_lookup: bool = False,
    retailers: bool = False,
    delay: float = 0.75,
) -> None:
    """Crawl manufacturer (and optionally retailer) pages for helmet protection technology."""
    if not helmets_path.exists():
        print(f"Helmet catalog not found: {helmets_path}", file=sys.stderr)
        sys.exit(1)

    helmets = load_helmets(helmets_path)
    brands = load_brands()
    cache = load_protection_cache()
    retailer_cache = load_retailer_protection_cache()
    price_cache = {}
    price_cache_path = PRICE_CACHE_PATH
    if price_cache_path.exists():
        price_cache = json.loads(price_cache_path.read_text(encoding="utf-8")).get("helmets", {})
    targets = helmets

    if helmet_ids:
        wanted = set(helmet_ids)
        targets = [helmet for helmet in helmets if helmet["id"] in wanted]
        missing = wanted - {helmet["id"] for helmet in targets}
        if missing:
            print(f"Unknown helmet id(s): {', '.join(sorted(missing))}", file=sys.stderr)
            sys.exit(1)
    elif brand:
        brand_lower = brand.lower()
        targets = [helmet for helmet in helmets if helmet["brand"].lower() == brand_lower]
    elif all_missing:
        targets = [
            helmet
            for helmet in helmets
            if helmet["id"] not in cache
            and not (helmet.get("features") or {}).get("rotational_protection")
            and brands.get(helmet["brand"].lower(), {}).get("search_url")
        ]

    if limit is not None:
        targets = targets[:limit]

    if not targets:
        print("No helmets matched.")
        return

    print(f"Crawling {len(targets)} helmet(s)...")
    detected = 0
    errors = 0

    with httpx.Client(timeout=30.0, headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
        for helmet in targets:
            entry = crawl_helmet_protection(
                helmet,
                brands,
                client,
                force=force,
                cache=cache,
                fetch_delay_s=delay,
            )
            label = entry.get("mips_label") or entry.get("protection_tech") or "none"
            status = entry.get("error") or "ok"
            url = entry.get("product_url") or ""
            print(f"  {helmet['id']}: {label} [{status}]")
            if url:
                print(f"    {url}")
            if entry.get("snippet"):
                print(f"    …{entry['snippet'][:90]}")
            if entry.get("mips_variant"):
                detected += 1
            if entry.get("error"):
                errors += 1

            if retailers and not entry.get("mips_variant"):
                retailer_entry = crawl_helmet_retailer_protection(
                    helmet,
                    cache=retailer_cache,
                    price_cache_entry=price_cache.get(helmet["id"]),
                    fetch_delay_s=delay,
                    force=force,
                )
                retailer_label = (
                    retailer_entry.get("mips_label") or retailer_entry.get("protection_tech") or "none"
                )
                print(f"    retailer: {retailer_label}")
                if retailer_entry.get("mips_variant"):
                    detected += 1

    save_protection_cache(cache)
    if retailers:
        save_retailer_protection_cache(retailer_cache)
    print(f"\nCache: {PROTECTION_CACHE_PATH}")
    print(f"Detected protection on {detected}/{len(targets)} helmets ({errors} errors)")

    if write_lookup:
        updated = write_cache_to_mips_lookup(cache)
        print(f"Updated {updated} entries in mips_lookup.json")
