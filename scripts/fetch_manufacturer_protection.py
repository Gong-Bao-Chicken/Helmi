#!/usr/bin/env python3
"""Crawl manufacturer websites for helmet protection technology."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

from fetch_helmets import USER_AGENT, load_brands
from manufacturer_protection import (
    PROTECTION_CACHE_PATH,
    crawl_helmet_protection,
    load_protection_cache,
    save_protection_cache,
    write_cache_to_mips_lookup,
)
from retailer_protection import (
    RETAILER_CACHE_PATH,
    crawl_helmet_retailer_protection,
    load_retailer_protection_cache,
    save_retailer_protection_cache,
)

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_HELMETS = SCRIPT_DIR.parent / "web" / "data" / "helmets.json"


def load_helmets(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("helmets", [])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--helmets-json",
        type=Path,
        default=DEFAULT_HELMETS,
        help="Helmet catalog JSON (default: web/data/helmets.json)",
    )
    parser.add_argument(
        "--helmet",
        action="append",
        dest="helmet_ids",
        metavar="ID",
        help="Crawl specific helmet id(s), e.g. fox-racing-speedframe-rs",
    )
    parser.add_argument(
        "--brand",
        help="Crawl all helmets from this brand (case-insensitive)",
    )
    parser.add_argument(
        "--all-missing",
        action="store_true",
        help="Crawl helmets with no MIPS in model name and no cache entry",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max helmets to crawl in one run",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-fetch even if cached",
    )
    parser.add_argument(
        "--write-lookup",
        action="store_true",
        help="Merge crawl results into scripts/mips_lookup.json",
    )
    parser.add_argument(
        "--retailers",
        action="store_true",
        help="Also crawl Geizhals/Galaxus product pages from listings/price cache",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.75,
        help="Delay between manufacturer requests (seconds)",
    )
    args = parser.parse_args()

    if not args.helmets_json.exists():
        print(f"Helmet catalog not found: {args.helmets_json}", file=sys.stderr)
        sys.exit(1)

    helmets = load_helmets(args.helmets_json)
    brands = load_brands()
    cache = load_protection_cache()
    retailer_cache = load_retailer_protection_cache()
    price_cache = {}
    price_cache_path = SCRIPT_DIR / "price_cache.json"
    if price_cache_path.exists():
        price_cache = json.loads(price_cache_path.read_text(encoding="utf-8")).get("helmets", {})
    targets = helmets

    if args.helmet_ids:
        wanted = set(args.helmet_ids)
        targets = [helmet for helmet in helmets if helmet["id"] in wanted]
        missing = wanted - {helmet["id"] for helmet in targets}
        if missing:
            print(f"Unknown helmet id(s): {', '.join(sorted(missing))}", file=sys.stderr)
            sys.exit(1)
    elif args.brand:
        brand_lower = args.brand.lower()
        targets = [helmet for helmet in helmets if helmet["brand"].lower() == brand_lower]
    elif args.all_missing:
        targets = [
            helmet
            for helmet in helmets
            if helmet["id"] not in cache
            and not (helmet.get("features") or {}).get("rotational_protection")
            and brands.get(helmet["brand"].lower(), {}).get("search_url")
        ]

    if args.limit is not None:
        targets = targets[: args.limit]

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
                force=args.force,
                cache=cache,
                fetch_delay_s=args.delay,
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

            if args.retailers and not entry.get("mips_variant"):
                retailer_entry = crawl_helmet_retailer_protection(
                    helmet,
                    cache=retailer_cache,
                    price_cache_entry=price_cache.get(helmet["id"]),
                    fetch_delay_s=args.delay,
                    force=args.force,
                )
                retailer_label = (
                    retailer_entry.get("mips_label")
                    or retailer_entry.get("protection_tech")
                    or "none"
                )
                print(f"    retailer: {retailer_label}")
                if retailer_entry.get("mips_variant"):
                    detected += 1

    save_protection_cache(cache)
    if args.retailers:
        save_retailer_protection_cache(retailer_cache)
    print(f"\nCache: {PROTECTION_CACHE_PATH}")
    print(f"Detected protection on {detected}/{len(targets)} helmets ({errors} errors)")

    if args.write_lookup:
        updated = write_cache_to_mips_lookup(cache)
        print(f"Updated {updated} entries in mips_lookup.json")


if __name__ == "__main__":
    main()
