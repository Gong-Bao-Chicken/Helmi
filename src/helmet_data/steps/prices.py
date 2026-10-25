"""Fetch live shop prices and merge median market prices into helmets.json."""

import io
import json
import math
import re
import sys
import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager, redirect_stdout
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO

import httpx

from ..build import market_listings
from ..crawlers.price_history import (
    aggregate_price,
    append_history,
    fetch_is_due,
    prune_history,
)
from ..crawlers.price_sources import (
    MARKET_CURRENCY,
    PREFERRED_SOURCES,
    PriceOffer,
    build_search_context,
    dedupe_offers,
    make_price_client,
    parse_geizhals_phist_html,
    score_offer,
    search_http_sources,
    sibling_exclude_tokens,
)
from ..crawlers.stealth_fetch import site_report, site_stats, stealth_get
from ..enrich.protection_tech import apply_protection_to_helmet, load_mips_lookup
from ..enrich.ratings import value_ratio_from_ratings
from ..enrich.retailer_protection import (
    crawl_helmet_retailer_protection,
    load_retailer_protection_cache,
    merge_retailer_cache_into_lookup,
    save_retailer_protection_cache,
)
from ..paths import HELMETS_JSON_PATH, PRICE_CACHE_PATH

DEFAULT_INPUT = HELMETS_JSON_PATH
DEFAULT_CACHE = PRICE_CACHE_PATH
# Lowest accept_offer threshold used by any shop parser.
MIN_CACHED_MATCH_SCORE = 0.5
FRANKFURTER_URL = "https://api.frankfurter.app/latest?from=USD&to=EUR,CHF"
# Last resort when the rate service is down and no earlier rates are cached.
DEFAULT_RATES = {"EUR": 0.92, "CHF": 0.88}


def fetch_exchange_rates(client: httpx.Client) -> dict[str, Any] | None:
    """Today's USD -> EUR/CHF rates (ECB reference rates via Frankfurter), or None."""
    try:
        response = client.get(FRANKFURTER_URL, timeout=15.0)
        response.raise_for_status()
        body = response.json()
        rates = body["rates"]
        return {"EUR": float(rates["EUR"]), "CHF": float(rates["CHF"]), "date": body.get("date")}
    except (httpx.HTTPError, KeyError, TypeError, ValueError):
        return None


def resolve_exchange_rates(client: httpx.Client, cached: dict[str, Any] | None) -> dict[str, Any]:
    """Fresh rates if the service answers, else the last cached ones, else DEFAULT_RATES."""
    fresh = fetch_exchange_rates(client)
    if fresh:
        return {**fresh, "source": "frankfurter"}
    if cached and cached.get("EUR") and cached.get("CHF"):
        print("  warning: exchange rates unavailable; using the last cached rates", flush=True)
        return {**cached, "source": "cached"}
    print("  warning: exchange rates unavailable; using built-in defaults", flush=True)
    return {**DEFAULT_RATES, "date": None, "source": "default"}


def currency_to_usd(amount: float, currency: str, rates: dict[str, float]) -> float:
    rate = rates.get(currency)
    if not rate:
        return amount
    return amount / rate


def load_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 2, "helmets": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_cache(path: Path, cache: dict[str, Any]) -> None:
    cache["version"] = 2
    cache["saved_at"] = datetime.now(UTC).isoformat()
    path.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def offer_to_dict(offer: PriceOffer) -> dict[str, Any]:
    return {
        "source": offer.source,
        "title": offer.title,
        "price": offer.price,
        "currency": offer.currency,
        "url": offer.url,
        "rating": offer.rating,
        "review_count": offer.review_count,
        "available": offer.available,
        "match_score": round(offer.match_score, 3),
    }


def offer_from_dict(data: dict[str, Any]) -> PriceOffer:
    return PriceOffer(
        source=data["source"],
        title=data["title"],
        price=float(data["price"]),
        currency=data["currency"],
        url=data.get("url"),
        rating=data.get("rating"),
        review_count=data.get("review_count"),
        available=data.get("available", True),
        match_score=float(data.get("match_score", 0.0)),
    )


