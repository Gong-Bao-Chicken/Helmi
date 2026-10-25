"""NSW Helmet STAR ratings.

The programme moved from transport.nsw.gov.au (one big table) to its own site,
helmetstar.com.au (2026): listing pages with one card per helmet
(``/adult-helmets``, ``/childrens-helmets``) and a detail page per helmet
(``/helmet/<slug>``) that carries the test year, helmet type and the score: a total out of
100 (the stars are bands of it), its parts, and any penalty ("modifier") applied.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_client, polite_sleep

NSW_HELMET_STAR_BASE = "https://www.helmetstar.com.au"
NSW_HELMET_STAR_URL = f"{NSW_HELMET_STAR_BASE}/"
LISTING_PATHS = ("/adult-helmets", "/childrens-helmets")
# Not bicycle helmets - VT/the frontend never list them.
EXCLUDED_TYPES = {"skateboard & scooter"}
# Keep the category labels of the former transport.nsw.gov.au tables.
TYPE_LABELS = {
    "general": "General helmets",
    "road": "Road helmets",
    "mountain bike open-face": "Mountain bike open-face helmets",
    "mountain bike full-face": "Mountain bike/BMX full-face helmets",
}
CHILD_CATEGORY = "Child helmets"


@dataclass
class NswHelmetStarRating:
    model: str
    stars: int
    category: str | None
    price_band: str | None
    source_url: str
    test_year: int | None = None
    helmet_type: str | None = None
    age_group: str | None = None
    image_url: str | None = None
    score: float | None = None
    metrics: dict[str, dict[str, float]] | None = None
    modifier: str | None = None


def _text(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip() if el else ""


def _category(age_group: str | None, helmet_type: str | None) -> str | None:
    if age_group and age_group.lower().startswith("child"):
        return CHILD_CATEGORY
    if helmet_type:
        return TYPE_LABELS.get(helmet_type.lower(), f"{helmet_type} helmets")
    return None


def parse_listing_html(html: str) -> list[NswHelmetStarRating]:
    """Parse helmet cards from an /adult-helmets or /childrens-helmets page."""
    soup = BeautifulSoup(html, "html.parser")
    ratings: list[NswHelmetStarRating] = []
    seen: set[str] = set()
    for card in soup.select("[data-helmet-link]"):
        link = card.get("data-helmet-link") or ""
        if not link.startswith("/helmet/") or link in seen:
            continue
        spans = card.select("h3 span")
        name = " ".join(_text(span) for span in spans if _text(span)) or _text(card.find("h3"))
        stars_el = card.find(attrs={"aria-label": re.compile(r"\d out of 5 stars")})
        if not name or not stars_el:
            continue
        stars = int(re.search(r"(\d) out of 5", stars_el["aria-label"]).group(1))
        if stars < 1:
            continue
        price_el = card.find(attrs={"aria-label": re.compile(r"Price level \d out of 4")})
        price_band = None
        if price_el:
            price_band = "$" * int(re.search(r"level (\d)", price_el["aria-label"]).group(1))
        img = card.select_one("img[src]")
        age_el = card.select_one("h3 + span")
        age_group = _text(age_el) or None
        seen.add(link)
        ratings.append(
            NswHelmetStarRating(
                model=name,
                stars=stars,
                category=_category(age_group, None),
                price_band=price_band,
                source_url=f"{NSW_HELMET_STAR_BASE}{link}",
                age_group=age_group,
                image_url=urljoin(NSW_HELMET_STAR_BASE, img["src"]) if img else None,
            )
        )
    return ratings


METRIC_RE = re.compile(r"^(.+?):\s*([\d.]+) out of ([\d.]+)$")


def parse_detail_html(html: str) -> dict:
    """Return test_year / age_group / helmet_type and score / metrics / modifier from a helmet page."""
    soup = BeautifulSoup(html, "html.parser")
    info: dict = {}
    # "Total 29.0 / 100": the final score, after any modifier.
    total = soup.find(string=re.compile(r"^\s*Total\s*$"))
    row = total.find_parent("div") if total else None
    if row:
        number = re.search(r"(\d+(?:\.\d+)?)\s*/\s*100", _text(row))
        if number:
            info["score"] = float(number.group(1))
    metrics = {}
    for el in soup.find_all(attrs={"aria-label": METRIC_RE}):
        name, value, maximum = METRIC_RE.match(el["aria-label"]).groups()
        metrics[name.strip()] = {"score": float(value), "max": float(maximum)}
    if metrics:
        info["metrics"] = metrics
    modifier = soup.find("span", string=re.compile(r"^\s*Modifier\s*$"))
    if modifier and modifier.parent:
        info["modifier"] = _text(modifier.parent).split(":", 1)[-1].strip() or None
    tested = soup.find(string=re.compile(r"Tested in\s+\d{4}"))
    if tested:
        info["test_year"] = int(re.search(r"\d{4}", tested).group(0))
        row = tested.find_parent("div")
        if row:
            parts = [_text(span) for span in row.find_all("span") if _text(span)]
            parts = [p for p in parts if not p.startswith("Tested in")]
            if parts:
                info["age_group"] = parts[0]
            if len(parts) > 1:
                info["helmet_type"] = parts[1]
    return info


# Backwards-compatible name for the old table parser entry point.
def parse_nsw_html(html: str) -> list[NswHelmetStarRating]:
    return parse_listing_html(html)


def fetch_nsw_helmet_star_ratings(
    *,
    on_progress: Callable[[str], None] | None = None,
    delay: float = 0.2,
    fetch_details: bool = True,
) -> list[NswHelmetStarRating]:
    ratings: list[NswHelmetStarRating] = []
    seen: set[str] = set()
    with make_client(browser=True) as client:
        for path in LISTING_PATHS:
            url = f"{NSW_HELMET_STAR_BASE}{path}"
            if on_progress:
                on_progress(url)
            response = client.get(url)
            response.raise_for_status()
            for item in parse_listing_html(response.text):
                if item.source_url not in seen:
                    seen.add(item.source_url)
                    ratings.append(item)
        if not ratings:
            raise RuntimeError("NSW Helmet STAR: no helmet cards found (site layout changed?)")

        if not fetch_details:
            return ratings
        enriched: list[NswHelmetStarRating] = []
        for item in ratings:
            try:
                response = client.get(item.source_url)
                response.raise_for_status()
                info = parse_detail_html(response.text)
            except Exception as exc:  # keep the listing data if a detail page fails
                print(f"  NSW detail failed for {item.source_url}: {exc}", flush=True)
                info = {}
            helmet_type = info.get("helmet_type")
            if helmet_type and helmet_type.lower() in EXCLUDED_TYPES:
                continue
            age_group = info.get("age_group") or item.age_group
            enriched.append(
                replace(
                    item,
                    test_year=info.get("test_year"),
                    helmet_type=helmet_type,
                    age_group=age_group,
                    category=_category(age_group, helmet_type) or item.category,
                    score=info.get("score"),
                    metrics=info.get("metrics"),
                    modifier=info.get("modifier"),
                )
            )
            polite_sleep(delay)
        return enriched


def nsw_to_dict(rating: NswHelmetStarRating) -> dict:
    return {
        "model": rating.model,
        "stars": rating.stars,
        "category": rating.category,
        "price_band": rating.price_band,
        "url": rating.source_url,
        "test_year": rating.test_year,
        "image_url": rating.image_url,
        "score": rating.score,
        "metrics": rating.metrics,
        "modifier": rating.modifier,
    }
