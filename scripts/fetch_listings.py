#!/usr/bin/env python3
"""Fetch live shop prices and merge median market prices into helmets.json."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from crawlers.stealth_fetch import stealth_get
from crawlers.price_history import (
    aggregate_price,
    append_history,
    fetch_is_due,
    prune_history,
)
from crawlers.price_sources import (
    PREFERRED_SOURCES,
    PriceOffer,
    build_search_context,
    dedupe_offers,
    make_price_client,
    parse_geizhals_phist_html,
    polite_sleep,
    search_http_sources,
)
from protection_tech import apply_protection_to_helmet, load_mips_lookup
from retailer_protection import (
    crawl_helmet_retailer_protection,
    load_retailer_protection_cache,
    merge_retailer_cache_into_lookup,
    save_retailer_protection_cache,
)
from rating_sources import value_ratio_from_ratings

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_INPUT = REPO_ROOT / "web" / "data" / "helmets.json"
DEFAULT_CACHE = SCRIPT_DIR / "price_cache.json"
FRANKFURTER_URL = "https://api.frankfurter.app/latest?from=USD&to=EUR,CHF"


def fetch_exchange_rates(client: httpx.Client) -> dict[str, float]:
    try:
        response = client.get(FRANKFURTER_URL, timeout=15.0)
        response.raise_for_status()
        rates = response.json().get("rates", {})
        return {
            "EUR": float(rates.get("EUR", 0.92)),
            "CHF": float(rates.get("CHF", 0.88)),
        }
    except httpx.HTTPError:
        return {"EUR": 0.92, "CHF": 0.88}


def currency_to_usd(amount: float, currency: str, rates: dict[str, float]) -> float:
    rate = rates.get(currency)
    if not rate:
        return amount
    return amount / rate


def eur_to_chf(amount_eur: float, rates: dict[str, float]) -> float:
    usd = currency_to_usd(amount_eur, "EUR", rates)
    return round(usd * rates["CHF"], 2)


def load_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 2, "helmets": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_cache(path: Path, cache: dict[str, Any]) -> None:
    cache["version"] = 2
    cache["saved_at"] = datetime.now(timezone.utc).isoformat()
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


def apply_market_price(
    helmet: dict[str, Any],
    *,
    offers: list[PriceOffer],
    history: list[dict[str, Any]],
    rates: dict[str, float],
    fetched_at: str,
) -> bool:
    listings = helmet.setdefault("listings", {})
    changed = False

    eur_agg = aggregate_price(history, offers, currency="EUR", offer_from_dict=offer_from_dict)
    chf_agg = aggregate_price(history, offers, currency="CHF", offer_from_dict=offer_from_dict)

    if eur_agg:
        eur_sources = eur_agg["offers"]
        for market in ("de", "at"):
            listings[market] = listing_from_aggregate(
                eur_agg,
                sources=eur_sources,
                fetched_at=fetched_at,
            )
            changed = True

    if chf_agg:
        listings["ch"] = listing_from_aggregate(
            chf_agg,
            sources=chf_agg["offers"],
            fetched_at=fetched_at,
        )
        changed = True
    elif eur_agg:
        converted = eur_to_chf(eur_agg["amount"], rates)
        listings["ch"] = {
            **listing_from_aggregate(eur_agg, sources=eur_agg["offers"], fetched_at=fetched_at),
            "price": converted,
            "currency": "CHF",
            "source": f"{eur_agg['sources'][0]}_eur_converted" if eur_agg["sources"] else "eur_converted",
            "converted_from_eur": eur_agg["amount"],
        }
        changed = True

    test_usd = helmet.get("price_at_test_usd")
    primary = eur_agg or chf_agg
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
        f"{primary['amount']:.2f} {primary['currency']} "
        f"({window_label}; {', '.join(source_names)})"
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


def search_all_sources(
    client: httpx.Client,
    helmet: dict[str, Any],
) -> tuple[list[PriceOffer], list[dict[str, Any]]]:
    ctx = build_search_context(helmet["brand"], helmet["model"])
    offers = dedupe_offers(search_http_sources(client, ctx))
    external_history: list[dict[str, Any]] = []

    geizhals_offer = next((offer for offer in offers if offer.source == "geizhals" and offer.url), None)
    if geizhals_offer:
        phist = geizhals_phist_samples(geizhals_offer.url)
        external_history = history_from_geizhals_phist(phist, geizhals_offer)

    return offers, external_history


def rebuild_from_cache_entry(
    helmet: dict[str, Any],
    cached: dict[str, Any],
    *,
    rates: dict[str, float],
    retailer_cache: dict[str, dict[str, Any]] | None = None,
) -> None:
    history = prune_history(cached.get("history", []))
    offers = [offer_from_dict(item) for item in cached.get("offers", [])]
    apply_market_price(
        helmet,
        offers=offers,
        history=history,
        rates=rates,
        fetched_at=cached.get("fetched_at", datetime.now(timezone.utc).isoformat()),
    )
    if retailer_cache:
        lookup = merge_retailer_cache_into_lookup(load_mips_lookup(), retailer_cache)
        apply_protection_to_helmet(
            helmet,
            lookup=lookup,
            extra_texts=[offer.title for offer in offers],
        )


def update_helmets(
    helmets: list[dict[str, Any]],
    *,
    european_only: bool,
    limit: int | None,
    force: bool,
    cache_only: bool,
    cache_path: Path,
) -> dict[str, int]:
    cache = load_cache(cache_path)
    stats = {"checked": 0, "priced": 0, "better": 0, "cached": 0, "skipped": 0}
    retailer_cache = load_retailer_protection_cache()

    candidates = [
        helmet
        for helmet in helmets
        if (not european_only or helmet.get("european_market"))
        and helmet.get("price_at_test_usd") is not None
    ]
    if limit is not None:
        candidates = candidates[:limit]

    with make_price_client() as client:
        rates = fetch_exchange_rates(client)
        cache["exchange_rates"] = rates

        for index, helmet in enumerate(candidates, start=1):
            helmet_id = helmet["id"]
            cached = cache.get("helmets", {}).get(helmet_id)

            if cache_only and not cached:
                stats["skipped"] += 1
                continue

            if cache_only or not fetch_is_due(cached, force=force):
                if cached:
                    rebuild_from_cache_entry(
                        helmet,
                        cached,
                        rates=rates,
                        retailer_cache=retailer_cache,
                    )
                    stats["cached"] += 1
                    stats["checked"] += 1
                    if helmet.get("current_price"):
                        stats["priced"] += 1
                        if helmet["current_price"].get("better_than_test"):
                            stats["better"] += 1
                continue

            stats["checked"] += 1
            print(f"[{index}/{len(candidates)}] {helmet['brand']} {helmet['model']}…", flush=True)
            offers, external_history = search_all_sources(client, helmet)
            fetched_at = datetime.now(timezone.utc).isoformat()

            prior_history = prune_history(cached.get("history", []) if cached else [])
            history = append_history(
                {"history": prior_history + external_history},
                offers=offers,
                fetched_at=fetched_at,
                offer_to_dict=offer_to_dict,
            )

            cache.setdefault("helmets", {})[helmet_id] = {
                "fetched_at": fetched_at,
                "offers": [offer_to_dict(offer) for offer in offers],
                "history": history,
            }
            save_cache(cache_path, cache)

            cache_entry = cache["helmets"][helmet_id]
            if offers and not cache_only:
                retailer_cache = load_retailer_protection_cache()
                crawl_helmet_retailer_protection(
                    helmet,
                    cache=retailer_cache,
                    price_cache_entry=cache_entry,
                    fetch_delay_s=0.35,
                )
                save_retailer_protection_cache(retailer_cache)
                lookup = merge_retailer_cache_into_lookup(load_mips_lookup(), retailer_cache)
                apply_protection_to_helmet(
                    helmet,
                    lookup=lookup,
                    extra_texts=[offer.title for offer in offers],
                )

            if apply_market_price(
                helmet,
                offers=offers,
                history=history,
                rates=rates,
                fetched_at=fetched_at,
            ):
                stats["priced"] += 1
                current = helmet.get("current_price", {})
                if current.get("better_than_test"):
                    stats["better"] += 1
                    print(f"  better price: {helmet.get('price_comparison_label', '')}", flush=True)
                elif offers:
                    print(
                        f"  {current.get('amount', '?')} {current.get('currency', '')} "
                        f"({current.get('price_window', 'latest')}; "
                        f"{', '.join(current.get('sources', []))})",
                        flush=True,
                    )
            else:
                stats["skipped"] += 1
                preferred = [offer.source for offer in offers if offer.source in PREFERRED_SOURCES]
                print(
                    f"  no preferred offer (got: {', '.join(preferred) or 'none'})",
                    flush=True,
                )

            polite_sleep(2.0)

    save_cache(cache_path, cache)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-i", "--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--all-helmets", action="store_true", help="Include non-European-market helmets")
    parser.add_argument("--limit", type=int, help="Only fetch prices for the first N helmets")
    parser.add_argument("--force", action="store_true", help="Refetch even if today's snapshot exists")
    parser.add_argument(
        "--cache-only",
        action="store_true",
        help="Apply cached median prices only (no shop requests)",
    )
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Missing {args.input}. Run: python scripts/fetch_helmets.py", file=sys.stderr)
        sys.exit(1)

    data = json.loads(args.input.read_text(encoding="utf-8"))
    helmets = data.get("helmets", [])

    stats = update_helmets(
        helmets,
        european_only=not args.all_helmets,
        limit=args.limit,
        force=args.force,
        cache_only=args.cache_only,
        cache_path=args.cache,
    )

    meta = data.setdefault("meta", {})
    meta["market_prices_fetched_at"] = datetime.now(timezone.utc).isoformat()
    meta["market_prices_stats"] = stats
    meta["market_price_note"] = (
        "Prefers Geizhals (curl_cffi Safari TLS), Idealo, and toppreise.ch. "
        "Uses median daily price over 14 days when enough snapshots exist. "
        "Amazon is fallback when comparison portals are blocked."
    )

    args.input.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        f"\nDone. checked={stats['checked']} priced={stats['priced']} "
        f"better_than_test={stats['better']} cached={stats['cached']} skipped={stats['skipped']}"
    )


if __name__ == "__main__":
    main()