def listing_from_aggregate(
    aggregate: dict[str, Any],
    *,
    sources: list[PriceOffer],
    fetched_at: str,
) -> dict[str, Any]:
    representative: PriceOffer | None = aggregate.get("representative")
    return {
        "price": aggregate["amount"],
        "currency": aggregate["currency"],
        "rating": representative.rating if representative else None,
        "review_count": representative.review_count if representative else None,
        "url": representative.url if representative else None,
        "source": ", ".join(aggregate["sources"]),
        "sources": [offer_to_dict(item) for item in sources],
        "price_window": aggregate["window"],
        "price_sample_days": aggregate["sample_days"],
        "fetched_at": fetched_at,
    }


def history_from_geizhals_phist(
    samples: list[tuple[str, float]],
    template: PriceOffer,
) -> list[dict[str, Any]]:
    if not samples:
        return []
    history: list[dict[str, Any]] = []
    for day, price in samples[-30:]:
        offer = PriceOffer(
            source=template.source,
            title=template.title,
            price=price,
            currency=template.currency,
            url=template.url,
            available=True,
            match_score=template.match_score,
        )
        history.append(
            {
                "fetched_at": f"{day}T12:00:00+00:00",
                "offers": [offer_to_dict(offer)],
                "origin": "geizhals_phist",
            }
        )
    return history


# Plausibility bounds for shop offers (prices compared in USD after FX).
TEST_PRICE_RATIO_BOUNDS = (0.3, 2.5)  # offer vs price_at_test_usd
# CHF offer vs EUR offer for the same helmet. Swiss shops often charge up to ~2x the German
# price; wrong-product matches are typically 2.5x off or more.
CH_DE_RATIO_BOUNDS = (0.7, 2.0)
# Two prices within this factor of each other count as agreeing.
AGREEMENT_RATIO = 1.35


def source_company(source: str) -> str:
    """The company behind a price source: ``idealo_at`` and ``idealo`` are both Idealo."""
    return source.split("_")[0]


def price_outlier_check(
    offers: list[PriceOffer],
    *,
    test_usd: float | None,
    rates: dict[str, float],
):
    """Return ``reason(offer) -> str | None`` flagging implausible offers.

    1. Offers far from the VT test price (< 0.3x or > 2.5x) are wrong-product/bundle matches.
    2. A price two different companies agree on (within 1.35x) is a real market price; offers
       in that currency far below it are accessory or wrong-model matches.
    3. If the CHF and EUR prices disagree beyond 0.7-2.0x after FX, the side further from
       the test price (CHF when there is no test price) is treated as the mismatch -
       unless two companies agree on it.
    """
    low, high = TEST_PRICE_RATIO_BOUNDS

    def usd(offer: PriceOffer) -> float:
        return currency_to_usd(offer.price, offer.currency, rates)

    def test_reason(offer: PriceOffer) -> str | None:
        if not test_usd:
            return None
        ratio = usd(offer) / test_usd
        if ratio < low or ratio > high:
            return f"{ratio:.2f}x test price"
        return None

    sane = [offer for offer in offers if test_reason(offer) is None]

    def agreed_price(currency: str) -> float | None:
        """Lowest USD price in this currency that another company's price is within 1.35x of.

        idealo.de and idealo.at (or geizhals.de and .at) usually return the same product
        match, so they count as one company: their agreement says nothing about whether it is
        right. Any pair counts, so one wrong cheap match can't hide two shops that agree.
        """
        priced = sorted((usd(o), source_company(o.source)) for o in sane if o.currency == currency)
        for i, (price, company) in enumerate(priced):
            for other_price, other_company in priced[i + 1 :]:
                if other_price / price > AGREEMENT_RATIO:
                    break
                if other_company != company:
                    return price
        return None

    agreed = {currency: agreed_price(currency) for currency in ("EUR", "CHF")}

    def below_agreed(offer: PriceOffer) -> bool:
        price = agreed.get(offer.currency)
        return price is not None and usd(offer) * AGREEMENT_RATIO < price

    refs: dict[str, float] = {}
    for currency in ("EUR", "CHF"):
        prices = [usd(o) for o in sane if o.currency == currency and not below_agreed(o)]
        if prices:
            refs[currency] = agreed[currency] or min(prices)

    suspect_currency: str | None = None
    if "EUR" in refs and "CHF" in refs:
        ratio = refs["CHF"] / refs["EUR"]
        if not CH_DE_RATIO_BOUNDS[0] <= ratio <= CH_DE_RATIO_BOUNDS[1]:
            suspect_currency = "CHF"
            if test_usd:
                dev = {cur: abs(math.log(refs[cur] / test_usd)) for cur in refs}
                suspect_currency = max(dev, key=dev.get)
            if agreed[suspect_currency] is not None:
                # Two shops agreeing is a real market price (e.g. a German clearance price
                # far below Swiss list price), not a wrong-product match.
                suspect_currency = None
    other = {"CHF": "EUR", "EUR": "CHF"}

    def reason(offer: PriceOffer) -> str | None:
        found = test_reason(offer)
        if found:
            return found
        if below_agreed(offer):
            return "far below the price two shops agree on"
        if suspect_currency and offer.currency == suspect_currency:
            ref = refs[other[suspect_currency]]
            ratio = usd(offer) / ref if suspect_currency == "CHF" else ref / usd(offer)
            if not CH_DE_RATIO_BOUNDS[0] <= ratio <= CH_DE_RATIO_BOUNDS[1]:
                return f"CH/DE ratio {ratio:.2f}"
        return None

    return reason


