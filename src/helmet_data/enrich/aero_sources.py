"""Aerodynamic test sources, per-source ranks, and fused aero scores."""

from typing import Any

AERO_SOURCES: dict[str, dict[str, Any]] = {
    "cyclingnews_sseh_2025": {
        "label": "Cyclingnews SSEH 2025",
        "short": "CN 2025",
        "family": "cyclingnews_sseh",
        "confidence": 1.0,
        "test_year": "2025",
        "url": (
            "https://www.cyclingnews.com/features/"
            "wind-tunnel-tested-the-worlds-biggest-aero-helmet-grouptest/"
        ),
        "metric_key": "watts_saved",
        "lower_is_better": False,
        "display_metric": "watts_saved",
        "display_suffix": "W vs Powerdome",
    },
    "cyclingnews_sseh_2024": {
        "label": "Cyclingnews SSEH 2024",
        "short": "CN 2024",
        "family": "cyclingnews_sseh",
        "confidence": 0.85,
        "test_year": "2024",
        "url": (
            "https://www.cyclingnews.com/features/"
            "wind-tunnel-tested-which-aero-road-bike-helmets-are-the-fastest/"
        ),
        "metric_key": "rank_score",
        "lower_is_better": False,
        "display_metric": "watts_saved_vs_slowest",
        "display_suffix": "W vs slowest in test",
    },
}

# Legacy aliases
AERO_SOURCE_KEY = "cyclingnews_sseh_2025"
AERO_SOURCE_URL = AERO_SOURCES[AERO_SOURCE_KEY]["url"]

AERO_TIERS: list[dict[str, Any]] = [
    {"key": "elite", "label": "Elite", "min_rank_pct": 0.85},
    {"key": "strong", "label": "Strong", "min_rank_pct": 0.65},
    {"key": "moderate", "label": "Moderate", "min_rank_pct": 0.45},
    {"key": "neutral", "label": "Neutral", "min_rank_pct": 0.25},
    {"key": "draggy", "label": "Draggy", "min_rank_pct": None},
]

TIER_ORDER = [tier["key"] for tier in AERO_TIERS]


def aero_tier_for_rank_pct(rank_pct: float) -> str:
    if rank_pct >= 0.85:
        return "elite"
    if rank_pct >= 0.65:
        return "strong"
    if rank_pct >= 0.45:
        return "moderate"
    if rank_pct >= 0.25:
        return "neutral"
    return "draggy"


def aero_tier_for_watts(watts_saved: float) -> str:
    """Legacy watts-based tiers (2025 CN scale vs vented baseline)."""
    if watts_saved >= 7.0:
        return "elite"
    if watts_saved >= 4.0:
        return "strong"
    if watts_saved >= 2.0:
        return "moderate"
    if watts_saved >= 0.0:
        return "neutral"
    return "draggy"


def aero_tiers_for_filters() -> list[dict[str, Any]]:
    return [{"key": tier["key"], "label": tier["label"]} for tier in AERO_TIERS]


def aero_sources_for_filters() -> list[dict[str, Any]]:
    return [
        {"key": key, "label": meta["label"], "short": meta["short"], "confidence": meta["confidence"]}
        for key, meta in AERO_SOURCES.items()
    ]


def compute_rank_score_for_entry(entry: dict[str, Any], meta: dict[str, Any]) -> float | None:
    """Canonical within-test score (higher = faster)."""
    if entry.get("watts_saved") is not None:
        return float(entry["watts_saved"])
    if entry.get("watts_saved_vs_slowest") is not None:
        return float(entry["watts_saved_vs_slowest"])
    drag = entry.get("drag_watts_40kph")
    slowest = meta.get("slowest_drag_watts_40kph")
    if drag is not None and slowest is not None:
        return round(float(slowest) - float(drag), 4)
    cda = entry.get("cda_avg")
    if cda is not None:
        return round(-float(cda), 6)
    return None


