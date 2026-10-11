"""Price step: shop failures degrade gracefully, implausible offers are dropped."""

from helmet_data import pipeline
from helmet_data.crawlers import price_sources
from helmet_data.crawlers.price_sources import PriceOffer, build_search_context, score_offer
from helmet_data.steps import prices

RATES = {"EUR": 0.9, "CHF": 0.8}  # units per USD


def offer(source, price, currency, title="POC Cytal Helm"):
    return PriceOffer(
        source=source,
        title=title,
        price=price,
        currency=currency,
        url="https://geizhals.de/x-a1.html",
        match_score=1.0,
    )


# --- outlier filter -------------------------------------------------------


def test_ch_de_mismatch_drops_the_side_far_from_test_price():
    # 130 EUR ~ 144 USD, 404 CHF ~ 505 USD; test price 250 USD -> CHF is the outlier.
    offers = [offer("geizhals", 130.0, "EUR"), offer("toppreise", 404.2, "CHF")]
    kept, _, dropped = prices.drop_price_outliers(offers, [], test_usd=250.0, rates=RATES)
    assert [o.source for o in kept] == ["geizhals"]
    assert dropped[0]["source"] == "toppreise"
    assert "CH/DE" in dropped[0]["reason"]


def test_ch_de_mismatch_keeps_a_price_two_shops_agree_on():
    # Giro Helios Spherical: German clearance (93/117 EUR) vs Swiss list price (272 CHF),
    # test price 250 USD. Both are real market prices; neither side is dropped.
    offers = [
        offer("geizhals", 93.28, "EUR"),
        offer("idealo", 117.49, "EUR"),
        offer("toppreise", 272.0, "CHF"),
    ]
    kept, _, dropped = prices.drop_price_outliers(offers, [], test_usd=250.0, rates=RATES)
    assert {o.source for o in kept} == {"geizhals", "idealo", "toppreise"}
    assert dropped == []


def test_ch_de_mismatch_without_test_price_drops_chf():
    offers = [offer("geizhals", 100.0, "EUR"), offer("toppreise", 300.0, "CHF")]
    kept, _, dropped = prices.drop_price_outliers(offers, [], test_usd=None, rates=RATES)
    assert [o.currency for o in kept] == ["EUR"]
    assert len(dropped) == 1


def test_test_price_bounds():
    # test 100 USD: 20 EUR (0.22x) too cheap, 300 EUR (3.3x) too dear, 90 EUR fine.
    offers = [offer("idealo", 20.5, "EUR"), offer("geizhals", 300.0, "EUR"), offer("toppreise", 90.0, "CHF")]
    kept, _, dropped = prices.drop_price_outliers(offers, [], test_usd=100.0, rates=RATES)
    assert [o.source for o in kept] == ["toppreise"]
    assert {d["source"] for d in dropped} == {"idealo", "geizhals"}


def test_consistent_prices_are_kept_and_history_is_filtered():
    offers = [offer("geizhals", 100.0, "EUR"), offer("toppreise", 105.0, "CHF")]
    history = [
        {
            "fetched_at": "2026-10-01T12:00:00+00:00",
            "offers": [prices.offer_to_dict(offer("geizhals", 900.0, "EUR"))],
        },
        {
            "fetched_at": "2026-10-02T12:00:00+00:00",
            "offers": [prices.offer_to_dict(offer("geizhals", 99.0, "EUR"))],
        },
    ]
    kept, clean_history, dropped = prices.drop_price_outliers(offers, history, test_usd=120.0, rates=RATES)
    assert len(kept) == 2 and not dropped
    assert [e["offers"][0]["price"] for e in clean_history] == [99.0]


def test_apply_market_price_reports_dropped_offers():
    helmet = {"id": "poc-cytal", "price_at_test_usd": 250.0, "ratings": {}}
    dropped = []
    prices.apply_market_price(
        helmet,
        offers=[offer("geizhals", 130.0, "EUR"), offer("toppreise", 404.2, "CHF")],
        history=[],
        rates=RATES,
        fetched_at="2026-10-11T00:00:00+00:00",
        dropped=dropped,
    )
    assert len(dropped) == 1
    assert helmet["listings"]["de"]["price"] == 130.0
    # CH falls back to the converted EUR price instead of the suspect CHF offer.
    assert helmet["listings"]["ch"]["currency"] == "CHF"
    assert helmet["listings"]["ch"]["price"] < 200


# --- matching ---------------------------------------------------------------


def test_toppreise_uses_median_of_size_variants():
    offers = [offer("toppreise", p, "CHF") for p in (198.8, 466.0, 268.0)] + [offer("geizhals", 180.0, "EUR")]
    deduped = {o.source: o.price for o in price_sources.dedupe_offers(offers)}
    assert deduped == {"geizhals": 180.0, "toppreise": 268.0}


