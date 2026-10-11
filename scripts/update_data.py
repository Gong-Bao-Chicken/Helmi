#!/usr/bin/env python3
"""Fetch or refresh all helmet data (Virginia Tech + optional extra lab ratings)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
HELMETS_JSON = ROOT / "web" / "data" / "helmets.json"
PRICE_CACHE = SCRIPTS / "price_cache.json"


def run(cmd: list[str]) -> None:
    print(f"\n→ {' '.join(cmd)}\n")
    subprocess.run(cmd, check=True, cwd=ROOT)


def apply_market_prices(*, quick: bool, force: bool) -> None:
    cmd = [sys.executable, str(SCRIPTS / "fetch_listings.py")]
    if quick:
        if not PRICE_CACHE.exists():
            print("\nSkipping market prices (no cache). Run full ./update-data.sh once for live prices.")
            return
        cmd.append("--cache-only")
    else:
        if force:
            cmd.append("--force")
    run(cmd)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Refresh Virginia Tech only (reuse cached extra_ratings.json if present)",
    )
    parser.add_argument(
        "--fetch-manufacturer",
        action="store_true",
        help="Also fetch manufacturer search pages (slow)",
    )
    parser.add_argument(
        "--skip-prices",
        action="store_true",
        help="Do not fetch or apply shop prices",
    )
    parser.add_argument(
        "--force-prices",
        action="store_true",
        help="Ignore shop price cache and refetch all listings",
    )
    args = parser.parse_args()

    py = sys.executable
    fetch = [py, str(SCRIPTS / "fetch_helmets.py")]
    if args.fetch_manufacturer:
        fetch.append("--fetch-manufacturer")
    if args.quick:
        fetch.append("--verify-styles-cache-only")
        fetch.append("--manufacturer-protection-cache-only")
        fetch.append("--retailer-protection-cache-only")
    else:
        fetch.append("--verify-styles")

    if args.quick:
        if not (SCRIPTS / "extra_ratings.json").exists():
            fetch.append("--skip-extra-ratings")
        run(fetch)
        if not args.skip_prices:
            apply_market_prices(quick=True, force=False)
        print("\nDone. Start the site: ./serve.sh")
        return

    if not args.quick:
        run([py, str(SCRIPTS / "fetch_aero_ratings.py"), "--fetch"])

    if not HELMETS_JSON.exists():
        run([py, str(SCRIPTS / "fetch_helmets.py"), "--skip-extra-ratings"])

    run([py, str(SCRIPTS / "fetch_extra_ratings.py")])
    run(fetch)
    if not args.skip_prices:
        apply_market_prices(quick=False, force=args.force_prices)
    print("\nDone. Start the site: ./serve.sh")


if __name__ == "__main__":
    main()
