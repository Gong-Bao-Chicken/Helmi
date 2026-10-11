"""Crawl real helmet ratings from CERTIMOOV, Folksam, and NSW Helmet STAR."""

import json
from datetime import UTC, datetime
from pathlib import Path

from ..crawlers.certimoov import certimoov_to_dict, fetch_certimoov_ratings
from ..crawlers.folksam import fetch_folksam_ratings, folksam_to_dict
from ..crawlers.nsw_helmet_star import fetch_nsw_helmet_star_ratings, nsw_to_dict
from ..enrich.matching import HelmetMatch, match_certimoov, match_folksam, match_nsw
from ..enrich.ratings import compute_rank_percentiles
from ..paths import EXTRA_RATINGS_PATH, EXTRA_RATINGS_RAW_PATH, HELMETS_JSON_PATH

DEFAULT_HELMETS = HELMETS_JSON_PATH
DEFAULT_OUTPUT = EXTRA_RATINGS_PATH
DEFAULT_RAW_OUTPUT = EXTRA_RATINGS_RAW_PATH
ALL_SOURCES = ("certimoov", "folksam", "nsw_helmet_star")


def load_helmets(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("helmets", [])


def attach_rank_percentiles(
    entries: list[dict],
    source_key: str,
    *,
    lower_is_better: bool,
    score_key: str = "score",
) -> None:
    scored = [
        (entry, float(entry["ratings"][source_key][score_key]))
        for entry in entries
        if entry.get("ratings", {}).get(source_key, {}).get(score_key) is not None
    ]
    ranks = compute_rank_percentiles(
        [(entry["id"], value) for entry, value in scored],
        lower_is_better=lower_is_better,
    )
    for entry, _ in scored:
        entry["ratings"][source_key]["rank_pct"] = ranks.get(entry["id"])


def attach_folksam_percentiles(entries: list[dict]) -> None:
    scored = [
        (entry, float(entry["ratings"]["folksam"]["overall_result_pct"]))
        for entry in entries
        if entry.get("ratings", {}).get("folksam", {}).get("overall_result_pct") is not None
    ]
    ranks = compute_rank_percentiles(
        [(entry["id"], value) for entry, value in scored],
        lower_is_better=False,
    )
    for entry, _ in scored:
        entry["ratings"]["folksam"]["rank_pct"] = ranks.get(entry["id"])


def attach_star_percentiles(entries: list[dict], source_key: str) -> None:
    scored = [
        (entry, float(entry["ratings"][source_key]["stars"]))
        for entry in entries
        if entry.get("ratings", {}).get(source_key, {}).get("stars") is not None
    ]
    ranks = compute_rank_percentiles(
        [(entry["id"], value) for entry, value in scored],
        lower_is_better=False,
    )
    for entry, _ in scored:
        entry["ratings"][source_key]["rank_pct"] = ranks.get(entry["id"])


def _certimoov_block(payload: dict) -> dict:
    return {
        "score": payload["score"],
        "stars": payload["stars"],
        "test_year": payload["test_year"],
        "url": payload["url"],
        "impact_scores": payload["impact_scores"],
    }


def _folksam_block(payload: dict) -> dict:
    return {
        "recommended": payload["recommended"],
        "overall_result_pct": payload["overall_result_pct"],
        "grade": payload["grade"],
        "segment": payload["segment"],
        "test_year": payload["test_year"],
        "url": payload["url"],
    }


def load_previous(output: Path, raw_output: Path) -> dict:
    """Previous crawl results (merged matches + raw unmatched) used as per-source fallback."""
    previous: dict = {"meta": {}, "matches": [], "unmatched": []}
    for path, keys in ((output, ("meta", "matches")), (raw_output, ("unmatched",))):
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"  warning: could not read previous ratings cache {path}: {exc}")
            continue
        for key in keys:
            previous[key] = data.get(key, previous[key])
    return previous


