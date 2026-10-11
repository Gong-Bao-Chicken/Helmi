"""Offline parser tests for the CERTIMOOV and NSW Helmet STAR page layouts (2026 sites)."""

from helmet_data.crawlers import certimoov, nsw_helmet_star
from helmet_data.enrich.matching import match_certimoov

CERTIMOOV_LISTING = """
<a href="/en/les-tests/bike/abus-gamechanger-mips">x</a>
<a href="/en/les-tests/bike/abus-hyban-20">y</a>
<a href="/en/les-tests/velo">all</a>
"""

CERTIMOOV_DETAIL = """
<div class="product-title"><h1>Abus Hyban 2.0</h1></div>
<div class="field field--name-field-rating field--type-list-string field--item">3.5</div>
<div class="paragraph paragraph--type--dropdown">
  <div class="field"><div class="field--label">Category</div><div class="field--item">Adulte</div></div>
  <div class="field"><div class="field--label">Year of testing</div><div class="field--item">2020</div></div>
</div>
<div class="paragraph paragraph--type--choc-frontal"><div class="field--item">2</div></div>
<div class="paragraph paragraph--type--choc-lateral"><div class="field--item">3.0</div></div>
"""


def test_certimoov_listing_slugs():
    assert certimoov.parse_listing_slugs(CERTIMOOV_LISTING) == {
        "abus-gamechanger-mips",
        "abus-hyban-20",
    }


def test_certimoov_detail_parsing():
    rating = certimoov.parse_detail_html(CERTIMOOV_DETAIL, "abus-hyban-20")
    assert rating is not None
    assert rating.model == "Abus Hyban 2.0"
    assert rating.brand == ""
    assert rating.score == 3.5
    assert rating.test_year == 2020
    assert rating.url == "https://www.certimoov.com/en/les-tests/bike/abus-hyban-20"
    assert rating.impact_scores == {"choc-frontal": 2.0, "choc-lateral": 3.0}


def test_certimoov_combined_title_matches_with_inferred_brand():
    helmets = [
        {"id": "abus-hyban-2-0-mips", "brand": "ABUS", "model": "Hyban 2.0 MIPS"},
        {"id": "abus-gamechanger", "brand": "ABUS", "model": "GameChanger"},
    ]
    payload = certimoov.certimoov_to_dict(certimoov.parse_detail_html(CERTIMOOV_DETAIL, "abus-hyban-20"))
    match = match_certimoov(payload, helmets)
    assert match is not None and match.helmet_id == "abus-hyban-2-0-mips"


NSW_LISTING = """
<div data-helmet-link="/helmet/lazer-tempo-kineticore">
  <h3><span>Lazer</span><span>Tempo Kineticore</span></h3>
  <span>Adult</span>
  <div role="img" aria-label="5 out of 5 stars"></div>
  <div role="img" aria-label="Price level 2 out of 4"></div>
</div>
<div data-helmet-link="/helmet/trek-tyro">
  <h3><span>Trek</span><span>Tyro</span></h3>
  <span>Child</span>
  <div role="img" aria-label="3 out of 5 stars"></div>
  <div role="img" aria-label="Price level 1 out of 4"></div>
</div>
"""

NSW_DETAIL = """
<h1><span>Bell</span><span>Falcon XR MIPS</span></h1>
<div class="flex"><span>Tested in 2025</span><span class="dot"></span>
<span>Adult</span><span class="dot"></span><span>Road</span></div>
"""


def test_nsw_listing_parsing():
    ratings = nsw_helmet_star.parse_listing_html(NSW_LISTING)
    assert [(r.model, r.stars, r.price_band) for r in ratings] == [
        ("Lazer Tempo Kineticore", 5, "$$"),
        ("Trek Tyro", 3, "$"),
    ]
    assert ratings[0].source_url == "https://www.helmetstar.com.au/helmet/lazer-tempo-kineticore"
    assert ratings[1].category == "Child helmets"


def test_nsw_detail_parsing():
    assert nsw_helmet_star.parse_detail_html(NSW_DETAIL) == {
        "test_year": 2025,
        "age_group": "Adult",
        "helmet_type": "Road",
    }


def test_extra_only_stub_from_combined_title_keeps_lab_photo():
    from helmet_data import build

    entry = {
        "source": "certimoov",
        "brand": "",
        "model": "Abus Hyban 2.0",
        "slug": "abus-hyban-20",
        "score": 3.5,
        "stars": 4,
        "test_year": 2020,
        "url": "https://www.certimoov.com/en/les-tests/bike/abus-hyban-20",
        "impact_scores": {},
        "image_url": "https://www.certimoov.com/sites/default/files/hyban_front.jpg",
    }
    stub = build.standalone_from_unmatched(entry, set())
    assert stub is not None
    assert stub["brand"].lower() == "abus" and "Hyban" in stub["model"]
    assert stub["image_url"] == entry["image_url"]


def test_duplicate_certimoov_pages_become_one_stub():
    from helmet_data import build

    base = {
        "source": "certimoov",
        "brand": "",
        "model": "Abus Yadd-I",
        "score": 3.0,
        "stars": 3,
        "test_year": 2020,
        "impact_scores": {"choc-frontal": 3.0},
    }
    entries = [
        {**base, "slug": "abus-yadd-i", "url": "https://x/abus-yadd-i"},
        {**base, "slug": "abus-yadd-i-0", "url": "https://x/abus-yadd-i-0"},
        {**base, "slug": "abus-yadd-i-mips", "model": "Abus Yadd-I MIPS", "url": "https://x/m"},
    ]
    helmets: list[dict] = []
    assert build.append_unmatched_helmets(helmets, entries, set()) == 2