def test_sibling_model_words_are_rejected():
    helmets = [
        {"id": "poc-cytal", "brand": "POC", "model": "Cytal"},
        {"id": "poc-cytal-carbon", "brand": "POC", "model": "Cytal Carbon"},
    ]
    exclude = price_sources.sibling_exclude_tokens(helmets[0], helmets)
    assert exclude == {"carbon"}
    ctx = build_search_context("POC", "Cytal", exclude_tokens=exclude)
    assert score_offer(ctx, "POC Cytal Carbon Fahrradhelm, weiss") == 0.0
    assert score_offer(ctx, "POC Cytal Fahrradhelm") > 0.0
    # The carbon model itself is unaffected.
    assert price_sources.sibling_exclude_tokens(helmets[1], helmets) == frozenset()


# --- resilience ---------------------------------------------------------------


def test_failing_shop_is_recorded_and_others_still_searched(monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("curl: (35) TLS handshake failed")

    monkeypatch.setattr(price_sources, "search_geizhals", boom)
    monkeypatch.setattr(price_sources, "search_idealo", lambda *_: [])
    monkeypatch.setattr(price_sources, "search_toppreise", lambda *_: [offer("toppreise", 120.0, "CHF")])
    monkeypatch.setattr(price_sources, "geizhals_is_rate_limited", lambda: False)
    monkeypatch.setattr(price_sources, "search_amazon_de", lambda *_: [])
    failures = {}
    found = price_sources.search_http_sources(None, build_search_context("POC", "Cytal"), failures=failures)
    assert [o.source for o in found] == ["toppreise"]
    assert "TLS" in failures["geizhals"]


def test_cached_offer_kept_for_failed_source():
    cached = {"offers": [prices.offer_to_dict(offer("geizhals", 130.0, "EUR"))]}
    fresh = [offer("toppreise", 120.0, "CHF")]
    merged = prices.carry_over_failed_sources(fresh, cached, {"geizhals"})
    assert sorted(o.source for o in merged) == ["geizhals", "toppreise"]
    assert prices.carry_over_failed_sources(fresh, cached, set()) == fresh


def test_update_helmets_survives_helmet_level_crash(monkeypatch, tmp_path):
    def crash(*_args, **_kwargs):
        raise ValueError("parser exploded")

    monkeypatch.setattr(prices, "search_shops", crash)
    monkeypatch.setattr(prices, "fetch_exchange_rates", lambda client: RATES)
    monkeypatch.setattr(prices, "load_retailer_protection_cache", lambda: {})
    helmets = [
        {"id": "a", "brand": "POC", "model": "Cytal", "european_market": True, "price_at_test_usd": 250.0},
        {"id": "b", "brand": "POC", "model": "Ventral", "european_market": True, "price_at_test_usd": 250.0},
    ]
    errors = {}
    stats = prices.update_helmets(
        helmets,
        european_only=True,
        limit=None,
        force=True,
        cache_only=False,
        cache_path=tmp_path / "cache.json",
        source_errors=errors,
    )
    assert stats["checked"] == 2 and stats["skipped"] == 2
    assert errors["helmet_refresh"]["count"] == 2


def test_pipeline_continues_after_failed_step(monkeypatch, tmp_path):
    calls = []

    def fail(**_kwargs):
        calls.append("ratings")
        raise RuntimeError("certimoov 404")

    helmets_json = tmp_path / "helmets.json"
    helmets_json.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(pipeline, "HELMETS_JSON_PATH", helmets_json)
    monkeypatch.setattr(pipeline, "run_fetch_aero", lambda **_: calls.append("aero"))
    monkeypatch.setattr(pipeline, "run_fetch_extra_ratings", fail)
    monkeypatch.setattr(pipeline, "run_build", lambda **_: calls.append("build"))
    monkeypatch.setattr(pipeline, "run_fetch_prices", lambda **_: calls.append("prices"))
    pipeline.run_update()
    assert calls == ["aero", "ratings", "build", "prices"]


def test_shared_tech_suffix_alone_does_not_match_another_model():
    ctx = build_search_context("Sweet Protection", "Strayer 2Vi MIPS")
    assert score_offer(ctx, "Sweet Protection Falconer 2Vi MIPS Helm") == 0.0
    assert score_offer(ctx, "Sweet Protection Strayer 2Vi MIPS") > 0.0
    ctx = build_search_context("Sweet Protection", "Fixer Carbon 2Vi MIPS")
    assert score_offer(ctx, "Sweet Protection Fixer Composite 2Vi MIPS") == 0.0


def test_cached_offers_are_rescored_on_rebuild():
    helmets = [
        {"id": "poc-cytal", "brand": "POC", "model": "Cytal", "price_at_test_usd": 250.0, "ratings": {}},
        {"id": "poc-cytal-carbon", "brand": "POC", "model": "Cytal Carbon"},
    ]
    stale_wrong = offer("toppreise", 404.2, "CHF", title="POC Cytal Carbon Fahrradhelm , weiss")
    good = offer("geizhals", 130.0, "EUR", title="POC Cytal Helm")
    cached = {
        "fetched_at": "2026-10-11T00:00:00+00:00",
        "offers": [prices.offer_to_dict(good), prices.offer_to_dict(stale_wrong)],
        "history": [],
    }
    helmet = helmets[0]
    prices.rebuild_from_cache_entry(
        helmet,
        cached,
        rates=RATES,
        exclude_tokens=price_sources.sibling_exclude_tokens(helmet, helmets),
    )
    assert helmet["listings"]["de"]["price"] == 130.0
    assert "converted_from_eur" in helmet["listings"]["ch"]


def test_blocked_geizhals_counts_as_failure(monkeypatch):
    monkeypatch.setattr(price_sources, "search_geizhals", lambda *a, **k: [])
    monkeypatch.setattr(price_sources, "search_idealo", lambda *_: [offer("idealo", 100.0, "EUR")])
    monkeypatch.setattr(price_sources, "search_toppreise", lambda *_: [])
    monkeypatch.setattr(price_sources, "geizhals_is_rate_limited", lambda: True)
    monkeypatch.setattr(price_sources, "search_amazon_de", lambda *_: [])
    failures = {}
    price_sources.search_http_sources(None, build_search_context("POC", "Cytal"), failures=failures)
    assert "blocked" in failures["geizhals"]


def test_stealth_get_spaces_requests_per_host_not_globally(monkeypatch):
    import threading
    import time as real_time

    from helmet_data.crawlers import stealth_fetch

    class FakeResponse:
        status_code = 200
        text = "x" * 10_000
        headers: dict[str, str] = {}

    class FakeSession:
        def get(self, *_args, **_kwargs):
            real_time.sleep(0.05)
            return FakeResponse()

    monkeypatch.setattr(stealth_fetch, "MIN_REQUEST_GAP_S", 0.2)
    monkeypatch.setattr(stealth_fetch.random, "uniform", lambda *_: 0.0)
    monkeypatch.setattr(stealth_fetch, "get_session", lambda _host: FakeSession())
    monkeypatch.setattr(stealth_fetch, "_save_cookies", lambda: None)
    monkeypatch.setattr(stealth_fetch, "_host_last_request_at", {})

    def fetch_all(urls):
        threads = [threading.Thread(target=stealth_fetch.stealth_get, args=(url,)) for url in urls]
        start = real_time.monotonic()
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        return real_time.monotonic() - start

    # Three hosts in parallel: no host waits for another.
    assert fetch_all([f"https://shop{i}.example/a" for i in range(3)]) < 0.25
    # Three requests to one host: each waits out the gap after the previous one.
    stealth_fetch._host_last_request_at.clear()
    assert fetch_all(["https://same.example/a"] * 3) >= 0.4


def test_update_helmets_fetches_helmets_in_parallel(monkeypatch, tmp_path, capsys):
    import time

    def slow_search(_client, helmet, **_kwargs):
        print(f"  searching {helmet['model']}")
        time.sleep(0.3)
        print(f"  searched {helmet['model']}")
        return []

    monkeypatch.setattr(prices, "search_shops", slow_search)
    monkeypatch.setattr(prices, "fetch_exchange_rates", lambda client: RATES)
    monkeypatch.setattr(prices, "load_retailer_protection_cache", lambda: {})
    helmets = [
        {
            "id": f"h{i}",
            "brand": "POC",
            "model": f"Model {i}",
            "european_market": True,
            "price_at_test_usd": 200.0,
        }
        for i in range(4)
    ]
    start = time.monotonic()
    stats = prices.update_helmets(
        helmets,
        european_only=True,
        limit=None,
        force=True,
        cache_only=False,
        cache_path=tmp_path / "c.json",
        workers=4,
    )
    assert time.monotonic() - start < 0.9  # four 0.3 s searches overlapped, not 1.2 s in a row
    assert stats["checked"] == 4
    # Each helmet's lines stay together under its own header.
    out = capsys.readouterr().out
    for i in range(4):
        block = out.split(f"POC Model {i}…\n", 1)[1].splitlines()
        assert block[:2] == [f"  searching Model {i}", f"  searched Model {i}"]