def drop_price_outliers(
    offers: list[PriceOffer],
    history: list[dict[str, Any]],
    *,
    test_usd: float | None,
    rates: dict[str, float],
) -> tuple[list[PriceOffer], list[dict[str, Any]], list[dict[str, Any]]]:
    """Remove implausible offers from the latest offers and the price history."""
    reason = price_outlier_check(offers, test_usd=test_usd, rates=rates)
    dropped: list[dict[str, Any]] = []
    kept: list[PriceOffer] = []
    for offer in offers:
        why = reason(offer)
        if why:
            dropped.append({**offer_to_dict(offer), "reason": why})
        else:
            kept.append(offer)
    clean_history: list[dict[str, Any]] = []
    for entry in history:
        entry_offers = [item for item in entry.get("offers", []) if reason(offer_from_dict(item)) is None]
        if entry_offers:
            clean_history.append({**entry, "offers": entry_offers})
    return kept, clean_history, dropped


def apply_market_price(
    helmet: dict[str, Any],
    *,
    offers: list[PriceOffer],
    history: list[dict[str, Any]],
    rates: dict[str, float],
    fetched_at: str,
    dropped: list[dict[str, Any]] | None = None,
) -> bool:
    listings = helmet.setdefault("listings", {})
    changed = False
    offers, history, outliers = drop_price_outliers(
        offers, history, test_usd=helmet.get("price_at_test_usd"), rates=rates
    )
    if outliers and dropped is not None:
        dropped.extend(outliers)

    # Each country only gets a price from its own shops. A country with none stays empty;
    # copying or converting another country's price would fake a price comparison.
    aggregates: dict[str, dict[str, Any]] = {}
    for market, currency in MARKET_CURRENCY.items():
        agg = aggregate_price(
            history, offers, currency=currency, market=market, offer_from_dict=offer_from_dict
        )
        if agg:
            aggregates[market] = agg
            listings[market] = listing_from_aggregate(agg, sources=agg["offers"], fetched_at=fetched_at)
            changed = True
        elif listings.get(market, {}).get("price") is not None:
            listings[market] = market_listings()[market]
            changed = True

    test_usd = helmet.get("price_at_test_usd")
    primary = aggregates.get("de") or aggregates.get("at") or aggregates.get("ch")
    if not changed or test_usd is None or primary is None:
        helmet.pop("current_price", None)
        helmet.pop("price_comparison_usd", None)
        helmet.pop("price_comparison_label", None)
        return changed

    market_usd = currency_to_usd(primary["amount"], primary["currency"], rates)
    source_names = primary["sources"]
    window_label = primary["window"].replace("_", " ")

    helmet["current_price"] = {
        "amount": primary["amount"],
        "currency": primary["currency"],
        "usd_equiv": round(market_usd, 2),
        "sources": source_names,
        "source_details": [offer_to_dict(offer) for offer in primary["offers"]],
        "price_window": primary["window"],
        "price_sample_days": primary["sample_days"],
        "sample_prices": primary["sample_prices"],
        "fetched_at": fetched_at,
        "better_than_test": market_usd < test_usd,
    }

    helmet["price_comparison_usd"] = round(market_usd, 2)
    helmet["price_comparison_label"] = (
        f"{primary['amount']:.2f} {primary['currency']} ({window_label}; {', '.join(source_names)})"
    )
    helmet["value_ratio"] = value_ratio_from_ratings(helmet.get("ratings", {}), market_usd)

    return changed


