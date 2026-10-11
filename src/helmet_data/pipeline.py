"""Fetch or refresh all helmet data (Virginia Tech + optional extra lab ratings)."""

from .build import run_build
from .paths import EXTRA_RATINGS_PATH, HELMETS_JSON_PATH, PRICE_CACHE_PATH
from .steps.aero import run_fetch_aero
from .steps.extra_ratings import run_fetch_extra_ratings
from .steps.prices import run_fetch_prices


def _step(label: str) -> None:
    print(f"\n→ {label}\n", flush=True)


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

    _step("fetch-aero --fetch")
    run_fetch_aero(fetch=True)

    if not HELMETS_JSON_PATH.exists():
        _step("build --skip-extra-ratings")
        run_build(skip_extra_ratings=True)

    _step("fetch-ratings")
    run_fetch_extra_ratings()
    _step("build")
    run_build(**build_kwargs)
    if not skip_prices:
        apply_market_prices(quick=False, force=force_prices)
    print("\nDone. Start the site from web/ (see README).")
