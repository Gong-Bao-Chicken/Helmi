from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from bs4 import BeautifulSoup

from crawlers.common import make_client

NSW_HELMET_STAR_URL = (
    "https://www.transport.nsw.gov.au/roadsafety/bicycle-riders/helmet-star"
)


@dataclass
class NswHelmetStarRating:
    model: str
    stars: int
    category: str | None
    price_band: str | None
    source_url: str


def parse_nsw_html(html: str) -> list[NswHelmetStarRating]:
    soup = BeautifulSoup(html, "html.parser")
    ratings: list[NswHelmetStarRating] = []
    category: str | None = None

    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 3:
                continue

            first = cells[0].get_text(" ", strip=True)
            second = cells[1].get_text(" ", strip=True)
            if "Make and model" in second:
                if "helmet" in first.lower():
                    category = first
                continue

            if not cells[0].find("img") or not second:
                continue

            stars = cells[2].get_text(" ", strip=True).count("★")
            if stars < 1:
                continue

            price_band = cells[3].get_text(strip=True) if len(cells) > 3 else None
            model = re.sub(r"\s+", " ", second).strip()
            ratings.append(
                NswHelmetStarRating(
                    model=model,
                    stars=stars,
                    category=category,
                    price_band=price_band,
                    source_url=NSW_HELMET_STAR_URL,
                )
            )

    return ratings


def fetch_nsw_helmet_star_ratings(
    *,
    on_progress: Callable[[str], None] | None = None,
) -> list[NswHelmetStarRating]:
    with make_client(browser=True) as client:
        if on_progress:
            on_progress(NSW_HELMET_STAR_URL)
        response = client.get(NSW_HELMET_STAR_URL)
        response.raise_for_status()
        return parse_nsw_html(response.text)


def nsw_to_dict(rating: NswHelmetStarRating) -> dict:
    return {
        "model": rating.model,
        "stars": rating.stars,
        "category": rating.category,
        "price_band": rating.price_band,
        "url": rating.source_url,
    }