def geizhals_phist_samples(product_url: str) -> list[tuple[str, float]]:
    match = re.search(r"-a(\d+)\.html", product_url)
    if not match:
        return []
    product_id = match.group(1)
    status, html = stealth_get(f"https://geizhals.de/?phist={product_id}")
    if status != 200 or not html:
        return []
    return parse_geizhals_phist_html(html)


def search_shops(
    client: httpx.Client,
    helmet: dict[str, Any],
    *,
    exclude_tokens: frozenset[str] = frozenset(),
    failures: dict[str, str] | None = None,
) -> list[PriceOffer]:
    ctx = build_search_context(helmet["brand"], helmet["model"], exclude_tokens=exclude_tokens)
    return dedupe_offers(search_http_sources(client, ctx, failures=failures))


def geizhals_history(
    offers: list[PriceOffer], failures: dict[str, str] | None = None
) -> list[dict[str, Any]]:
    """Daily prices from the matched Geizhals product's price-history page (optional extra)."""
    geizhals_offer = next((offer for offer in offers if offer.source == "geizhals" and offer.url), None)
    if not geizhals_offer:
        return []
    try:
        return history_from_geizhals_phist(geizhals_phist_samples(geizhals_offer.url), geizhals_offer)
    except Exception as exc:  # noqa: BLE001 - history is optional
        print(f"  warning: geizhals price history failed ({type(exc).__name__}: {exc})", flush=True)
        if failures is not None:
            failures["geizhals_phist"] = f"{type(exc).__name__}: {exc}"[:300]
        return []


def search_all_sources(
    client: httpx.Client,
    helmet: dict[str, Any],
    *,
    exclude_tokens: frozenset[str] = frozenset(),
    failures: dict[str, str] | None = None,
) -> tuple[list[PriceOffer], list[dict[str, Any]]]:
    offers = search_shops(client, helmet, exclude_tokens=exclude_tokens, failures=failures)
    return offers, geizhals_history(offers, failures)


def carry_over_failed_sources(
    offers: list[PriceOffer],
    cached: dict[str, Any] | None,
    failed_sources: set[str],
) -> list[PriceOffer]:
    """Keep the previously cached offer of every shop whose search just failed."""
    if not cached or not failed_sources:
        return offers
    present = {offer.source for offer in offers}
    carried = [
        offer_from_dict(item)
        for item in cached.get("offers", [])
        if item.get("source") in failed_sources and item.get("source") not in present
    ]
    return offers + carried


def rebuild_from_cache_entry(
    helmet: dict[str, Any],
    cached: dict[str, Any],
    *,
    rates: dict[str, float],
    retailer_cache: dict[str, dict[str, Any]] | None = None,
    dropped: list[dict[str, Any]] | None = None,
    exclude_tokens: frozenset[str] = frozenset(),
) -> None:
    history = prune_history(cached.get("history", []))
    offers = [offer_from_dict(item) for item in cached.get("offers", [])]
    # Re-score cached titles with the current matching rules (offers cached by older,
    # looser matching - e.g. "POC Cytal Carbon" for the Cytal - must not keep pricing a helmet).
    ctx = build_search_context(helmet["brand"], helmet["model"], exclude_tokens=exclude_tokens)

    def still_matches(item: dict[str, Any]) -> bool:
        return score_offer(ctx, item.get("title", "")) >= MIN_CACHED_MATCH_SCORE

    offers = [offer for offer in offers if still_matches(offer_to_dict(offer))]
    history = [
        {**entry, "offers": [item for item in entry.get("offers", []) if still_matches(item)]}
        for entry in history
    ]
    apply_market_price(
        helmet,
        offers=offers,
        history=history,
        rates=rates,
        fetched_at=cached.get("fetched_at", datetime.now(UTC).isoformat()),
        dropped=dropped,
    )
    if retailer_cache:
        lookup = merge_retailer_cache_into_lookup(load_mips_lookup(), retailer_cache)
        apply_protection_to_helmet(
            helmet,
            lookup=lookup,
            extra_texts=[offer.title for offer in offers],
        )