def build_matches(
    helmets: list[dict],
    *,
    sources: list[str] | tuple[str, ...] = ALL_SOURCES,
    certimoov_limit: int | None = None,
    folksam_year: int = 2025,
    nsw_year: int = 2025,
    delay: float = 0.25,
    previous: dict | None = None,
) -> tuple[list[dict], list[dict], dict]:
    """Crawl each source and match it to helmets.

    A failing source never aborts the run: its entries from ``previous`` (the last
    successful crawl) are reused and its stats get ``error`` / ``stale: true``.
    """
    previous = previous or {}
    by_id: dict[str, dict] = {}
    unmatched: list[dict] = []
    stats: dict[str, dict] = {}

    def ensure_entry(match) -> dict:
        if match.helmet_id not in by_id:
            by_id[match.helmet_id] = {
                "id": match.helmet_id,
                "match": {
                    "brand": match.brand,
                    "model": match.model,
                    "confidence": round(match.confidence, 3),
                    "method": match.method,
                },
                "ratings": {},
            }
        return by_id[match.helmet_id]

    def fetch_certimoov() -> list[tuple[dict, object, dict]]:
        print("Fetching CERTIMOOV bike helmets…")
        items = fetch_certimoov_ratings(
            limit=certimoov_limit,
            delay=delay,
            on_progress=lambda i, total, slug: print(f"  CERTIMOOV {i}/{total}: {slug}", flush=True),
        )
        rows = []
        for item in items:
            payload = certimoov_to_dict(item)
            rows.append((payload, match_certimoov(payload, helmets), _certimoov_block(payload)))
        return rows

    def fetch_folksam() -> list[tuple[dict, object, dict]]:
        print("Fetching Folksam PDF reports…")
        items = fetch_folksam_ratings(
            test_year=folksam_year,
            on_progress=lambda url: print(f"  Folksam PDF: {url}", flush=True),
        )
        rows = []
        for item in items:
            payload = folksam_to_dict(item)
            rows.append((payload, match_folksam(payload, helmets), _folksam_block(payload)))
        return rows

    def fetch_nsw() -> list[tuple[dict, object, dict]]:
        print("Fetching NSW Helmet STAR…")
        items = fetch_nsw_helmet_star_ratings(
            on_progress=lambda url: print(f"  NSW page: {url}", flush=True),
        )
        rows = []
        for item in items:
            payload = nsw_to_dict(item)
            block = {
                "stars": payload["stars"],
                "category": payload["category"],
                "price_band": payload["price_band"],
                "test_year": payload.get("test_year") or nsw_year,
                "url": payload["url"],
            }
            rows.append((payload, match_nsw(payload, helmets), block))
        return rows

    fetchers = {
        "certimoov": fetch_certimoov,
        "folksam": fetch_folksam,
        "nsw_helmet_star": fetch_nsw,
    }

    for source in ALL_SOURCES:
        if source not in sources:
            continue
        try:
            rows = fetchers[source]()
            if not rows:
                raise RuntimeError("no ratings returned (site layout changed?)")
        except Exception as exc:  # noqa: BLE001 - one broken lab must not abort the update
            stats[source] = _fallback_to_previous(source, exc, previous, ensure_entry, unmatched)
            continue
        matched = 0
        for payload, match, block in rows:
            if not match:
                unmatched.append({"source": source, **payload})
                continue
            ensure_entry(match)["ratings"][source] = block
            matched += 1
        stats[source] = {"fetched": len(rows), "matched": matched}

    matches = list(by_id.values())

    certimoov_entries = [entry for entry in matches if "certimoov" in entry["ratings"]]
    attach_rank_percentiles(certimoov_entries, "certimoov", lower_is_better=False, score_key="score")

    folksam_entries = [entry for entry in matches if "folksam" in entry["ratings"]]
    attach_folksam_percentiles(folksam_entries)

    nsw_entries = [entry for entry in matches if "nsw_helmet_star" in entry["ratings"]]
    attach_star_percentiles(nsw_entries, "nsw_helmet_star")

    return matches, unmatched, stats


def _fallback_to_previous(source, exc, previous, ensure_entry, unmatched) -> dict:
    error = f"{type(exc).__name__}: {exc}"
    print(
        f"\n  WARNING: {source} fetch failed ({error}).\n"
        f"  Falling back to previously cached {source} ratings.\n",
        flush=True,
    )
    reused = 0
    for entry in previous.get("matches", []):
        block = entry.get("ratings", {}).get(source)
        if block is None:
            continue
        info = entry.get("match", {})
        cached_match = HelmetMatch(
            helmet_id=entry["id"],
            brand=info.get("brand", ""),
            model=info.get("model", ""),
            confidence=info.get("confidence", 0.0),
            method=info.get("method", "cached"),
        )
        ensure_entry(cached_match)["ratings"][source] = dict(block)
        reused += 1
    reused_unmatched = [u for u in previous.get("unmatched", []) if u.get("source") == source]
    unmatched.extend(reused_unmatched)

    prev_stats = previous.get("meta", {}).get("sources", {}).get(source, {})
    stale_since = (
        prev_stats.get("stale_since")
        if prev_stats.get("stale")
        else previous.get("meta", {}).get("generated_at")
    )
    return {
        "fetched": prev_stats.get("fetched", reused + len(reused_unmatched)),
        "matched": reused,
        "error": error,
        "stale": True,
        "stale_since": stale_since,
    }


def write_output(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_fetch_extra_ratings(
    *,
    helmets_path: Path = DEFAULT_HELMETS,
    output: Path = DEFAULT_OUTPUT,
    raw_output: Path = DEFAULT_RAW_OUTPUT,
    sources: list[str] | tuple[str, ...] = ALL_SOURCES,
    certimoov_limit: int | None = None,
    folksam_year: int = 2025,
    nsw_year: int = 2025,
    delay: float = 0.25,
) -> None:
    """Crawl CERTIMOOV, Folksam and NSW Helmet STAR and match them to helmets.json."""
    helmets = load_helmets(helmets_path)
    if not helmets:
        raise SystemExit(f"No helmets found at {helmets_path}. Run `helmet-data build` first.")

    previous = load_previous(output, raw_output)
    matches, unmatched, stats = build_matches(
        helmets,
        previous=previous,
        sources=sources,
        certimoov_limit=certimoov_limit,
        folksam_year=folksam_year,
        nsw_year=nsw_year,
        delay=delay,
    )
    generated_at = datetime.now(UTC).isoformat()

    merged_payload = {
        "meta": {
            "generated_at": generated_at,
            "sources": stats,
            "match_count": len(matches),
            "unmatched_count": len(unmatched),
        },
        "matches": matches,
    }
    write_output(output, merged_payload)

    raw_payload = {
        **merged_payload,
        "unmatched": unmatched,
    }
    write_output(raw_output, raw_payload)

    print(f"\nWrote {len(matches)} matched helmets to {output}")
    print(f"Unmatched entries: {len(unmatched)} (see {raw_output})")
    for source, info in stats.items():
        line = f"  {source}: fetched {info['fetched']}, matched {info['matched']}"
        if info.get("stale"):
            line += f"  [STALE - fetch failed: {info['error']}; reused cached entries]"
        print(line)
    print("\nNext: helmet-data build")
