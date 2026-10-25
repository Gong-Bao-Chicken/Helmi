"""Write helmets.json plus the slimmer copy the website loads."""

import copy
import json
from pathlib import Path
from typing import Any

SITE_SUFFIX = ".site.json"


def site_copy(data: dict[str, Any]) -> dict[str, Any]:
    """helmets.json without what only the pipeline or data users need (debug and per-offer detail).

    The site loads this on every visit; helmets.json stays complete for anyone reusing the data.
    """
    slim = copy.deepcopy(data)
    meta = slim.get("meta", {})
    meta.pop("market_prices_source_errors", None)
    meta.get("market_prices_outliers", {}).pop("dropped", None)
    for helmet in slim.get("helmets", []):
        helmet.pop("style_meta", None)
        helmet.pop("price_comparison_label", None)
        website = (helmet.get("manufacturer") or {}).get("website")
        helmet["manufacturer"] = {"website": website} if website else {}
        for key in ("source_details", "sample_prices"):
            (helmet.get("current_price") or {}).pop(key, None)
        for listing in (helmet.get("listings") or {}).values():
            listing.pop("sources", None)
    return slim


def write_dataset(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    site_path = path.with_name(path.stem + SITE_SUFFIX)
    compact = json.dumps(site_copy(data), separators=(",", ":"), ensure_ascii=False)
    site_path.write_text(compact, encoding="utf-8")
