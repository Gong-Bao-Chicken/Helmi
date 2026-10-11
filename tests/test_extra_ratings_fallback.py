"""A failing lab source must fall back to its cached entries instead of aborting the update."""

import json

import httpx
import pytest

from helmet_data.crawlers.folksam import FolksamRating
from helmet_data.crawlers.nsw_helmet_star import NswHelmetStarRating
from helmet_data.steps import extra_ratings

HELMETS = [
    {"id": "giro-register", "brand": "Giro", "model": "Register"},
    {"id": "bell-nomad", "brand": "Bell", "model": "Nomad"},
]

PREVIOUS = {
    "meta": {
        "generated_at": "2026-06-28T15:55:23+00:00",
        "sources": {
            "certimoov": {"fetched": 2, "matched": 1},
            "folksam": {"fetched": 1, "matched": 1},
        },
    },
    "matches": [
        {
            "id": "giro-register",
            "match": {"brand": "Giro", "model": "Register", "confidence": 1.0, "method": "slug"},
            "ratings": {
                "certimoov": {
                    "score": 3.0,
                    "stars": 3,
                    "test_year": 2021,
                    "url": "https://www.certimoov.com/en/les-tests/giro-register-mips",
                    "impact_scores": {},
                    "rank_pct": 0.4,
                },
                "folksam": {"overall_result_pct": -50.0, "rank_pct": 0.0},
            },
        }
    ],
    "unmatched": [
        {"source": "certimoov", "brand": "B'Twin", "model": "KH 300", "slug": "btwin-kh-300"},
        {"source": "folksam", "name": "Old Folksam Helmet"},
    ],
}


def _boom(**_kwargs):
    request = httpx.Request("GET", "https://www.certimoov.com/en/les-tests")
    raise httpx.HTTPStatusError(
        "404 Not Found", request=request, response=httpx.Response(404, request=request)
    )


@pytest.fixture
def paths(tmp_path):
    helmets_path = tmp_path / "helmets.json"
    helmets_path.write_text(json.dumps({"helmets": HELMETS}), encoding="utf-8")
    output = tmp_path / "extra_ratings.json"
    raw_output = tmp_path / "extra_ratings_raw.json"
    output.write_text(
        json.dumps({"meta": PREVIOUS["meta"], "matches": PREVIOUS["matches"]}), encoding="utf-8"
    )
    raw_output.write_text(json.dumps(PREVIOUS), encoding="utf-8")
    return helmets_path, output, raw_output


@pytest.fixture
def working_folksam_and_nsw(monkeypatch):
    folksam = [
        FolksamRating(
            name="Bell Nomad",
            overall_result_pct=10.0,
            recommended=True,
            grade=3,
            segment="adults",
            test_year=2025,
            source_url="https://example.org/folksam.pdf",
        )
    ]
    nsw = [
        NswHelmetStarRating(
            model="Bell Nomad",
            stars=4,
            category="General helmets",
            price_band="$$",
            source_url="https://www.helmetstar.com.au/helmet/bell-nomad",
            test_year=2026,
        )
    ]
    monkeypatch.setattr(extra_ratings, "fetch_folksam_ratings", lambda **_: folksam)
    monkeypatch.setattr(extra_ratings, "fetch_nsw_helmet_star_ratings", lambda **_: nsw)


def _run(paths):
    helmets_path, output, raw_output = paths
    extra_ratings.run_fetch_extra_ratings(
        helmets_path=helmets_path, output=output, raw_output=raw_output, delay=0
    )
    return (
        json.loads(output.read_text(encoding="utf-8")),
        json.loads(raw_output.read_text(encoding="utf-8")),
    )


def test_failed_source_reuses_cached_entries(monkeypatch, paths, working_folksam_and_nsw):
    monkeypatch.setattr(extra_ratings, "fetch_certimoov_ratings", _boom)

    merged, raw = _run(paths)

    sources = merged["meta"]["sources"]
    assert sources["certimoov"]["stale"] is True
    assert "404" in sources["certimoov"]["error"]
    assert sources["certimoov"]["stale_since"] == PREVIOUS["meta"]["generated_at"]
    assert sources["certimoov"]["matched"] == 1
    # Healthy sources are fresh and carry no failure markers.
    assert sources["folksam"] == {"fetched": 1, "matched": 1}
    assert sources["nsw_helmet_star"] == {"fetched": 1, "matched": 1}

    by_id = {entry["id"]: entry for entry in merged["matches"]}
    cached = by_id["giro-register"]["ratings"]
    assert cached["certimoov"]["score"] == 3.0
    assert cached["certimoov"]["url"].endswith("giro-register-mips")
    # Only the failed source is taken from the cache; old Folksam data is replaced.
    assert "folksam" not in cached
    assert by_id["bell-nomad"]["ratings"]["folksam"]["overall_result_pct"] == 10.0
    assert by_id["bell-nomad"]["ratings"]["nsw_helmet_star"]["test_year"] == 2026

    raw_sources = {(u["source"], u.get("slug") or u.get("name")) for u in raw["unmatched"]}
    assert ("certimoov", "btwin-kh-300") in raw_sources
    assert ("folksam", "Old Folksam Helmet") not in raw_sources


def test_stale_since_survives_repeated_failures(monkeypatch, paths, working_folksam_and_nsw):
    monkeypatch.setattr(extra_ratings, "fetch_certimoov_ratings", _boom)
    _run(paths)
    merged, _ = _run(paths)
    certimoov = merged["meta"]["sources"]["certimoov"]
    assert certimoov["stale_since"] == PREVIOUS["meta"]["generated_at"]
    assert certimoov["matched"] == 1


def test_empty_result_counts_as_failure(monkeypatch, paths, working_folksam_and_nsw):
    monkeypatch.setattr(extra_ratings, "fetch_certimoov_ratings", lambda **_: [])
    merged, _ = _run(paths)
    assert merged["meta"]["sources"]["certimoov"]["stale"] is True


def test_all_sources_failing_without_cache_does_not_raise(monkeypatch, tmp_path):
    helmets_path = tmp_path / "helmets.json"
    helmets_path.write_text(json.dumps({"helmets": HELMETS}), encoding="utf-8")
    for name in ("fetch_certimoov_ratings", "fetch_folksam_ratings", "fetch_nsw_helmet_star_ratings"):
        monkeypatch.setattr(extra_ratings, name, _boom)
    merged, _ = _run((helmets_path, tmp_path / "out.json", tmp_path / "raw.json"))
    assert merged["matches"] == []
    assert all(info["stale"] for info in merged["meta"]["sources"].values())


def test_extra_only_stubs_are_not_match_targets(tmp_path):
    path = tmp_path / "helmets.json"
    path.write_text(
        json.dumps(
            {
                "helmets": HELMETS
                + [
                    {
                        "id": "extra-btwin-kh-300",
                        "brand": "B'Twin",
                        "model": "KH 300",
                        "catalog": "extra_only",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    assert [h["id"] for h in extra_ratings.load_helmets(path)] == ["giro-register", "bell-nomad"]
