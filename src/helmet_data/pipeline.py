"""Fetch or refresh all helmet data (Virginia Tech + optional extra lab ratings)."""

import traceback

from .build import run_build
from .paths import EXTRA_RATINGS_PATH, HELMETS_JSON_PATH, PRICE_CACHE_PATH
from .steps.aero import run_fetch_aero
from .steps.extra_ratings import run_fetch_extra_ratings
from .steps.prices import run_fetch_prices


def _step(label: str) -> None:
    print(f"\n→ {label}\n", flush=True)


def _run_step(label: str, fn, failures: list[str], **kwargs) -> bool:
    """Run one pipeline step; a failure is logged and the update continues."""
    _step(label)
    try:
        fn(**kwargs)
    except (Exception, SystemExit) as exc:  # noqa: BLE001 - keep the update going
        message = f"{label}: {type(exc).__name__}: {exc}"
        print(f"\n  WARNING: step failed - {message}\n  Continuing with cached data.\n", flush=True)
        traceback.print_exc()
        failures.append(message)
        return False
    return True


def apply_market_prices(*, quick: bool, force: bool) -> None:
    if quick:
        if not PRICE_CACHE_PATH.exists():
            print("\nSkipping market prices (no cache). Run `helmet-data update` once for live prices.")
            return
        _step("fetch-prices --cache-only")
        run_fetch_prices(cache_only=True)
    else:
        _step("fetch-prices" + (" --force" if force else ""))
        run_fetch_prices(force=force)


def run_update(
    *,
    quick: bool = False,
    fetch_manufacturer: bool = False,
    skip_prices: bool = False,
    force_prices: bool = False,
) -> None:
    build_kwargs: dict[str, bool] = {"fetch_manufacturer": fetch_manufacturer}
    if quick:
        build_kwargs |= {
            "verify_styles_cache_only": True,
            "manufacturer_protection_cache_only": True,
            "retailer_protection_cache_only": True,
        }
    else:
        build_kwargs["verify_styles"] = True

    if quick:
        if not EXTRA_RATINGS_PATH.exists():
            build_kwargs["skip_extra_ratings"] = True
        _step("build")
        run_build(**build_kwargs)
        if not skip_prices:
            apply_market_prices(quick=True, force=False)
        print("\nDone. Start the site from web/ (see README).")
        return

    failures: list[str] = []
    _run_step("fetch-aero --fetch", run_fetch_aero, failures, fetch=True)

    if not HELMETS_JSON_PATH.exists():
        _run_step("build --skip-extra-ratings", run_build, failures, skip_extra_ratings=True)

    _run_step("fetch-ratings", run_fetch_extra_ratings, failures)
    built = _run_step("build", run_build, failures, **build_kwargs)
    if not skip_prices and HELMETS_JSON_PATH.exists():
        label = "fetch-prices" + (" --force" if force_prices else "")
        _run_step(label, run_fetch_prices, failures, force=force_prices)

    if failures:
        print("\nUpdate finished with failed steps (cached data was used):")
        for message in failures:
            print(f"  - {message}")
    if not built:
        raise SystemExit("build failed - helmets.json was not regenerated")
    print("\nDone. Start the site from web/ (see README).")
