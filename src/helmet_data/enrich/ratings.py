"""Rating source definitions, percentile ranks, and multi-source fusion."""

from typing import Any

RATING_SOURCES: dict[str, dict[str, Any]] = {
    "virginia_tech": {
        "label": "Virginia Tech",
        "short": "VT",
        "confidence": 1.0,
        "lower_score_is_better": True,
        "score_key": "score",
        "url": "https://www.helmet.beam.vt.edu/bicycle-helmet-ratings.html",
    },
    "folksam": {
        "label": "Folksam",
        "short": "Folksam",
        "confidence": 0.9,
        "lower_score_is_better": False,
        "rank_key": "overall_result_pct",
        "recommended_key": "recommended",
        "stars_key": "stars",
        "url": "https://www.folksam.se/",
    },
    "certimoov": {
        "label": "CERTIMOOV",
        "short": "CERTIMOOV",
        "confidence": 0.85,
        "lower_score_is_better": False,
        "score_key": "score",
        "stars_key": "stars",
        "url": "https://www.certimoov.com/",
    },
    "nsw_helmet_star": {
        "label": "NSW Helmet STAR",
        "short": "NSW",
        "confidence": 0.85,
        "lower_score_is_better": False,
        "stars_key": "stars",
        "url": "https://www.transport.nsw.gov.au/roadsafety/bicycle-riders/helmet-star",
    },
    "hiper": {
        "label": "Hiper",
        "short": "Hiper",
        "confidence": 0.7,
        "lower_score_is_better": False,
        "stars_key": "stars",
        "url": "https://www.hiperhelmets.org/",
    },
}


def rating_sources_for_filters() -> list[dict[str, Any]]:
    return [
        {"key": key, **{k: v for k, v in meta.items() if k != "url"}} for key, meta in RATING_SOURCES.items()
    ]


def compute_min_max_norm(
    entries: list[tuple[Any, float]],
    *,
    lower_is_better: bool,
) -> dict[Any, float]:
    """Map entry id -> min-max normalized value in [0, 1] (1 = safest)."""
    if not entries:
        return {}

    values = [value for _, value in entries]
    min_v = min(values)
    max_v = max(values)
    if min_v == max_v:
        return {entry_id: 1.0 for entry_id, _ in entries}

    ranks: dict[Any, float] = {}
    for entry_id, value in entries:
        if lower_is_better:
            ranks[entry_id] = (max_v - value) / (max_v - min_v)
        else:
            ranks[entry_id] = (value - min_v) / (max_v - min_v)
    return ranks


def compute_rank_percentiles(
    entries: list[tuple[Any, float]],
    *,
    lower_is_better: bool,
) -> dict[Any, float]:
    """Map entry id -> percentile rank in [0, 1] (1 = safest). Tied scores share a rank."""
    if not entries:
        return {}

    ordered = sorted(entries, key=lambda item: item[1], reverse=not lower_is_better)
    n = len(ordered)
    if n == 1:
        return {ordered[0][0]: 1.0}

    ranks: dict[Any, float] = {}
    index = 0
    while index < n:
        value = ordered[index][1]
        end = index
        while end < n and ordered[end][1] == value:
            end += 1
        avg_rank = sum((n - 1 - position) / (n - 1) for position in range(index, end)) / (end - index)
        for position in range(index, end):
            ranks[ordered[position][0]] = avg_rank
        index = end
    return ranks


def source_rank_field(meta: dict[str, Any]) -> str | None:
    return meta.get("rank_key") or meta.get("score_key") or meta.get("stars_key")


def apply_source_percentiles(helmets: list[dict], source_key: str) -> None:
    meta = RATING_SOURCES[source_key]
    rank_field = source_rank_field(meta)
    if not rank_field:
        return

    scored: list[tuple[str, float]] = []
    for helmet in helmets:
        rating = helmet.get("ratings", {}).get(source_key)
        if not rating or rating.get(rank_field) is None:
            continue
        scored.append((helmet["id"], float(rating[rank_field])))

    lower_is_better = meta["lower_score_is_better"]
    percentiles = compute_rank_percentiles(scored, lower_is_better=lower_is_better)
    norms = (
        compute_min_max_norm(scored, lower_is_better=lower_is_better) if source_key == "virginia_tech" else {}
    )
    for helmet in helmets:
        rating = helmet.get("ratings", {}).get(source_key)
        if not rating:
            continue
        if helmet["id"] in percentiles:
            rating["rank_pct"] = round(percentiles[helmet["id"]], 4)
        if helmet["id"] in norms:
            rating["score_norm"] = round(norms[helmet["id"]], 4)


