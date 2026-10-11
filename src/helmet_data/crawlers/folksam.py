import re
from collections.abc import Callable
from dataclasses import dataclass
from io import BytesIO

import httpx
from pypdf import PdfReader

from .common import CRAWLER_USER_AGENT, polite_sleep

FOLKSAM_PDF_URLS = {
    "adults_en": "https://www.folksam.se/media/S41586-cykelhjalmstest-2025-vuxen-eng_tcm5-84883.pdf",
    "children_en": "https://www.folksam.se/media/S41586-cykelhjalmstest-2025-barn-eng_tcm5-84884.pdf",
}


@dataclass
class FolksamRating:
    name: str
    overall_result_pct: float
    recommended: bool
    grade: int | None
    segment: str
    test_year: int
    source_url: str


def _parse_table3(text: str, segment: str, source_url: str, test_year: int) -> list[FolksamRating]:
    start = text.find("Table 3. Overall results")
    if start < 0:
        start = text.find("Tabell 3.")
    if start < 0:
        return []

    chunk = text[start : start + 3000]
    end = chunk.find("Table 4.")
    if end < 0:
        end = chunk.find("Tabell 4.")
    if end > 0:
        chunk = chunk[:end]

    ratings: list[FolksamRating] = []
    line_pattern = re.compile(r"^(?P<name>.+?)\s+(?P<pct>-?\d+)%\s*(?P<rest>.*)$")

    for line in chunk.splitlines():
        line = line.strip()
        if not line or line.startswith("*"):
            continue
        if line.startswith("Table ") or line.startswith("Tabell "):
            continue
        if "Overall result" in line or line.startswith(("Helmets ", "Child Helmets ")):
            continue
        if line.startswith("All helmets"):
            break

        match = line_pattern.match(line)
        if not match:
            continue

        name = re.sub(r"\s+", " ", match.group("name")).strip(" -")
        if len(name) > 80 or not name[0].isalpha():
            continue

        pct = float(match.group("pct"))
        rest = match.group("rest").strip()
        recommended = rest.startswith("Recommended")
        grade_match = re.search(r"\b([1-4])\b", rest)
        grade = int(grade_match.group(1)) if grade_match else None

        ratings.append(
            FolksamRating(
                name=name,
                overall_result_pct=pct,
                recommended=recommended,
                grade=grade,
                segment=segment,
                test_year=test_year,
                source_url=source_url,
            )
        )

    return ratings


def fetch_folksam_ratings(
    *,
    test_year: int = 2025,
    on_progress: Callable[[str], None] | None = None,
) -> list[FolksamRating]:
    ratings: list[FolksamRating] = []
    headers = {"User-Agent": CRAWLER_USER_AGENT}

    with httpx.Client(timeout=60.0, headers=headers, follow_redirects=True) as client:
        for key, url in FOLKSAM_PDF_URLS.items():
            if on_progress:
                on_progress(url)
            response = client.get(url)
            response.raise_for_status()
            reader = PdfReader(BytesIO(response.content))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            segment = "adults" if "vuxen" in key or "adult" in key else "children"
            ratings.extend(_parse_table3(text, segment, url, test_year))
            polite_sleep(0.2)

    return ratings


def folksam_to_dict(rating: FolksamRating) -> dict:
    return {
        "name": rating.name,
        "overall_result_pct": rating.overall_result_pct,
        "recommended": rating.recommended,
        "grade": rating.grade,
        "segment": rating.segment,
        "test_year": rating.test_year,
        "url": rating.source_url,
    }