def apply_source_rank_percentiles(
    entries: list[dict[str, Any]],
    source_key: str,
    meta: dict[str, Any],
) -> None:
    from .ratings import compute_rank_percentiles

    source_meta = AERO_SOURCES[source_key]
    metric_key = source_meta["metric_key"]
    lower_is_better = source_meta["lower_is_better"]

    scored: list[tuple[str, float]] = []
    for entry in entries:
        if metric_key == "rank_score":
            value = compute_rank_score_for_entry(entry, meta)
            if value is not None:
                entry["rank_score"] = value
        else:
            value = entry.get(metric_key)
        if value is None:
            continue
        entry_id = entry.get("id") or f"{entry.get('brand')}-{entry.get('model')}"
        scored.append((entry_id, float(value)))

    percentiles = compute_rank_percentiles(scored, lower_is_better=lower_is_better)
    for entry in entries:
        entry_id = entry.get("id") or f"{entry.get('brand')}-{entry.get('model')}"
        if entry_id in percentiles:
            entry["rank_pct"] = round(percentiles[entry_id], 4)


def aero_source_family(source_key: str) -> str:
    return AERO_SOURCES.get(source_key, {}).get("family", source_key)


def select_latest_blocks_per_family(
    blocks: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """When one publisher has multiple test years, keep the newest year only."""
    grouped: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for key, block in blocks.items():
        if key not in AERO_SOURCES:
            continue
        grouped.setdefault(aero_source_family(key), []).append((key, block))

    selected: dict[str, dict[str, Any]] = {}
    for items in grouped.values():
        best_key, best_block = max(
            items,
            key=lambda item: (
                int(AERO_SOURCES[item[0]].get("test_year") or 0),
                float(AERO_SOURCES[item[0]].get("confidence", 0)),
            ),
        )
        selected[best_key] = best_block
    return selected


def fuse_aero_source_blocks(blocks: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    blocks = select_latest_blocks_per_family(blocks)
    eligible: list[tuple[str, float, float]] = []
    for key, block in blocks.items():
        if key not in AERO_SOURCES:
            continue
        rank_pct = block.get("rank_pct")
        if rank_pct is None:
            continue
        eligible.append((key, float(rank_pct), float(AERO_SOURCES[key]["confidence"])))

    if not eligible:
        return None

    total_weight = sum(weight for _, _, weight in eligible)
    fused_rank = sum(rank * weight for _, rank, weight in eligible) / total_weight
    return {
        "rank_pct": round(fused_rank, 4),
        "score": round(fused_rank * 100),
        "sources": [key for key, _, _ in eligible],
        "weights": {key: weight for key, _, weight in eligible},
    }


def finalize_helmet_aero(helmet: dict[str, Any]) -> None:
    aero = helmet.get("aero")
    if not aero:
        return

    sources = aero.get("sources") or {}
    active_sources = select_latest_blocks_per_family(sources)
    fused = fuse_aero_source_blocks(sources)
    if fused:
        aero["fused"] = fused
        aero["rank_pct"] = fused["rank_pct"]
        aero["score"] = fused["score"]
        aero["tier"] = aero_tier_for_rank_pct(fused["rank_pct"])
    elif active_sources:
        best_key = max(
            active_sources,
            key=lambda key: (
                int(AERO_SOURCES.get(key, {}).get("test_year") or 0),
                AERO_SOURCES.get(key, {}).get("confidence", 0),
                active_sources[key].get("rank_pct") or 0,
            ),
        )
        block = active_sources[best_key]
        if block.get("rank_pct") is not None:
            aero["rank_pct"] = block["rank_pct"]
            aero["score"] = round(block["rank_pct"] * 100)
            aero["tier"] = aero_tier_for_rank_pct(block["rank_pct"])

    display_block = _best_display_block(active_sources)
    if display_block:
        metric = display_block.get("watts_saved")
        if metric is None:
            metric = display_block.get("watts_saved_vs_slowest")
        if metric is not None:
            aero["watts_saved"] = metric
        if display_block.get("drag_watts_40kph") is not None:
            aero["drag_watts"] = display_block["drag_watts_40kph"]
        if display_block.get("cda_avg") is not None:
            aero["weighted_cda_m2"] = display_block["cda_avg"]

    active_keys = list(active_sources.keys())
    if active_keys:
        aero["source"] = active_keys[0] if len(active_keys) == 1 else "fused"
        aero["source_keys"] = active_keys


def _best_display_block(sources: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    if not sources:
        return None
    best_key = max(
        sources,
        key=lambda key: (
            int(AERO_SOURCES.get(key, {}).get("test_year") or 0),
            float(AERO_SOURCES.get(key, {}).get("confidence", 0)),
        ),
    )
    return sources[best_key]


def finalize_all_aero(helmets: list[dict]) -> None:
    for helmet in helmets:
        finalize_helmet_aero(helmet)