# Helmets fetched at the same time. Shops are still paced per host (stealth_fetch), so more
# workers mostly keep every shop busy rather than raising the request rate to any one of them.
DEFAULT_WORKERS = 8


class _HelmetOutput(io.TextIOBase):
    """stdout that buffers each worker thread's lines, so a helmet's log prints as one block,
    numbered in completion order."""

    def __init__(self, real: TextIO, total: int) -> None:
        self.real = real
        self.total = total
        self.done = 0
        self.local = threading.local()
        self.lock = threading.Lock()

    def write(self, text: str) -> int:
        buffer = getattr(self.local, "buffer", None)
        if buffer is None:
            with self.lock:
                return self.real.write(text)
        buffer.append(text)
        return len(text)

    def flush(self) -> None:
        if getattr(self.local, "buffer", None) is None:
            self.real.flush()

    @contextmanager
    def block(self, header: str) -> Iterator[None]:
        self.local.buffer = []
        try:
            yield
        finally:
            text = "".join(self.local.buffer)
            self.local.buffer = None
            with self.lock:
                self.done += 1
                self.real.write(f"[{self.done}/{self.total}] {header}…\n{text}")
                self.real.flush()


@dataclass
class _Run:
    """State shared by the price workers; every read-modify-write goes through ``lock``."""

    cache: dict[str, Any]
    cache_path: Path
    retailer_cache: dict[str, dict[str, Any]]
    source_errors: dict[str, dict[str, Any]]
    outliers: dict[str, list[dict[str, Any]]]
    lock: threading.Lock = field(default_factory=threading.Lock)

    def record_error(self, source: str, message: str) -> None:
        with self.lock:
            _record_error(self.source_errors, source, message)


def update_helmets(
    helmets: list[dict[str, Any]],
    *,
    european_only: bool,
    limit: int | None,
    force: bool,
    cache_only: bool,
    cache_path: Path,
    source_errors: dict[str, dict[str, Any]] | None = None,
    outliers: dict[str, list[dict[str, Any]]] | None = None,
    exchange_rates: dict[str, Any] | None = None,
    workers: int = DEFAULT_WORKERS,
) -> dict[str, int]:
    """Refresh shop prices, ``workers`` helmets at a time. ``source_errors``/``outliers``/
    ``exchange_rates`` collect per-shop failures, dropped implausible offers and the rates
    used, for the output meta."""
    run = _Run(
        cache=load_cache(cache_path),
        cache_path=cache_path,
        retailer_cache=load_retailer_protection_cache(),
        source_errors=source_errors if source_errors is not None else {},
        outliers=outliers if outliers is not None else {},
    )
    stats = {"checked": 0, "priced": 0, "better": 0, "cached": 0, "skipped": 0}

    candidates = [
        helmet
        for helmet in helmets
        if (not european_only or helmet.get("european_market"))
        and helmet.get("price_at_test_usd") is not None
    ]
    if limit is not None:
        candidates = candidates[:limit]

    def count_price(helmet: dict[str, Any]) -> None:
        stats["priced"] += 1
        if helmet.get("current_price", {}).get("better_than_test"):
            stats["better"] += 1

    with make_price_client() as client:
        rates = resolve_exchange_rates(client, run.cache.get("exchange_rates"))
        run.cache["exchange_rates"] = rates
        if exchange_rates is not None:
            exchange_rates.update(rates)

        due: list[dict[str, Any]] = []
        for helmet in candidates:
            cached = run.cache.get("helmets", {}).get(helmet["id"])
            if cache_only and not cached:
                stats["skipped"] += 1
            elif cache_only or not fetch_is_due(cached, force=force):
                if cached:
                    dropped: list[dict[str, Any]] = []
                    rebuild_from_cache_entry(
                        helmet,
                        cached,
                        rates=rates,
                        retailer_cache=run.retailer_cache,
                        dropped=dropped,
                        exclude_tokens=sibling_exclude_tokens(helmet, helmets),
                    )
                    if dropped:
                        run.outliers[helmet["id"]] = dropped
                    stats["cached"] += 1
                    stats["checked"] += 1
                    if helmet.get("current_price"):
                        count_price(helmet)
            else:
                due.append(helmet)

        if due:
            print(f"Fetching {len(due)} helmets, {min(workers, len(due))} at a time…", flush=True)
            output = _HelmetOutput(sys.stdout, len(due))

            def fetch_one(helmet: dict[str, Any]) -> bool:
                with output.block(f"{helmet['brand']} {helmet['model']}"):
                    return _fetch_helmet(
                        helmet,
                        cached=run.cache.get("helmets", {}).get(helmet["id"]),
                        client=client,
                        rates=rates,
                        exclude_tokens=sibling_exclude_tokens(helmet, helmets),
                        run=run,
                    )

            with redirect_stdout(output), ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
                futures = {pool.submit(fetch_one, helmet): helmet for helmet in due}
                for future in as_completed(futures):
                    stats["checked"] += 1
                    if future.result():
                        count_price(futures[future])
                    else:
                        stats["skipped"] += 1

    with run.lock:
        save_cache(cache_path, run.cache)
    return stats


