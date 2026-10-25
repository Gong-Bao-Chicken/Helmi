"""`helmet-data` command-line entry point."""

import argparse
from collections.abc import Sequence
from pathlib import Path

from . import paths
from .build import run_build
from .pipeline import run_update
from .steps.aero import run_fetch_aero
from .steps.extra_ratings import ALL_SOURCES, run_fetch_extra_ratings
from .steps.prices import DEFAULT_WORKERS as DEFAULT_PRICE_WORKERS
from .steps.prices import run_fetch_prices
from .steps.protection import run_fetch_protection


def _cmd_update(args: argparse.Namespace) -> None:
    run_update(
        quick=args.quick,
        fetch_manufacturer=args.fetch_manufacturer,
        skip_prices=args.skip_prices,
        force_prices=args.force_prices,
    )


def _cmd_build(args: argparse.Namespace) -> None:
    run_build(
        output=args.output,
        fetch_manufacturer=args.fetch_manufacturer,
        fetch_extra_ratings=args.fetch_extra_ratings,
        skip_extra_ratings=args.skip_extra_ratings,
        verify_styles=args.verify_styles,
        verify_styles_cache_only=args.verify_styles_cache_only,
        crawl_manufacturer_protection=args.crawl_manufacturer_protection,
        manufacturer_protection_cache_only=args.manufacturer_protection_cache_only,
        crawl_retailer_protection=args.crawl_retailer_protection,
        retailer_protection_cache_only=args.retailer_protection_cache_only,
    )


def _cmd_fetch_ratings(args: argparse.Namespace) -> None:
    run_fetch_extra_ratings(
        helmets_path=args.helmets,
        output=args.output,
        raw_output=args.raw_output,
        sources=args.sources,
        certimoov_limit=args.certimoov_limit,
        folksam_year=args.folksam_year,
        nsw_year=args.nsw_year,
        delay=args.delay,
    )


def _cmd_fetch_prices(args: argparse.Namespace) -> None:
    run_fetch_prices(
        input_path=args.input,
        cache_path=args.cache,
        all_helmets=args.all_helmets,
        limit=args.limit,
        force=args.force,
        cache_only=args.cache_only,
        workers=args.workers,
    )


def _cmd_fetch_aero(args: argparse.Namespace) -> None:
    run_fetch_aero(output=args.output, helmets_path=args.helmets, fetch=args.fetch)


