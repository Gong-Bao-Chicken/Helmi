#!/usr/bin/env python3
"""Crawl real helmet ratings from CERTIMOOV, Folksam, and NSW Helmet STAR."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from crawlers.certimoov import certimoov_to_dict, fetch_certimoov_ratings
from crawlers.folksam import folksam_to_dict, fetch_folksam_ratings
from crawlers.nsw_helmet_star import fetch_nsw_helmet_star_ratings, nsw_to_dict
from helmet_match import match_certimoov, match_folksam, match_nsw
from rating_sources import compute_rank_percentiles

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_HELMETS = REPO_ROOT / "web" / "data" / "helmets.json"
DEFAULT_OUTPUT = SCRIPT_DIR / "extra_ratings.json"
DEFAULT_RAW_OUTPUT = SCRIPT_DIR / "extra_ratings_raw.json"


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


def build_matches(helmets: list[dict], args: argparse.Namespace) -> tuple[list[dict], list[dict], dict]:
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

    if "certimoov" in args.sources:
        print("Fetching CERTIMOOV bike helmets…")
        certimoov = fetch_certimoov_ratings(
            limit=args.certimoov_limit,
            delay=args.delay,
            on_progress=lambda i, total, slug: print(f"  CERTIMOOV {i}/{total}: {slug}", flush=True),
        )
        matched = 0
        for item in certimoov:
            payload = certimoov_to_dict(item)
            match = match_certimoov(payload, helmets)
            if not match:
                unmatched.append({"source": "certimoov", **payload})
                continue
            entry = ensure_entry(match)
            entry["ratings"]["certimoov"] = {
                "score": payload["score"],
                "stars": payload["stars"],
                "test_year": payload["test_year"],
                "url": payload["url"],
                "impact_scores": payload["impact_scores"],
            }
            matched += 1
        stats["certimoov"] = {"fetched": len(certimoov), "matched": matched}

    if "folksam" in args.sources:
        print("Fetching Folksam PDF reports…")
        folksam = fetch_folksam_ratings(
            test_year=args.folksam_year,
            on_progress=lambda url: print(f"  Folksam PDF: {url}", flush=True),
        )
        matched = 0
        for item in folksam:
            payload = folksam_to_dict(item)
            match = match_folksam(payload, helmets)
            if not match:
                unmatched.append({"source": "folksam", **payload})
                continue
            entry = ensure_entry(match)
            entry["ratings"]["folksam"] = {
                "recommended": payload["recommended"],
                "overall_result_pct": payload["overall_result_pct"],
                "grade": payload["grade"],
                "segment": payload["segment"],
                "test_year": payload["test_year"],
                "url": payload["url"],
            }
            matched += 1
        stats["folksam"] = {"fetched": len(folksam), "matched": matched}

    if "nsw_helmet_star" in args.sources:
        print("Fetching NSW Helmet STAR…")
        nsw = fetch_nsw_helmet_star_ratings(
            on_progress=lambda url: print(f"  NSW page: {url}", flush=True),
        )
        matched = 0
        for item in nsw:
            payload = nsw_to_dict(item)
            match = match_nsw(payload, helmets)
            if not match:
                unmatched.append({"source": "nsw_helmet_star", **payload})
                continue
            entry = ensure_entry(match)
            entry["ratings"]["nsw_helmet_star"] = {
                "stars": payload["stars"],
                "category": payload["category"],
                "price_band": payload["price_band"],
                "test_year": args.nsw_year,
                "url": payload["url"],
            }
            matched += 1
        stats["nsw_helmet_star"] = {"fetched": len(nsw), "matched": matched}

    matches = list(by_id.values())

    certimoov_entries = [entry for entry in matches if "certimoov" in entry["ratings"]]
    attach_rank_percentiles(certimoov_entries, "certimoov", lower_is_better=False, score_key="score")

    folksam_entries = [entry for entry in matches if "folksam" in entry["ratings"]]
    attach_folksam_percentiles(folksam_entries)

    nsw_entries = [entry for entry in matches if "nsw_helmet_star" in entry["ratings"]]
    attach_star_percentiles(nsw_entries, "nsw_helmet_star")

    return matches, unmatched, stats


def write_output(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--helmets",
        type=Path,
        default=DEFAULT_HELMETS,
        help="VT helmets.json used for matching (default: web/data/helmets.json)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Merged match output for fetch_helmets.py",
    )
    parser.add_argument(
        "--raw-output",
        type=Path,
        default=DEFAULT_RAW_OUTPUT,
        help="Optional full crawl + unmatched report",
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=["certimoov", "folksam", "nsw_helmet_star"],
        default=["certimoov", "folksam", "nsw_helmet_star"],
    )
    parser.add_argument("--certimoov-limit", type=int, default=None)
    parser.add_argument("--folksam-year", type=int, default=2025)
    parser.add_argument("--nsw-year", type=int, default=2025)
    parser.add_argument("--delay", type=float, default=0.25)
    args = parser.parse_args()

    helmets = load_helmets(args.helmets)
    if not helmets:
        raise SystemExit(
            f"No helmets found at {args.helmets}. Run scripts/fetch_helmets.py first."
        )

    matches, unmatched, stats = build_matches(helmets, args)
    generated_at = datetime.now(timezone.utc).isoformat()

    merged_payload = {
        "meta": {
            "generated_at": generated_at,
            "sources": stats,
            "match_count": len(matches),
            "unmatched_count": len(unmatched),
        },
        "matches": matches,
    }
    write_output(args.output, merged_payload)

    raw_payload = {
        **merged_payload,
        "unmatched": unmatched,
    }
    write_output(args.raw_output, raw_payload)

    print(f"\nWrote {len(matches)} matched helmets to {args.output}")
    print(f"Unmatched entries: {len(unmatched)} (see {args.raw_output})")
    for source, info in stats.items():
        print(f"  {source}: fetched {info['fetched']}, matched {info['matched']}")
    print("\nNext: python scripts/fetch_helmets.py")


if __name__ == "__main__":
    main()