def _record_error(source_errors: dict[str, dict[str, Any]], source: str, message: str) -> None:
    info = source_errors.setdefault(source, {"count": 0, "last_error": None})
    info["count"] += 1
    info["last_error"] = message[:300]


def _has_listing(helmet: dict[str, Any]) -> bool:
    return any(
        isinstance(listing, dict) and listing.get("price") is not None
        for listing in helmet.get("listings", {}).values()
    )


def _fetch_helmet(
    helmet: dict[str, Any],
    *,
    cached: dict[str, Any] | None,
    client: httpx.Client,
    rates: dict[str, float],
    exclude_tokens: frozenset[str],
    run: _Run,
) -> bool:
    """One helmet, never raising: a failure falls back to its cached prices."""
    try:
        priced = _refresh_helmet_price(
            helmet, cached=cached, client=client, rates=rates, exclude_tokens=exclude_tokens, run=run
        )
    except Exception as exc:  # noqa: BLE001 - one helmet must not abort the run
        print(
            f"  WARNING: price refresh failed ({type(exc).__name__}: {exc}); using cached prices", flush=True
        )
        run.record_error("helmet_refresh", f"{helmet['id']}: {type(exc).__name__}: {exc}")
        priced = False
        if cached:
            try:
                rebuild_from_cache_entry(helmet, cached, rates=rates)
                priced = bool(helmet.get("current_price") or _has_listing(helmet))
            except Exception as inner:  # noqa: BLE001
                print(f"  cache rebuild failed too: {inner}", flush=True)
    return priced


def _crawl_protection(helmet: dict[str, Any], offers: list[PriceOffer], run: _Run) -> None:
    """Read MIPS & co. off the retailer product pages (only for helmets not crawled before)."""
    helmet_id = helmet["id"]
    with run.lock:
        own = {helmet_id: run.retailer_cache[helmet_id]} if helmet_id in run.retailer_cache else {}
    crawl_helmet_retailer_protection(
        helmet, cache=own, price_cache_entry={"offers": [offer_to_dict(offer) for offer in offers]}
    )
    with run.lock:
        run.retailer_cache.update(own)
        save_retailer_protection_cache(run.retailer_cache)
        lookup = merge_retailer_cache_into_lookup(load_mips_lookup(), run.retailer_cache)
    apply_protection_to_helmet(helmet, lookup=lookup, extra_texts=[offer.title for offer in offers])