def vt_rating_block(
    *,
    score: float,
    test_year: str | None,
    score_low: float | None = None,
    score_high: float | None = None,
) -> dict[str, Any]:
    block: dict[str, Any] = {
        "score": score,
        "test_year": test_year,
        "rank_pct": None,
        "score_norm": None,
    }
    if score_low is not None:
        block["score_low_impact"] = score_low
    if score_high is not None:
        block["score_high_impact"] = score_high
    return block


def best_safety_rank_pct(ratings: dict[str, dict]) -> float | None:
    """Best available lab percentile (1 = safest)."""
    for key in ("virginia_tech", "fused"):
        block = ratings.get(key)
        if block and block.get("rank_pct") is not None:
            return float(block["rank_pct"])
    for key in RATING_SOURCES:
        block = ratings.get(key)
        if block and block.get("rank_pct") is not None:
            return float(block["rank_pct"])
    return None


def value_ratio_from_ratings(ratings: dict[str, dict], price_usd: float | None) -> float | None:
    """Safety percentile per USD (higher = better value)."""
    if price_usd is None or price_usd <= 0:
        return None
    rank = best_safety_rank_pct(ratings)
    if rank is None:
        return None
    return round(rank / price_usd, 6)


def fuse_ratings(
    ratings: dict[str, dict],
    source_keys: list[str],
) -> dict[str, Any] | None:
    eligible: list[tuple[str, float, float]] = []
    for key in source_keys:
        if key not in RATING_SOURCES:
            continue
        block = ratings.get(key)
        if not block or block.get("rank_pct") is None:
            continue
        confidence = RATING_SOURCES[key]["confidence"]
        eligible.append((key, float(block["rank_pct"]), confidence))

    if not eligible:
        return None

    total_weight = sum(weight for _, _, weight in eligible)
    fused = sum(rank * weight for _, rank, weight in eligible) / total_weight
    return {
        "rank_pct": round(fused, 4),
        "sources": [key for key, _, _ in eligible],
        "weights": {key: weight for key, _, weight in eligible},
    }


def finalize_helmet_ratings(helmet: dict) -> None:
    ratings = helmet.setdefault("ratings", {})
    available = [
        key for key in RATING_SOURCES if ratings.get(key) and ratings[key].get("rank_pct") is not None
    ]
    available.sort(key=lambda key: RATING_SOURCES[key]["confidence"], reverse=True)
    fused = fuse_ratings(ratings, available)
    if fused:
        ratings["fused"] = fused
    elif "fused" in ratings:
        del ratings["fused"]


def finalize_all_ratings(helmets: list[dict]) -> None:
    """Recompute lab safety percentiles on the full helmet pool, then fuse safety only."""
    for source_key in RATING_SOURCES:
        apply_source_percentiles(helmets, source_key)

    for helmet in helmets:
        finalize_helmet_ratings(helmet)


def merge_extra_ratings(helmets: list[dict], matches: list[dict]) -> int:
    by_id = {helmet["id"]: helmet for helmet in helmets}
    by_brand_model = {(helmet["brand"].lower(), helmet["model"].lower()): helmet for helmet in helmets}
    merged = 0

    for entry in matches:
        helmet: dict | None = None
        if "id" in entry:
            helmet = by_id.get(entry["id"])
        elif "match" in entry:
            match = entry["match"]
            helmet = by_brand_model.get((match["brand"].lower(), match["model"].lower()))

        if not helmet:
            continue

        ratings_block = helmet.setdefault("ratings", {})
        for source_key, payload in entry.get("ratings", {}).items():
            if source_key not in RATING_SOURCES:
                continue
            ratings_block[source_key] = {key: value for key, value in payload.items() if key != "rank_pct"}
            merged += 1

        for source_key in ("folksam", "certimoov"):
            block = ratings_block.get(source_key)
            if block and block.get("demo"):
                del block["demo"]

    return merged
