"""Rolling shop-price history and median/average aggregation."""

from __future__ import annotations

import statistics
from datetime import datetime, timedelta, timezone
from typing import Any

from crawlers.price_sources import PREFERRED_SOURCES, PriceOffer, MIN_HELMET_PRICE

HISTORY_MAX_DAYS = 30
HISTORY_PREFERRED_DAYS = 14
FETCH_COOLDOWN_DAYS = 1


def parse_ts(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def prune_history(history: list[dict[str, Any]], *, max_days: int = HISTORY_MAX_DAYS) -> list[dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_days)
    kept: list[dict[str, Any]] = []
    for entry in history:
        fetched_at = parse_ts(entry.get("fetched_at", ""))
        if fetched_at is not None and fetched_at >= cutoff:
            kept.append(entry)
    return kept


def append_history(
    cache_entry: dict[str, Any],
    *,
    offers: list[PriceOffer],
    fetched_at: str,
    offer_to_dict,
) -> list[dict[str, Any]]:
    history = list(cache_entry.get("history", []))
    history.append({"fetched_at": fetched_at, "offers": [offer_to_dict(offer) for offer in offers]})
    return prune_history(history)


def offers_from_history_entry(entry: dict[str, Any], offer_from_dict) -> list[PriceOffer]:
    return [offer_from_dict(item) for item in entry.get("offers", [])]


def offer_price_is_plausible(offer: PriceOffer) -> bool:
    min_price = MIN_HELMET_PRICE.get(offer.currency)
    return min_price is None or offer.price >= min_price


def preferred_offers(offers: list[PriceOffer]) -> list[PriceOffer]:
    plausible = [offer for offer in offers if offer_price_is_plausible(offer)]
    preferred = [offer for offer in plausible if offer.source in PREFERRED_SOURCES]
    return preferred or plausible


def daily_prices(
    history: list[dict[str, Any]],
    *,
    currency: str,
    offer_from_dict,
    max_days: int,
    min_days: int = 0,
) -> list[float]:
    now = datetime.now(timezone.utc)
    oldest = now - timedelta(days=max_days)
    youngest = now - timedelta(days=min_days) if min_days else oldest

    by_day: dict[str, list[float]] = {}
    for entry in history:
        fetched_at = parse_ts(entry.get("fetched_at", ""))
        if fetched_at is None or fetched_at < oldest or fetched_at > now:
            continue
        if min_days and fetched_at < youngest:
            continue

        day = fetched_at.date().isoformat()
        day_offers = preferred_offers(offers_from_history_entry(entry, offer_from_dict))
        day_offers = [offer for offer in day_offers if offer.currency == currency]
        if not day_offers:
            continue
        by_day.setdefault(day, []).append(min(offer.price for offer in day_offers))

    prices: list[float] = []
    for day_prices in by_day.values():
        prices.append(min(day_prices))
    return prices


def aggregate_price(
    history: list[dict[str, Any]],
    latest_offers: list[PriceOffer],
    *,
    currency: str,
    offer_from_dict,
) -> dict[str, Any] | None:
    preferred_latest = [
        offer for offer in preferred_offers(latest_offers) if offer.currency == currency
    ]
    if not preferred_latest and not history:
        return None

    prices_14d = daily_prices(
        history,
        currency=currency,
        offer_from_dict=offer_from_dict,
        max_days=HISTORY_PREFERRED_DAYS,
    )
    prices_30d = daily_prices(
        history,
        currency=currency,
        offer_from_dict=offer_from_dict,
        max_days=HISTORY_MAX_DAYS,
    )

    window = "latest"
    sample: list[float] = []
    if len(prices_14d) >= 2:
        sample = prices_14d
        window = f"{HISTORY_PREFERRED_DAYS}d_median"
    elif len(prices_30d) >= 2:
        sample = prices_30d
        window = f"{HISTORY_MAX_DAYS}d_median"
    elif prices_30d:
        sample = prices_30d
        window = f"{HISTORY_MAX_DAYS}d_latest"
    elif preferred_latest:
        sample = [min(offer.price for offer in preferred_latest)]
        window = "latest"

    if not sample:
        return None

    amount = statistics.median(sample) if len(sample) >= 2 else sample[0]
    amount = round(amount, 2)

    representative = min(preferred_latest, key=lambda offer: abs(offer.price - amount), default=None)
    if representative is None and preferred_latest:
        representative = min(preferred_latest, key=lambda offer: offer.price)

    sources = sorted({offer.source for offer in preferred_latest}) or (
        [representative.source] if representative else []
    )

    return {
        "amount": amount,
        "currency": currency,
        "window": window,
        "sample_days": len(sample),
        "sample_prices": [round(price, 2) for price in sorted(sample)],
        "representative": representative,
        "sources": sources,
        "offers": preferred_latest,
    }


def cache_needs_refresh(entry: dict[str, Any]) -> bool:
    offers = entry.get("offers", [])
    if not offers:
        return True
    if not any(offer.get("source") in PREFERRED_SOURCES for offer in offers):
        return True
    for offer in offers:
        price = float(offer.get("price", 0))
        currency = offer.get("currency", "EUR")
        min_price = {"EUR": 20.0, "CHF": 20.0}.get(currency)
        if min_price is not None and 0 < price < min_price:
            return True
    return False


def fetch_is_due(entry: dict[str, Any] | None, *, force: bool) -> bool:
    if force or not entry:
        return True
    if cache_needs_refresh(entry):
        return True
    fetched_at = parse_ts(entry.get("fetched_at", ""))
    if fetched_at is None:
        return True
    return datetime.now(timezone.utc) - fetched_at >= timedelta(days=FETCH_COOLDOWN_DAYS)