def _refresh_helmet_price(
    helmet: dict[str, Any],
    *,
    cached: dict[str, Any] | None,
    client: httpx.Client,
    rates: dict[str, float],
    exclude_tokens: frozenset[str],
    run: _Run,
) -> bool:
    helmet_id = helmet["id"]
    failures: dict[str, str] = {}
    offers = search_shops(client, helmet, exclude_tokens=exclude_tokens, failures=failures)

    # Price history and the product-page protection check both start from the offers and hit
    # different pages, so run them side by side.
    with ThreadPoolExecutor(max_workers=2) as pool:
        history_job = pool.submit(geizhals_history, offers, failures)
        protection_job = pool.submit(_crawl_protection, helmet, offers, run) if offers else None
        external_history = history_job.result()
        if protection_job is not None:
            try:
                protection_job.result()
            except Exception as exc:  # noqa: BLE001 - protection crawl is a side quest
                print(
                    f"  warning: retailer protection crawl failed ({type(exc).__name__}: {exc})", flush=True
                )
                run.record_error("retailer_protection", f"{type(exc).__name__}: {exc}")

    for source, message in failures.items():
        run.record_error(source, message)
    offers = carry_over_failed_sources(offers, cached, set(failures))
    fetched_at = datetime.now(UTC).isoformat()

    prior_history = prune_history(cached.get("history", []) if cached else [])
    history = append_history(
        {"history": prior_history + external_history},
        offers=offers,
        fetched_at=fetched_at,
        offer_to_dict=offer_to_dict,
    )

    with run.lock:
        run.cache.setdefault("helmets", {})[helmet_id] = {
            "fetched_at": fetched_at,
            "offers": [offer_to_dict(offer) for offer in offers],
            "history": history,
        }
        save_cache(run.cache_path, run.cache)

    dropped: list[dict[str, Any]] = []
    priced = apply_market_price(
        helmet,
        offers=offers,
        history=history,
        rates=rates,
        fetched_at=fetched_at,
        dropped=dropped,
    )
    if dropped:
        with run.lock:
            run.outliers[helmet_id] = dropped
        for item in dropped:
            print(
                f"  dropped suspect offer: {item['source']} {item['price']} "
                f"{item['currency']} ({item['reason']})",
                flush=True,
            )
    if priced:
        current = helmet.get("current_price", {})
        if current.get("better_than_test"):
            print(f"  better price: {helmet.get('price_comparison_label', '')}", flush=True)
        elif offers:
            print(
                f"  {current.get('amount', '?')} {current.get('currency', '')} "
                f"({current.get('price_window', 'latest')}; "
                f"{', '.join(current.get('sources', []))})",
                flush=True,
            )
    else:
        preferred = [offer.source for offer in offers if offer.source in PREFERRED_SOURCES]
        print(f"  no preferred offer (got: {', '.join(preferred) or 'none'})", flush=True)
    return priced


def run_fetch_prices(
    *,
    input_path: Path = DEFAULT_INPUT,
    cache_path: Path = DEFAULT_CACHE,
    all_helmets: bool = False,
    limit: int | None = None,
    force: bool = False,
    cache_only: bool = False,
    workers: int = DEFAULT_WORKERS,
) -> None:
    """Fetch live shop prices and merge median market prices into helmets.json."""
    if not input_path.exists():
        print(f"Missing {input_path}. Run: helmet-data build", file=sys.stderr)
        sys.exit(1)

    data = json.loads(input_path.read_text(encoding="utf-8"))
    helmets = data.get("helmets", [])

    source_errors: dict[str, dict[str, Any]] = {}
    outliers: dict[str, list[dict[str, Any]]] = {}
    rates: dict[str, Any] = {}
    stats = update_helmets(
        helmets,
        european_only=not all_helmets,
        limit=limit,
        force=force,
        cache_only=cache_only,
        cache_path=cache_path,
        source_errors=source_errors,
        outliers=outliers,
        exchange_rates=rates,
        workers=workers,
    )

    meta = data.setdefault("meta", {})
    meta["market_prices_fetched_at"] = datetime.now(UTC).isoformat()
    # The site converts between currencies with these (units per USD), refreshed every run.
    meta["exchange_rates"] = {"base": "USD", **rates}
    meta["market_prices_stats"] = stats
    meta["market_price_note"] = (
        "Prefers Geizhals (curl_cffi Safari TLS), Idealo, and toppreise.ch. "
        "Uses median daily price over 14 days when enough snapshots exist. "
        "Amazon is fallback when comparison portals are blocked."
    )
    meta["market_prices_source_errors"] = source_errors
    meta["market_prices_outliers"] = {
        "helmets": len(outliers),
        "offers": sum(len(items) for items in outliers.values()),
        "rules": {
            "test_price_ratio": list(TEST_PRICE_RATIO_BOUNDS),
            "ch_de_ratio": list(CH_DE_RATIO_BOUNDS),
        },
        "dropped": outliers,
    }

    input_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        f"\nDone. checked={stats['checked']} priced={stats['priced']} "
        f"better_than_test={stats['better']} cached={stats['cached']} skipped={stats['skipped']}"
    )
    if outliers:
        print(f"Dropped {sum(len(v) for v in outliers.values())} suspect offers on {len(outliers)} helmets")
    for source, info in source_errors.items():
        print(f"  WARNING: {source} failed {info['count']}x (last: {info['last_error']})")
    if site_stats:
        print("Time per site (the busiest one sets the pace):")
        print(site_report())
