import re
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_client, polite_sleep

CERTIMOOV_BASE = "https://www.certimoov.com"
BIKE_LIST_URL = f"{CERTIMOOV_BASE}/en/les-tests?field_categorie_target_id=2"
IMPACT_FIELDS = (
    "choc-frontal",
    "choc-lateral",
    "choc-arriere",
    "choc-frontal-oblique",
    "choc-lateral-oblique-1",
    "choc-lateral-oblique-2-",
)


@dataclass
class CertimoovRating:
    slug: str
    brand: str
    model: str
    score: float
    stars: int
    test_year: int | None
    url: str
    impact_scores: dict[str, float]


def list_bike_slugs(
    client,
    *,
    max_pages: int = 40,
    delay: float = 0.2,
) -> list[str]:
    slugs: set[str] = set()
    for page in range(max_pages):
        response = client.get(f"{BIKE_LIST_URL}&page={page}")
        response.raise_for_status()
        found = set(re.findall(r"/en/les-tests/([a-z0-9-]+)", response.text))
        if not found:
            break
        slugs |= found
        polite_sleep(delay)
    return sorted(slugs)


def parse_detail_html(html: str, slug: str) -> CertimoovRating | None:
    soup = BeautifulSoup(html, "html.parser")
    rating_el = soup.select_one(".field--name-field-rating.field--item")
    if not rating_el:
        rating_el = soup.select_one(".field--name-field-rating")
    if not rating_el:
        return None

    score_text = rating_el.get_text(strip=True)
    try:
        score = float(score_text)
    except ValueError:
        return None

    brand_el = soup.select_one(".field--name-field-marque.field--item") or soup.select_one(
        ".field--name-field-marque .field--item"
    )
    model_el = soup.select_one(".field--name-field-modele.field--item") or soup.select_one(
        ".field--name-field-modele .field--item"
    )
    year_el = soup.select_one(".field--name-field-annee-de-test.field--item") or soup.select_one(
        ".field--name-field-annee-de-test .field--item"
    )

    brand = brand_el.get_text(strip=True) if brand_el else ""
    model = model_el.get_text(strip=True) if model_el else slug.replace("-", " ").title()
    year_text = year_el.get_text(strip=True) if year_el else ""
    test_year = int(year_text) if year_text.isdigit() else None

    impact_scores: dict[str, float] = {}
    for field in IMPACT_FIELDS:
        paragraph = soup.select_one(f".paragraph--type--{field}")
        if not paragraph:
            continue
        for item in paragraph.select(".field--item"):
            text = item.get_text(strip=True)
            if re.fullmatch(r"\d+(?:\.\d+)?", text):
                impact_scores[field] = float(text)
                break

    return CertimoovRating(
        slug=slug,
        brand=brand,
        model=model,
        score=score,
        stars=max(0, min(5, round(score))),
        test_year=test_year,
        url=f"{CERTIMOOV_BASE}/en/les-tests/{slug}",
        impact_scores=impact_scores,
    )


def fetch_certimoov_ratings(
    *,
    limit: int | None = None,
    delay: float = 0.25,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> list[CertimoovRating]:
    with make_client() as client:
        slugs = list_bike_slugs(client, delay=delay)
        if limit is not None:
            slugs = slugs[:limit]

        ratings: list[CertimoovRating] = []
        total = len(slugs)
        for index, slug in enumerate(slugs, start=1):
            if on_progress:
                on_progress(index, total, slug)
            response = client.get(urljoin(CERTIMOOV_BASE, f"/en/les-tests/{slug}"))
            response.raise_for_status()
            parsed = parse_detail_html(response.text, slug)
            if parsed:
                ratings.append(parsed)
            polite_sleep(delay)
        return ratings


def certimoov_to_dict(rating: CertimoovRating) -> dict:
    return {
        "brand": rating.brand,
        "model": rating.model,
        "slug": rating.slug,
        "score": rating.score,
        "stars": rating.stars,
        "test_year": rating.test_year,
        "url": rating.url,
        "impact_scores": rating.impact_scores,
    }