def _cmd_fetch_protection(args: argparse.Namespace) -> None:
    run_fetch_protection(
        helmets_path=args.helmets_json,
        helmet_ids=args.helmet_ids,
        brand=args.brand,
        all_missing=args.all_missing,
        limit=args.limit,
        force=args.force,
        write_lookup=args.write_lookup,
        retailers=args.retailers,
        delay=args.delay,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="helmet-data", description="Helmi data pipeline.")
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    # update (formerly scripts/update_data.py)
    p = sub.add_parser(
        "update",
        help="Fetch or refresh all helmet data (VT + extra lab ratings + prices)",
        description="Fetch or refresh all helmet data (Virginia Tech + optional extra lab ratings).",
    )
    p.add_argument(
        "--quick",
        action="store_true",
        help="Refresh Virginia Tech only (reuse cached extra_ratings.json if present)",
    )
    p.add_argument(
        "--fetch-manufacturer",
        action="store_true",
        help="Also fetch manufacturer search pages (slow)",
    )
    p.add_argument("--skip-prices", action="store_true", help="Do not fetch or apply shop prices")
    p.add_argument(
        "--force-prices",
        action="store_true",
        help="Ignore shop price cache and refetch all listings",
    )
    p.set_defaults(func=_cmd_update)

    # build (formerly scripts/fetch_helmets.py)
    p = sub.add_parser(
        "build",
        aliases=["fetch-vt"],
        help="Fetch Virginia Tech ratings and assemble helmets.json from cached enrichments",
        description="Fetch Virginia Tech bicycle helmet ratings and enrich with manufacturer metadata.",
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=paths.HELMETS_JSON_PATH,
        help="Output JSON path (default: web/public/data/helmets.json)",
    )
    p.add_argument(
        "--fetch-manufacturer",
        action="store_true",
        help="Fetch manufacturer search pages for Open Graph metadata (slow)",
    )
    p.add_argument(
        "--fetch-extra-ratings",
        action="store_true",
        help="Crawl CERTIMOOV/Folksam/NSW and refresh data/cache/extra_ratings.json before merge",
    )
    p.add_argument(
        "--skip-extra-ratings",
        action="store_true",
        help="Do not merge data/cache/extra_ratings.json",
    )
    p.add_argument(
        "--verify-styles",
        action="store_true",
        help="Fetch manufacturer pages to verify helmet styles (slow; uses cache)",
    )
    p.add_argument(
        "--verify-styles-cache-only",
        action="store_true",
        help="Apply cached manufacturer style verifications only",
    )
    p.add_argument(
        "--crawl-manufacturer-protection",
        action="store_true",
        help="Crawl manufacturer sites for MIPS/protection tech (slow; uses cache)",
    )
    p.add_argument(
        "--manufacturer-protection-cache-only",
        action="store_true",
        help="Apply cached manufacturer protection data only",
    )
    p.add_argument(
        "--crawl-retailer-protection",
        action="store_true",
        help="Crawl Geizhals/Galaxus product pages for MIPS/protection tech (uses cache)",
    )
    p.add_argument(
        "--retailer-protection-cache-only",
        action="store_true",
        help="Apply cached retailer product-page protection data only",
    )
    p.set_defaults(func=_cmd_build)

    # fetch-ratings (formerly scripts/fetch_extra_ratings.py)
    p = sub.add_parser(
        "fetch-ratings",
        help="Crawl CERTIMOOV, Folksam and NSW Helmet STAR ratings",
        description="Crawl real helmet ratings from CERTIMOOV, Folksam, and NSW Helmet STAR.",
    )
    p.add_argument(
        "--helmets",
        type=Path,
        default=paths.HELMETS_JSON_PATH,
        help="VT helmets.json used for matching (default: web/public/data/helmets.json)",
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=paths.EXTRA_RATINGS_PATH,
        help="Merged match output for `helmet-data build`",
    )
    p.add_argument(
        "--raw-output",
        type=Path,
        default=paths.EXTRA_RATINGS_RAW_PATH,
        help="Optional full crawl + unmatched report",
    )
    p.add_argument("--sources", nargs="+", choices=list(ALL_SOURCES), default=list(ALL_SOURCES))
    p.add_argument("--certimoov-limit", type=int, default=None)
    p.add_argument("--folksam-year", type=int, default=2025)
    p.add_argument("--nsw-year", type=int, default=2025)
    p.add_argument("--delay", type=float, default=0.25)
    p.set_defaults(func=_cmd_fetch_ratings)

    # fetch-prices (formerly scripts/fetch_listings.py)
    p = sub.add_parser(
        "fetch-prices",
        help="Fetch live shop prices and merge market prices into helmets.json",
        description="Fetch live shop prices and merge median market prices into helmets.json.",
    )
    p.add_argument("-i", "--input", type=Path, default=paths.HELMETS_JSON_PATH)
    p.add_argument("--cache", type=Path, default=paths.PRICE_CACHE_PATH)
    p.add_argument("--all-helmets", action="store_true", help="Include non-European-market helmets")
    p.add_argument("--limit", type=int, help="Only fetch prices for the first N helmets")
    p.add_argument("--force", action="store_true", help="Refetch even if today's snapshot exists")
    p.add_argument(
        "--cache-only",
        action="store_true",
        help="Apply cached median prices only (no shop requests)",
    )
    p.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_PRICE_WORKERS,
        help="Helmets fetched at the same time; each shop stays paced per host (default %(default)s)",
    )
    p.set_defaults(func=_cmd_fetch_prices)

    # fetch-aero (formerly scripts/fetch_aero_ratings.py)
    p = sub.add_parser(
        "fetch-aero",
        help="Refresh Cyclingnews Labs aero data and report helmet coverage",
        description="Fetch Cyclingnews Labs aero helmet data and refresh data/reference/aero_ratings.json.",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=paths.AERO_RATINGS_PATH,
        help="Path to aero_ratings.json",
    )
    p.add_argument(
        "--helmets",
        type=Path,
        default=paths.HELMETS_JSON_PATH,
        help="Helmets JSON for match report",
    )
    p.add_argument(
        "--fetch",
        action="store_true",
        help="Fetch Cyclingnews Labs pages and refresh numeric fields",
    )
    p.add_argument(
        "--report-only",
        action="store_true",
        help="Only report how curated data maps onto helmets.json (default without --fetch)",
    )
    p.set_defaults(func=_cmd_fetch_aero)

    # fetch-protection (formerly scripts/fetch_manufacturer_protection.py)
    p = sub.add_parser(
        "fetch-protection",
        help="Crawl manufacturer/retailer sites for MIPS and protection tech",
        description="Crawl manufacturer websites for helmet protection technology.",
    )
    p.add_argument(
        "--helmets-json",
        type=Path,
        default=paths.HELMETS_JSON_PATH,
        help="Helmet catalog JSON (default: web/public/data/helmets.json)",
    )
    p.add_argument(
        "--helmet",
        action="append",
        dest="helmet_ids",
        metavar="ID",
        help="Crawl specific helmet id(s), e.g. fox-racing-speedframe-rs",
    )
    p.add_argument("--brand", help="Crawl all helmets from this brand (case-insensitive)")
    p.add_argument(
        "--all-missing",
        action="store_true",
        help="Crawl helmets with no MIPS in model name and no cache entry",
    )
    p.add_argument("--limit", type=int, default=None, help="Max helmets to crawl in one run")
    p.add_argument("--force", action="store_true", help="Re-fetch even if cached")
    p.add_argument(
        "--write-lookup",
        action="store_true",
        help="Merge crawl results into data/reference/mips_lookup.json",
    )
    p.add_argument(
        "--retailers",
        action="store_true",
        help="Also crawl Geizhals/Galaxus product pages from listings/price cache",
    )
    p.add_argument(
        "--delay",
        type=float,
        default=0.75,
        help="Delay between manufacturer requests (seconds)",
    )
    p.set_defaults(func=_cmd_fetch_protection)

    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
