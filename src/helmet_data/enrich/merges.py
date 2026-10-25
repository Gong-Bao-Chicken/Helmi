"""Fold helmets listed twice under different lab names into one entry."""

import json

from ..paths import HELMET_MERGES_PATH


def load_helmet_merges() -> dict[str, dict[str, str]]:
    if not HELMET_MERGES_PATH.exists():
        return {}
    return json.loads(HELMET_MERGES_PATH.read_text(encoding="utf-8"))["merges"]


def apply_helmet_merges(helmets: list[dict], merges: dict[str, dict[str, str]]) -> int:
    """Move each duplicate's lab results and aero data onto the kept helmet, then drop it.

    The kept helmet's own results win when both have one from the same lab. Callers re-run
    the rating fusion afterwards, since the kept helmet may now have more labs.
    """
    by_id = {helmet["id"]: helmet for helmet in helmets}
    dropped: set[str] = set()
    for duplicate_id, merge in merges.items():
        duplicate, kept = by_id.get(duplicate_id), by_id.get(merge["into"])
        if duplicate is None or kept is None:
            continue
        ratings = kept.setdefault("ratings", {})
        for source, block in duplicate.get("ratings", {}).items():
            if source != "fused" and source not in ratings:
                ratings[source] = block
        if duplicate.get("aero") and not kept.get("aero"):
            kept["aero"] = duplicate["aero"]
        kept.setdefault("merged_from", []).append({"id": duplicate_id, "name": duplicate["model"]})
        dropped.add(duplicate_id)
    helmets[:] = [helmet for helmet in helmets if helmet["id"] not in dropped]
    return len(dropped)
