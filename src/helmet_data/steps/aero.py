"""Fetch Cyclingnews Labs aero helmet data and refresh data/reference/aero_ratings.json."""

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup

from ..enrich.aero import DEFAULT_AERO_RATINGS, load_aero_ratings, merge_aero_ratings
from ..enrich.aero_sources import AERO_SOURCES, apply_source_rank_percentiles
from ..paths import HELMETS_JSON_PATH

DEFAULT_HELMETS = HELMETS_JSON_PATH
USER_AGENT = "LidWiser/0.1 (+https://github.com/Gong-Bao-Chicken/LidWiser; research prototype)"

CN_2025_URL = AERO_SOURCES["cyclingnews_sseh_2025"]["url"]
CN_2024_URL = AERO_SOURCES["cyclingnews_sseh_2024"]["url"]

NUM_RE = re.compile(r"[-\d.]+")


def _normalize_name(text: str) -> str:
    text = re.sub(r"^\d+\.\s*", "", text.strip().lower())
    text = text.replace("s-works", "s works").replace("iii", "3").replace("ii", "2")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _entry_match_key(entry: dict[str, Any]) -> str:
    parts = [entry.get("brand", ""), entry.get("model", "")]
    variant = (entry.get("variant") or "").lower()
    if variant:
        parts.append(variant.replace("with", "w").replace("without", "w out"))
    return _normalize_name(" ".join(parts))


def _row_match_key(helmet_cell: str) -> str:
    text = helmet_cell.strip()
    text = re.sub(r"\([^)]*\)", lambda m: m.group(0).replace("without", "w out").replace("with", "w"), text)
    return _normalize_name(text)


def _parse_float(cell: str) -> float | None:
    match = NUM_RE.search(cell.replace(",", ""))
    if not match:
        return None
    return float(match.group())


def _first_data_table(soup: BeautifulSoup):
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) >= 5:
            return table
    return None


def _match_entries_to_rows(
    entries: list[dict[str, Any]],
    rows: list[list[str]],
) -> dict[str, list[str]]:
    by_key: dict[str, dict[str, Any]] = {}
    for entry in entries:
        by_key[_entry_match_key(entry)] = entry

    mapping: dict[str, list[str]] = {}
    for row in rows:
        if not row:
            continue
        row_key = _row_match_key(row[0])
        if row_key in by_key:
            mapping[by_key[row_key]["id"]] = row
            continue
        brand_model = row_key
        for entry in entries:
            entry_key = _entry_match_key(entry)
            if entry_key in brand_model or brand_model in entry_key:
                mapping[entry["id"]] = row
                break
    return mapping


def parse_2024_html(html: str, entries: list[dict[str, Any]]) -> int:
    soup = BeautifulSoup(html, "html.parser")
    table = _first_data_table(soup)
    if not table:
        return 0

    rows: list[list[str]] = []
    for tr in table.find_all("tr")[1:]:
        cells = [td.get_text(" ", strip=True) for td in tr.find_all(["th", "td"])]
        if cells and cells[0]:
            rows.append(cells)

    mapping = _match_entries_to_rows(entries, rows)
    updated = 0
    for entry in entries:
        row = mapping.get(entry["id"])
        if not row or len(row) < 3:
            continue
        cda = _parse_float(row[1])
        drag = _parse_float(row[2])
        if cda is not None:
            entry["cda_avg"] = cda
        if drag is not None:
            entry["drag_watts_40kph"] = drag
        if cda is not None or drag is not None:
            updated += 1
    return updated


def parse_2025_html(html: str, entries: list[dict[str, Any]]) -> int:
    soup = BeautifulSoup(html, "html.parser")
    table = _first_data_table(soup)
    if not table:
        return 0

    rows: list[list[str]] = []
    for tr in table.find_all("tr")[1:]:
        cells = [td.get_text(" ", strip=True) for td in tr.find_all(["th", "td"])]
        if cells and cells[0]:
            rows.append(cells)

    mapping = _match_entries_to_rows(entries, rows)
    updated = 0
    for entry in entries:
        row = mapping.get(entry["id"])
        if not row or len(row) < 3:
            continue
        drag = _parse_float(row[1])
        watts = _parse_float(row[2])
        if drag is not None:
            entry["drag_watts"] = drag
        if watts is not None:
            entry["watts_saved"] = watts
        if drag is not None or watts is not None:
            updated += 1
    return updated


