"""Match CN Labs aero wind-tunnel results to helmets and compute fused aero scores."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from aero_sources import (
    AERO_SOURCES,
    apply_source_rank_percentiles,
    finalize_all_aero,
)
from helmet_styles import infer_style
from helmet_match import HelmetMatch, _brand_candidates, _match_by_brand_model, _match_by_slug

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_AERO_RATINGS = SCRIPT_DIR / "aero_ratings.json"

HELMET_ID_HINTS: dict[str, str] = {
    "specialized-s-works-evade-3": "specialized-evade-3",
    "specialized-s-works-prevail-3": "specialized-prevail-3",
    "trek-ballista": "trek-ballista-mips",
    "abus-gamechanger-2-0": "abus-gamechanger-2-0-mips",
    "abus-gamechanger": "abus-gamechanger-2-0-mips",
    "lazer-vento-kineticore": "lazer-vento-kineticore",
    "lazer-z1-kineticore": "lazer-z1-kineticore",
    "sweet-protection-falconer": "sweet-protection-falconer-aero-2vi-mips",
    "sweet-protection-tucker-2vi": "sweet-protection-falconer-2vi-mips",
    "scott-cadence": "scott-cadence-plus-mips",
    "giro-aerohead": "giro-aerohead-mips",
    "met-manta": "met-manta-mips",
    "kask-protone-icon": "kask-protone",
    "hjc-ibex-3": "hjc-ibex",
    "hjc-furion-3": "hjc-furion",
    "rudy-project-nytron": "rudy-project-nytron",
    "rudy-project-nytron-pro": "rudy-project-nytron-pro",
    "giro-eclipse": "giro-eclipse-spherical",
    "giro-aries": "giro-aries-spherical",
    "trek-circuit-wavecel": "trek-circuit-wavecel",
    "trek-velocis": "trek-velocis-mips",
    "bell-xr-spherical": "bell-xr-spherical-mips",
    "poc-cytal-carbon": "poc-cytal-carbon",
    "poc-cytal": "poc-cytal",
    "poc-procen-air": "poc-procen-air",
    "poc-ventral": "poc-ventral-air",
    "poc-ventral-tempus": "poc-ventral-air",
    "fizik-kudo-aero": "fizik-kudo-aero",
    "kask-elemento": "kask-elemento",
    "specialized-propero-4": "specialized-propero-4",
    "specialized-search": "specialized-search",
    "giant-rev": "giant-rev-mips",
    "giant-rivet": "giant-rivet",
    "oakley-velo-mach": "extra-aero-oakley-velo-mach",
    "canyon-stingr": "extra-aero-canyon-stingr",
    "kask-nirvana": "extra-aero-kask-nirvana",
    "kask-utopia-y": "extra-aero-kask-utopia-y",
    "van-rysel-rcr-f": "extra-aero-van-rysel-rcr-f",
    "van-rysel-rcr": "extra-aero-van-rysel-rcr",
    "van-rysel-fcr": "extra-aero-van-rysel-fcr",
    "van-rysel-xcr-tt": "extra-aero-van-rysel-xcr-tt",
    "oakley-aro7": "extra-aero-oakley-aro7",
    "julbo-sprint": "extra-aero-julbo-sprint",
    "limar-air-atlas": "extra-aero-limar-air-atlas",
    "carnac-evo": "extra-aero-carnac-evo",
    "uvex-rise-pro": "extra-aero-uvex-rise-pro",
    "abus-stormchaser": "extra-aero-abus-stormchaser",
    "abus-airbreaker": "extra-aero-abus-airbreaker",
    "bell-falcon-xr": "extra-aero-bell-falcon-xr",
    "bell-xr-spherical-mips": "bell-xr-spherical-mips",
    "sunrimoon-sariel": "extra-aero-sunrimoon-sariel",
    "sunrimoon-alien": "extra-aero-sunrimoon-alien",
    "uvex-surge": "extra-aero-uvex-surge",
    "smith-network": "extra-aero-smith-network",
    "smith-trace": "extra-aero-smith-trace",
    "hjc-furion-3-mips": "hjc-furion",
}


def slugify(*parts: str) -> str:
    text = "-".join(parts).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def _normalize_class(raw: str) -> str:
    value = raw.strip().lower().replace("-", "_").replace(" ", "_")
    if value in ("time_trial", "tt"):
        return "time_trial"
    if value in ("semi_aero", "semiaero"):
        return "semi_aero"
    if value == "vented":
        return "vented"
    return "aero"


def _entry_slug(entry: dict[str, Any]) -> str:
    if entry.get("id"):
        return str(entry["id"])
    return slugify(entry.get("brand", ""), entry.get("model", ""))


def match_aero_entry(
    entry: dict[str, Any],
    helmets: list[dict],
    helmets_by_id: dict[str, dict],
    brand_candidates: list[str],
) -> HelmetMatch | None:
    hint_id = entry.get("helmet_id") or HELMET_ID_HINTS.get(_entry_slug(entry))
    if hint_id and hint_id in helmets_by_id:
        helmet = helmets_by_id[hint_id]
        return HelmetMatch(
            helmet_id=helmet["id"],
            brand=helmet["brand"],
            model=helmet["model"],
            confidence=1.0,
            method="hint",
        )

    by_slug = _match_by_slug(_entry_slug(entry), helmets_by_id)
    if by_slug:
        return by_slug

    return _match_by_brand_model(
        entry.get("brand", ""),
        entry.get("model", ""),
        helmets,
        brand_candidates,
    )


def build_source_block(
    entry: dict[str, Any],
    meta: dict[str, Any],
    source_key: str,
) -> dict[str, Any]:
    source_meta = AERO_SOURCES[source_key]
    block: dict[str, Any] = {
        "source": source_key,
        "source_url": meta.get("source_url", source_meta["url"]),
        "test_year": meta.get("test_year", source_meta["test_year"]),
        "speed_kph": meta.get("speed_kph", 40),
        "helmet_class": _normalize_class(entry.get("helmet_class", "aero")),
        "rank_pct": entry.get("rank_pct"),
        "score": round(entry["rank_pct"] * 100) if entry.get("rank_pct") is not None else None,
    }
    if meta.get("baseline_helmet"):
        block["baseline_helmet"] = meta["baseline_helmet"]
    if meta.get("error_margin_w") is not None:
        block["error_margin_w"] = meta["error_margin_w"]
    if entry.get("watts_saved") is not None:
        block["watts_saved"] = round(float(entry["watts_saved"]), 2)
    if entry.get("watts_saved_vs_slowest") is not None:
        block["watts_saved_vs_slowest"] = round(float(entry["watts_saved_vs_slowest"]), 2)
    if entry.get("weighted_cda_m2") is not None:
        block["weighted_cda_m2"] = entry["weighted_cda_m2"]
    if entry.get("cda_avg") is not None:
        block["cda_avg"] = entry["cda_avg"]
    drag = entry.get("drag_watts") or entry.get("drag_watts_40kph")
    if drag is not None:
        block["drag_watts_40kph"] = drag
    if entry.get("test_rank") is not None:
        block["test_rank"] = entry["test_rank"]
    if entry.get("variant"):
        block["variant"] = entry["variant"]
    if entry.get("rank_score") is not None:
        block["rank_score"] = entry["rank_score"]
    return block


def _empty_market_listings() -> dict:
    empty = {
        "price": None,
        "currency": "EUR",
        "rating": None,
        "review_count": None,
        "url": None,
        "source": None,
        "fetched_at": None,
    }
    return {
        "de": {**empty, "currency": "EUR", "source": "amazon_de"},
        "at": {**empty, "currency": "EUR", "source": "geizhals_at"},
        "ch": {**empty, "currency": "CHF", "source": "galaxus"},
    }


def standalone_from_aero_entry(entry: dict[str, Any], source_key: str) -> dict[str, Any]:
    brand = entry.get("brand", "").strip()
    model = entry.get("model", "").strip()
    helmet_id = entry.get("id") or f"extra-aero-{slugify(brand, model)}"
    if not helmet_id.startswith("extra-"):
        helmet_id = f"extra-aero-{helmet_id}"
    inferred_style = infer_style(brand, model)
    return {
        "id": helmet_id,
        "brand": brand,
        "brand_key": brand.lower(),
        "model": model,
        "search_text": f"{brand} {model}".lower(),
        "catalog": "extra_only",
        "primary_rating_source": None,
        "score": None,
        "ratings": {},
        "style": inferred_style,
        "style_meta": {
            "assigned": inferred_style,
            "source": "inferred",
            "aero_catalog": True,
        },
        "test_year": None,
        "certifications": "",
        "score_low_impact": None,
        "score_high_impact": None,
        "price_at_test_usd": None,
        "price_at_test_label": None,
        "value_ratio": None,
        "image_url": None,
        "features": {
            "mips_standard": False,
            "mips_spherical": False,
            "wavecel": False,
            "spin": False,
            "sweet_2vi": False,
            "koroyd": False,
            "rotational_protection": False,
            "nta8776": False,
            "asia_fit": False,
            "round_fit": False,
        },
        "feature_labels": [],
        "eu_brand": False,
        "eu_version": False,
        "european_market": True,
        "listings": _empty_market_listings(),
        "manufacturer": {
            "website": None,
            "search_url": None,
            "fetched": False,
            "title": None,
            "description": None,
            "image": None,
            "error": "aero_catalog",
        },
        "source": {
            "name": AERO_SOURCES[source_key]["label"],
            "url": AERO_SOURCES[source_key]["url"],
        },
    }


def _attach_source_to_helmet(
    helmet: dict[str, Any],
    entry: dict[str, Any],
    meta: dict[str, Any],
    source_key: str,
    match: HelmetMatch,
) -> None:
    block = build_source_block(entry, meta, source_key)
    block["match"] = {
        "confidence": round(match.confidence, 3),
        "method": match.method,
        "test_name": f"{entry.get('brand')} {entry.get('model')}",
    }
    aero = helmet.setdefault("aero", {"sources": {}})
    if "sources" not in aero:
        aero["sources"] = {}
    aero["sources"][source_key] = block


def merge_aero_ratings(helmets: list[dict], aero_data: dict[str, Any]) -> dict[str, Any]:
    tests = aero_data.get("tests")
    if not tests:
        tests = [{"meta": aero_data.get("meta", {}), "entries": aero_data.get("entries", [])}]

    helmets_by_id = {helmet["id"]: helmet for helmet in helmets}
    brand_candidates = _brand_candidates(helmets)
    existing_ids = set(helmets_by_id)

    stats: dict[str, Any] = {
        "matched": 0,
        "unmatched": 0,
        "extra_added": 0,
        "by_source": {},
        "unmatched_names": [],
    }

    for test in tests:
        meta = test.get("meta", {})
        source_key = meta.get("source")
        if not source_key or source_key not in AERO_SOURCES:
            continue

        entries = [dict(entry) for entry in test.get("entries", [])]
        apply_source_rank_percentiles(entries, source_key, meta)

        source_matched = 0
        source_unmatched: list[str] = []

        for entry in entries:
            match = match_aero_entry(entry, helmets, helmets_by_id, brand_candidates)
            if not match:
                stub_id = entry.get("id") or f"extra-aero-{slugify(entry.get('brand', ''), entry.get('model', ''))}"
                if not stub_id.startswith("extra-"):
                    stub_id = f"extra-aero-{stub_id}"
                if stub_id not in existing_ids:
                    stub = standalone_from_aero_entry(entry, source_key)
                    stub["id"] = stub_id
                    helmets.append(stub)
                    helmets_by_id[stub_id] = stub
                    existing_ids.add(stub_id)
                    brand_candidates = _brand_candidates(helmets)
                    stats["extra_added"] += 1
                    match = HelmetMatch(
                        helmet_id=stub_id,
                        brand=stub["brand"],
                        model=stub["model"],
                        confidence=1.0,
                        method="aero_stub",
                    )
                else:
                    match = HelmetMatch(
                        helmet_id=stub_id,
                        brand=entry.get("brand", ""),
                        model=entry.get("model", ""),
                        confidence=1.0,
                        method="aero_stub_existing",
                    )

            if match:
                helmet = helmets_by_id[match.helmet_id]
                _attach_source_to_helmet(helmet, entry, meta, source_key, match)
                source_matched += 1
                stats["matched"] += 1
            else:
                source_unmatched.append(f"{entry.get('brand')} {entry.get('model')}")

        stats["by_source"][source_key] = {
            "matched": source_matched,
            "entries": len(entries),
            "unmatched": len(source_unmatched),
        }
        stats["unmatched_names"].extend(source_unmatched)
        stats["unmatched"] += len(source_unmatched)

    finalize_all_aero(helmets)
    stats["total_entries"] = sum(len(test.get("entries", [])) for test in tests)
    stats["helmets_with_aero"] = sum(1 for helmet in helmets if helmet.get("aero"))
    return stats


def load_aero_ratings(path: Path | None = None) -> dict[str, Any]:
    path = path or DEFAULT_AERO_RATINGS
    return json.loads(path.read_text(encoding="utf-8"))
