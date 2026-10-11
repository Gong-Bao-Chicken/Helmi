"""Offline regression test: the helmets.json schema from build_dataset is a frontend contract."""

import pytest

from helmet_data import build
from helmet_data.enrich import manufacturer_protection, retailer_protection, styles

RAW_VT = [
    {
        "brand": "Giro",
        "model": "Aries Spherical",
        "certifications": "CPSC, CE",
        "cost": "$300",
        "score": 8.5,
        "date": 2023,
        "low": 7.0,
        "high": 10.0,
        "style": "Road",
        "photo": "giro-aries.jpg",
    },
    {
        "brand": "Bell",
        "model": "Nomad 2 MIPS",
        "certifications": "CPSC",
        "cost": "$80",
        "score": 14.2,
        "date": 2024,
        "low": 12.0,
        "high": 16.5,
        "style": "Multi-sport",
        "photo": "bell-nomad.jpg",
    },
]

TOP_LEVEL_KEYS = {"meta", "filters", "helmets"}
FILTER_KEYS = {
    "aero_sources",
    "aero_tiers",
    "brands_all",
    "brands_eu",
    "markets",
    "mips_variants",
    "presentation_modes",
    "protection_groups",
    "protection_technologies",
    "rating_sources",
    "styles",
}
META_REQUIRED_KEYS = {
    "generated_at",
    "source_url",
    "helmet_count_total",
    "helmet_count_european_market",
    "helmet_count_vt_catalog",
    "manufacturer_fetch_enabled",
    "note",
    "extra_ratings_merged",
    "extra_only_count",
}
VT_HELMET_KEYS = {
    "brand",
    "brand_key",
    "certifications",
    "eu_brand",
    "eu_version",
    "european_market",
    "feature_labels",
    "features",
    "id",
    "image_url",
    "listings",
    "manufacturer",
    "model",
    "price_at_test_label",
    "price_at_test_usd",
    "protection",
    "protection_group",
    "protection_tech",
    "ratings",
    "score",
    "score_high_impact",
    "score_low_impact",
    "search_text",
    "source",
    "style",
    "style_meta",
    "test_year",
    "value_ratio",
}
# Extra-only entries: lab-only helmets (have "stars") and aero catalog stubs (have "aero").
EXTRA_ONLY_KEYS = VT_HELMET_KEYS | {"catalog", "primary_rating_source"}


@pytest.fixture
def dataset(monkeypatch, tmp_path):
    monkeypatch.setattr(build, "fetch_vt_data", lambda client: [dict(raw) for raw in RAW_VT])
    # Never touch the real network-fed caches: point writable caches at empty temp paths.
    for module, attr in [
        (build, "PROTECTION_CACHE_PATH"),
        (manufacturer_protection, "PROTECTION_CACHE_PATH"),
        (build, "RETAILER_CACHE_PATH"),
        (retailer_protection, "RETAILER_CACHE_PATH"),
        (build, "STYLE_CACHE_PATH"),
        (styles, "STYLE_CACHE_PATH"),
    ]:
        monkeypatch.setattr(module, attr, tmp_path / f"{attr.lower()}.json")
    return build.build_dataset(fetch_manufacturer=False)


def test_top_level_and_filter_keys(dataset):
    assert set(dataset) == TOP_LEVEL_KEYS
    assert set(dataset["filters"]) == FILTER_KEYS
    assert set(dataset["meta"]) >= META_REQUIRED_KEYS


def test_helmet_field_sets(dataset):
    helmets = dataset["helmets"]
    vt = [h for h in helmets if h.get("catalog") != "extra_only"]
    assert len(vt) == len(RAW_VT)
    for helmet in vt:
        assert VT_HELMET_KEYS <= set(helmet) <= VT_HELMET_KEYS | {"aero"}
        assert set(helmet["listings"]) == {"de", "at", "ch"}
    for helmet in helmets:
        if helmet.get("catalog") == "extra_only":
            assert EXTRA_ONLY_KEYS <= set(helmet) <= EXTRA_ONLY_KEYS | {"aero", "stars"}
