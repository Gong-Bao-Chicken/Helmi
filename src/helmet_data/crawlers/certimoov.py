import re
from collections.abc import Callable
from dataclasses import dataclass

from bs4 import BeautifulSoup

from .common import make_client, polite_sleep

CERTIMOOV_BASE = "https://www.certimoov.com"
# Site relaunch (2026): the bike listing moved from
# /en/les-tests?field_categorie_target_id=2 to /en/les-tests/velo and detail
# pages from /en/les-tests/<slug> to /en/les-tests/bike/<slug>.
BIKE_LIST_URL = f"{CERTIMOOV_BASE}/en/les-tests/velo"
DETAIL_PATH = "/en/les-tests/bike/"
SLUG_RE = re.compile(r"/en/les-tests/bike/([a-z0-9-]+)")
YEAR_LABELS = ("year of testing", "année de test", "annee de test", "année du test")
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
        response = client.get(BIKE_LIST_URL, params={"page": page})
        response.raise_for_status()
        found = parse_listing_slugs(response.text)
        # Pages past the end render no products (only teaser links we already know).
        if not found - slugs:
            break
        slugs |= found
        polite_sleep(delay)
    return sorted(slugs)


def parse_listing_slugs(html: str) -> set[str]:
    return set(SLUG_RE.findall(html))


def detail_url(slug: str) -> str:
    return f"{CERTIMOOV_BASE}{DETAIL_PATH}{slug}"


def _labelled_value(soup: BeautifulSoup, labels: tuple[str, ...]) -> str:
    for label_el in soup.select(".field--label"):
        if label_el.get_text(strip=True).lower() in labels:
            item = label_el.find_next_sibling(class_="field--item")
            if item:
                return item.get_text(strip=True)
    return ""


def parse_detail_html(html: str, slug: str) -> CertimoovRating | None:
    soup = BeautifulSoup(html, "html.parser")
    rating_el = soup.select_one(".field--name-field-rating.field--item")
    if not rating_el:
        rating_el = soup.select_one(".field--name-field-rating")
    if not rating_el:
        return None

    score_text = rating_el.get_text(strip=True)
    try:
        score = float(score_text.replace(",", "."))
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

    title_el = soup.select_one(".product-title h1") or soup.select_one("h1")

    # Legacy pages had separate brand/model fields; the current site only shows a
    # combined title ("ABUS GAMECHANGER MIPS") - brand is then inferred at match time.
    brand = brand_el.get_text(strip=True) if brand_el else ""
    if model_el:
        model = model_el.get_text(strip=True)
    elif title_el and title_el.get_text(strip=True):
        model = re.sub(r"\s+", " ", title_el.get_text(" ", strip=True))
    else:
        model = slug.replace("-", " ").title()
    year_text = year_el.get_text(strip=True) if year_el else _labelled_value(soup, YEAR_LABELS)
    year_match = re.search(r"\b(19|20)\d{2}\b", year_text)
    test_year = int(year_match.group(0)) if year_match else None

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
        url=detail_url(slug),
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
            response = client.get(detail_url(slug))
            if response.status_code == 404:
                polite_sleep(delay)
                continue
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