def _load_tests(path: Path) -> dict[str, Any]:
    data = load_aero_ratings(path)
    if "tests" in data:
        return data
    return {
        "meta": data.get("meta", {}),
        "tests": [{"meta": data.get("meta", {}), "entries": data.get("entries", [])}],
    }


def _find_test(data: dict[str, Any], source_key: str) -> dict[str, Any] | None:
    for test in data.get("tests", []):
        if test.get("meta", {}).get("source") == source_key:
            return test
    return None


def _validate_2024_entries(entries: list[dict[str, Any]], parsed_count: int) -> bool:
    return parsed_count >= max(10, len(entries) // 2)


def _validate_2025_entries(entries: list[dict[str, Any]], parsed_count: int) -> bool:
    return parsed_count >= max(10, len(entries) // 2)


def refresh_derived_fields(data: dict[str, Any]) -> None:
    for test in data.get("tests", []):
        meta = test.get("meta", {})
        source_key = meta.get("source")
        if not source_key:
            continue
        entries = test.get("entries", [])
        if source_key == "cyclingnews_sseh_2024":
            drags = [
                entry.get("drag_watts_40kph")
                for entry in entries
                if entry.get("drag_watts_40kph") is not None
            ]
            if drags:
                slowest = max(drags)
                meta["slowest_drag_watts_40kph"] = slowest
                for entry in entries:
                    drag = entry.get("drag_watts_40kph")
                    if drag is not None:
                        entry["watts_saved_vs_slowest"] = round(slowest - float(drag), 2)
        apply_source_rank_percentiles(entries, source_key, meta)


def fetch_cn_labs(path: Path, *, timeout: float = 30.0) -> dict[str, Any]:
    data = _load_tests(path)
    data.setdefault("meta", {})
    fetched_at = datetime.now(UTC).isoformat()
    notes: list[str] = []

    with httpx.Client(timeout=timeout, headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
        for source_key, url in (
            ("cyclingnews_sseh_2025", CN_2025_URL),
            ("cyclingnews_sseh_2024", CN_2024_URL),
        ):
            test = _find_test(data, source_key)
            if not test:
                notes.append(f"missing test block for {source_key}")
                continue
            entries = test.get("entries", [])
            try:
                response = client.get(url)
                response.raise_for_status()
                html = response.text
            except httpx.HTTPError as exc:
                notes.append(f"{source_key}: fetch failed ({exc})")
                continue

            if source_key == "cyclingnews_sseh_2024":
                parsed = parse_2024_html(html, entries)
                if not _validate_2024_entries(entries, parsed):
                    notes.append(
                        f"{source_key}: parsed only {parsed}/{len(entries)} rows; kept curated values"
                    )
                else:
                    notes.append(f"{source_key}: refreshed {parsed} entries from CN Labs")
            else:
                parsed = parse_2025_html(html, entries)
                if not _validate_2025_entries(entries, parsed):
                    notes.append(
                        f"{source_key}: parsed only {parsed}/{len(entries)} rows; kept curated values"
                    )
                else:
                    notes.append(f"{source_key}: refreshed {parsed} entries from CN Labs")

    refresh_derived_fields(data)
    data["meta"]["fetched_at"] = fetched_at
    data["meta"]["fetch_notes"] = notes
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return data


def run_fetch_aero(
    *,
    output: Path = DEFAULT_AERO_RATINGS,
    helmets_path: Path = DEFAULT_HELMETS,
    fetch: bool = False,
) -> None:
    """Optionally refresh aero_ratings.json from CN Labs, then report how it maps onto helmets.json."""
    if fetch:
        fetch_cn_labs(output)
        print(f"Updated {output}")
        for note in load_aero_ratings(output).get("meta", {}).get("fetch_notes", []):
            print(f"  - {note}")

    if not helmets_path.exists():
        print(f"No helmets file at {helmets_path}; skipping match report")
        return

    helmets = json.loads(helmets_path.read_text(encoding="utf-8")).get("helmets", [])
    for helmet in helmets:
        helmet.pop("aero", None)

    stats = merge_aero_ratings(helmets, load_aero_ratings(output))
    print(
        f"Aero coverage: {stats['helmets_with_aero']} helmets, "
        f"{stats['matched']} source matches, {stats['extra_added']} catalog stubs added"
    )
    for source_key, source_stats in stats.get("by_source", {}).items():
        print(f"  {source_key}: {source_stats['matched']}/{source_stats['entries']} matched")
    if stats.get("unmatched_names"):
        print("Unmatched without stub:")
        for name in stats["unmatched_names"]:
            print(f"  - {name}")
