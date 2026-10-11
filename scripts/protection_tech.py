"""Rotational protection detection, including MIPS variants not in model names."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
MIPS_LOOKUP_PATH = SCRIPT_DIR / "mips_lookup.json"

# Chart / summary supersets (one color bucket per helmet).
PROTECTION_SUPERSETS: list[dict[str, str]] = [
    {
        "key": "spherical",
        "label": "Spherical",
        "hint": "Ball-and-socket liners rotate as a unit (MIPS Spherical, Bell/Giro Spherical)",
        "color": "#818cf8",
    },
    {
        "key": "rotational",
        "label": "Slip-plane",
        "hint": "Low-friction layer lets the helmet slide on your head to reduce twist forces (MIPS, SPIN, 2Vi)",
        "color": "#34d399",
    },
    {
        "key": "crumple",
        "label": "Crumple",
        "hint": "Honeycomb or tube structures collapse to absorb impact energy (WaveCel, Koroyd) — not a sliding layer",
        "color": "#f472b6",
    },
    {
        "key": "none",
        "label": "None",
        "hint": "No detected rotational or crumple technology",
        "color": "#94a3b8",
    },
]

MIPS_VARIANTS: list[dict[str, str]] = [
    {
        "key": "air_node",
        "label": "MIPS Air Node",
        "pattern": r"mips\s*(?:®|™)?\s*(?:air\s*node|node\s*air)",
    },
    {"key": "evolve", "label": "MIPS Evolve", "pattern": r"mips\s*(?:®|™)?\s*evolve(?:\s*core)?"},
    {"key": "integra_split", "label": "MIPS Integra Split", "pattern": r"mips\s*(?:®|™)?\s*integra\s*split"},
    {"key": "integra_fuse", "label": "MIPS Integra Fuse", "pattern": r"mips\s*(?:®|™)?\s*integra\s*fuse"},
    {"key": "integra_tx", "label": "MIPS Integra TX", "pattern": r"mips\s*(?:®|™)?\s*integra\s*tx"},
    {"key": "integra", "label": "MIPS Integra", "pattern": r"mips\s*(?:®|™)?\s*integra"},
    {"key": "spherical", "label": "MIPS Spherical", "pattern": r"(?:mips\s*(?:®|™)?\s*spherical|spherical\s*(?:®|™)?\s*mips)"},
    {"key": "air", "label": "MIPS Air", "pattern": r"mips\s*(?:®|™)?\s*air\b(?!\s*node)"},
    {"key": "standard", "label": "MIPS", "pattern": r"\bmips\b"},
]

MIPS_VARIANT_LABELS = {entry["key"]: entry["label"] for entry in MIPS_VARIANTS}
MIPS_VARIANT_PATTERNS = [
    (entry["key"], re.compile(entry["pattern"], re.I)) for entry in MIPS_VARIANTS
]

OTHER_TECHNOLOGIES: list[dict[str, str]] = [
    {
        "key": "spin",
        "label": "POC SPIN",
        "group": "rotational",
        "hint": "POC silicone pad shear layer",
    },
    {
        "key": "sweet_2vi",
        "label": "Sweet Protection 2Vi",
        "group": "rotational",
        "hint": "Sweet Protection dual-density slip plane",
    },
    {
        "key": "wavecel",
        "label": "WaveCel",
        "group": "crumple",
        "hint": "Bontrager/Trek collapsible cell liner",
    },
    {
        "key": "koroyd",
        "label": "Koroyd",
        "group": "crumple",
        "hint": "Welded tube cores that crumple on impact",
    },
    {
        "key": "none",
        "label": "None",
        "group": "none",
        "hint": "No detected protection technology",
    },
]

PROTECTION_TECHNOLOGIES: list[dict[str, str]] = [
    {
        "key": "mips_spherical",
        "label": "MIPS Spherical",
        "group": "spherical",
        "hint": "Ball-and-socket MIPS (Bell/Giro)",
    },
    *[
        {
            "key": f"mips_{entry['key']}" if entry["key"] != "standard" else "mips_standard",
            "label": entry["label"],
            "group": "rotational",
            "hint": f"MIPS variant: {entry['label']}",
        }
        for entry in MIPS_VARIANTS
        if entry["key"] != "spherical"
    ],
    *OTHER_TECHNOLOGIES,
]

TECH_KEYS = {entry["key"] for entry in PROTECTION_TECHNOLOGIES}
TECH_TO_GROUP = {entry["key"]: entry["group"] for entry in PROTECTION_TECHNOLOGIES}
TECH_LABELS = {entry["key"]: entry["label"] for entry in PROTECTION_TECHNOLOGIES}

PROTECTION_GROUPS = PROTECTION_SUPERSETS


def load_mips_lookup(path: Path | None = None) -> dict[str, Any]:
    path = path or MIPS_LOOKUP_PATH
    if not path.exists():
        return {"helmets": {}, "patterns": []}
    return json.loads(path.read_text(encoding="utf-8"))


def load_price_cache_offer_texts(path: Path | None = None) -> dict[str, list[str]]:
    path = path or SCRIPT_DIR / "price_cache.json"
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    helmets = payload.get("helmets", {})
    texts_by_id: dict[str, list[str]] = {}
    for helmet_id, entry in helmets.items():
        titles: list[str] = []
        for offer in entry.get("offers") or []:
            title = offer.get("title")
            if title:
                titles.append(title)
        for history in entry.get("history") or []:
            for offer in history.get("offers") or []:
                title = offer.get("title")
                if title:
                    titles.append(title)
        if titles:
            texts_by_id[helmet_id] = titles
    return texts_by_id


def detect_mips_variant(text: str) -> str | None:
    if not text or not re.search(r"\bmips\b", text, re.I):
        return None
    for key, pattern in MIPS_VARIANT_PATTERNS:
        if pattern.search(text):
            return key
    return None


def extract_protection_from_text(text: str) -> dict[str, Any]:
    """Parse protection technology mentions from manufacturer page text."""
    if not text:
        return {}

    mips_variant = detect_mips_variant(text)
    lowered = text.lower()
    spin = bool(re.search(r"poc\s*spin|\bspin\s*(?:system|technology|pads|shear)", text, re.I))
    sweet_2vi = bool(re.search(r"\b2vi\b|2-vi|2\s*vi", text, re.I))
    wavecel = bool(re.search(r"wavecel", text, re.I))
    koroyd = bool(re.search(r"koroyd", text, re.I))

    snippet: str | None = None
    if mips_variant:
        match = re.search(r".{0,40}mips.{0,60}", text, re.I)
        snippet = match.group(0).strip() if match else None
    elif spin and "spin" in lowered:
        match = re.search(r".{0,30}spin.{0,40}", text, re.I)
        snippet = match.group(0).strip() if match else None

    return {
        "mips_variant": mips_variant,
        "spin": spin,
        "sweet_2vi": sweet_2vi,
        "wavecel": wavecel,
        "koroyd": koroyd,
        "snippet": snippet,
    }


def lookup_mips_variant(
    helmet_id: str,
    brand: str,
    model: str,
    lookup: dict[str, Any],
) -> tuple[str | None, str | None]:
    helmets = lookup.get("helmets", {})
    if helmet_id in helmets:
        entry = helmets[helmet_id]
        return entry.get("variant"), entry.get("source") or "lookup"

    brand_lower = brand.lower()
    model_lower = model.lower()
    for pattern in lookup.get("patterns", []):
        if pattern.get("brand", "").lower() != brand_lower:
            continue
        contains = pattern.get("model_contains", "").lower()
        if contains and contains not in model_lower:
            continue
        return pattern.get("variant"), pattern.get("source") or "lookup"

    return None, None


def collect_helmet_texts(helmet: dict[str, Any], extra_texts: list[str] | None = None) -> list[str]:
    parts = [
        helmet.get("brand", ""),
        helmet.get("model", ""),
        helmet.get("certifications", ""),
    ]
    manufacturer = helmet.get("manufacturer") or {}
    parts.extend(
        [
            manufacturer.get("title") or "",
            manufacturer.get("description") or "",
        ]
    )
    style_meta = helmet.get("style_meta") or {}
    parts.append(style_meta.get("manufacturer_title") or "")

    for listing in (helmet.get("listings") or {}).values():
        if isinstance(listing, dict):
            parts.append(listing.get("title") or "")

    if extra_texts:
        parts.extend(extra_texts)

    return [part for part in parts if part and str(part).strip()]


def mips_variant_to_tech_key(variant: str | None) -> str | None:
    if not variant:
        return None
    if variant == "spherical":
        return "mips_spherical"
    if variant == "standard":
        return "mips_standard"
    key = f"mips_{variant}"
    return key if key in TECH_KEYS else "mips_standard"


def classify_protection_tech(helmet: dict[str, Any]) -> str:
    features = helmet.get("features") or {}
    protection = helmet.get("protection") or {}

    if features.get("spin"):
        return "spin"
    if features.get("sweet_2vi"):
        return "sweet_2vi"

    variant = protection.get("mips_variant")
    if variant or features.get("mips_spherical") or features.get("mips_standard"):
        return mips_variant_to_tech_key(
            variant or ("spherical" if features.get("mips_spherical") else "standard")
        )

    if features.get("wavecel"):
        return "wavecel"
    if features.get("koroyd"):
        return "koroyd"
    return "none"


def classify_protection_superset(helmet: dict[str, Any]) -> str:
    tech = helmet.get("protection_tech") or classify_protection_tech(helmet)
    return TECH_TO_GROUP.get(tech, "none")


def classify_protection_group(features: dict[str, bool]) -> str:
    if features.get("mips_spherical"):
        return "spherical"
    if features.get("wavecel") or features.get("koroyd"):
        return "crumple"
    if (
        features.get("mips_standard")
        or features.get("spin")
        or features.get("sweet_2vi")
        or features.get("rotational_protection")
    ):
        return "rotational"
    return "none"


def sync_mips_feature_flags(features: dict[str, bool], mips_variant: str | None) -> None:
    if not mips_variant:
        return
    if mips_variant == "spherical":
        features["mips_spherical"] = True
        features["mips_standard"] = False
    else:
        features["mips_standard"] = True
        features["mips_spherical"] = False
    features["rotational_protection"] = True


def build_feature_labels(features: dict[str, bool], protection: dict[str, Any]) -> list[str]:
    labels: list[str] = []

    mips_label = protection.get("mips_label")
    if protection.get("has_mips") and mips_label:
        labels.append(mips_label)
    elif features.get("mips_spherical"):
        labels.append("MIPS Spherical")
    elif features.get("mips_standard"):
        labels.append("MIPS")

    if features.get("spin"):
        labels.append("POC SPIN")
    if features.get("sweet_2vi"):
        labels.append("Sweet Protection 2Vi")
    if features.get("wavecel"):
        labels.append("WaveCel")
    if features.get("koroyd"):
        labels.append("Koroyd")

    if features.get("nta8776"):
        labels.append("NTA 8776")
    if features.get("asia_fit"):
        labels.append("Asia Fit")
    if features.get("round_fit"):
        labels.append("Round Fit")

    return labels


def apply_protection_to_helmet(
    helmet: dict[str, Any],
    *,
    lookup: dict[str, Any] | None = None,
    extra_texts: list[str] | None = None,
) -> dict[str, Any]:
    lookup = lookup or load_mips_lookup()
    features = helmet.setdefault("features", {})

    exclusive_rotational = features.get("spin") or features.get("sweet_2vi")

    mips_variant: str | None = None
    mips_source: str | None = None

    if not exclusive_rotational:
        texts = collect_helmet_texts(helmet, extra_texts)
        for text in texts:
            mips_variant = detect_mips_variant(text)
            if mips_variant:
                mips_source = "text"
                break

        if not mips_variant:
            lookup_variant, lookup_source = lookup_mips_variant(
                helmet.get("id", ""),
                helmet.get("brand", ""),
                helmet.get("model", ""),
                lookup,
            )
            if lookup_variant:
                mips_variant = lookup_variant
                mips_source = lookup_source

        if mips_variant:
            sync_mips_feature_flags(features, mips_variant)

    rotational_key: str | None = None
    rotational_label: str | None = None
    if features.get("spin"):
        rotational_key, rotational_label = "spin", "POC SPIN"
    elif features.get("sweet_2vi"):
        rotational_key, rotational_label = "sweet_2vi", "Sweet Protection 2Vi"
    elif mips_variant:
        rotational_key, rotational_label = "mips", MIPS_VARIANT_LABELS.get(mips_variant, "MIPS")
    elif features.get("wavecel"):
        rotational_key, rotational_label = "wavecel", "WaveCel"
    elif features.get("koroyd"):
        rotational_key, rotational_label = "koroyd", "Koroyd"

    protection: dict[str, Any] = {
        "has_mips": bool(mips_variant),
        "mips_variant": mips_variant,
        "mips_label": MIPS_VARIANT_LABELS.get(mips_variant) if mips_variant else None,
        "rotational_tech": rotational_key,
        "rotational_label": rotational_label,
        "source": mips_source if mips_variant else ("model_name" if exclusive_rotational else None),
    }

    helmet["protection"] = protection
    helmet["feature_labels"] = build_feature_labels(features, protection)
    helmet["protection_tech"] = classify_protection_tech(helmet)
    helmet["protection_group"] = classify_protection_superset(helmet)
    return protection


def apply_protection_to_all(
    helmets: list[dict[str, Any]],
    *,
    lookup: dict[str, Any] | None = None,
    price_texts: dict[str, list[str]] | None = None,
    manufacturer_cache: dict[str, dict[str, Any]] | None = None,
    retailer_cache: dict[str, dict[str, Any]] | None = None,
) -> dict[str, int]:
    lookup = lookup or load_mips_lookup()
    if retailer_cache:
        from retailer_protection import merge_retailer_cache_into_lookup

        lookup = merge_retailer_cache_into_lookup(lookup, retailer_cache)
    if manufacturer_cache:
        from manufacturer_protection import merge_manufacturer_cache_into_lookup

        lookup = merge_manufacturer_cache_into_lookup(lookup, manufacturer_cache)
    price_texts = price_texts if price_texts is not None else load_price_cache_offer_texts()
    stats = {"mips_detected": 0, "from_lookup": 0, "from_text": 0}

    for helmet in helmets:
        extra = price_texts.get(helmet.get("id", ""), [])
        protection = apply_protection_to_helmet(helmet, lookup=lookup, extra_texts=extra)
        if protection.get("has_mips"):
            stats["mips_detected"] += 1
            source = protection.get("source")
            if source == "text":
                stats["from_text"] += 1
            elif source:
                stats["from_lookup"] += 1

    return stats


def protection_supersets_for_filters() -> list[dict[str, str]]:
    return [dict(group) for group in PROTECTION_SUPERSETS]


def protection_groups_for_filters() -> list[dict[str, str]]:
    return protection_supersets_for_filters()


def protection_technologies_for_filters(helmets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {entry["key"]: 0 for entry in PROTECTION_TECHNOLOGIES}
    for helmet in helmets:
        tech = helmet.get("protection_tech") or classify_protection_tech(helmet)
        if tech in counts:
            counts[tech] += 1

    return [
        {
            **entry,
            "count": counts.get(entry["key"], 0),
            "group_label": next(
                (group["label"] for group in PROTECTION_SUPERSETS if group["key"] == entry["group"]),
                entry["group"],
            ),
        }
        for entry in PROTECTION_TECHNOLOGIES
    ]


def mips_variants_for_filters() -> list[dict[str, str]]:
    return [{"key": key, "label": label} for key, label in MIPS_VARIANT_LABELS.items()]
