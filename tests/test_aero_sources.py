"""Tests for aero tier assignment, per-source ranks, and fused scores."""

import unittest

from helmet_data.enrich.aero_sources import (
    aero_tier_for_rank_pct,
    aero_tier_for_watts,
    apply_source_rank_percentiles,
    finalize_helmet_aero,
    fuse_aero_source_blocks,
)


class AeroTierTests(unittest.TestCase):
    def test_watts_tier_thresholds(self) -> None:
        self.assertEqual(aero_tier_for_watts(8.0), "elite")
        self.assertEqual(aero_tier_for_watts(5.0), "strong")
        self.assertEqual(aero_tier_for_watts(3.0), "moderate")
        self.assertEqual(aero_tier_for_watts(1.0), "neutral")
        self.assertEqual(aero_tier_for_watts(-0.5), "draggy")

    def test_rank_pct_tier_thresholds(self) -> None:
        self.assertEqual(aero_tier_for_rank_pct(0.9), "elite")
        self.assertEqual(aero_tier_for_rank_pct(0.7), "strong")
        self.assertEqual(aero_tier_for_rank_pct(0.5), "moderate")
        self.assertEqual(aero_tier_for_rank_pct(0.3), "neutral")
        self.assertEqual(aero_tier_for_rank_pct(0.1), "draggy")


class AeroPercentileTests(unittest.TestCase):
    def test_source_rank_pct_higher_watts_is_better(self) -> None:
        entries = [
            {"id": "slow", "watts_saved": 1.0},
            {"id": "fast", "watts_saved": 7.0},
            {"id": "mid", "watts_saved": 4.0},
        ]
        meta = {"baseline_helmet": "Abus Powerdome"}
        apply_source_rank_percentiles(entries, "cyclingnews_sseh_2025", meta)
        by_id = {entry["id"]: entry["rank_pct"] for entry in entries}
        self.assertEqual(by_id["fast"], 1.0)
        self.assertEqual(by_id["mid"], 0.5)
        self.assertEqual(by_id["slow"], 0.0)


class AeroFusionTests(unittest.TestCase):
    def test_same_family_uses_newest_year(self) -> None:
        blocks = {
            "cyclingnews_sseh_2025": {"rank_pct": 0.27},
            "cyclingnews_sseh_2024": {"rank_pct": 0.82},
        }
        fused = fuse_aero_source_blocks(blocks)
        assert fused is not None
        self.assertEqual(fused["rank_pct"], 0.27)
        self.assertEqual(fused["sources"], ["cyclingnews_sseh_2025"])

    def test_finalize_prefers_newest_cn_year(self) -> None:
        helmet = {
            "id": "giro-eclipse-spherical",
            "aero": {
                "sources": {
                    "cyclingnews_sseh_2025": {
                        "rank_pct": 0.27,
                        "watts_saved": 1.1,
                        "baseline_helmet": "Abus Powerdome",
                        "speed_kph": 40,
                    },
                    "cyclingnews_sseh_2024": {
                        "rank_pct": 0.82,
                        "watts_saved_vs_slowest": 9.47,
                    },
                }
            },
        }
        finalize_helmet_aero(helmet)
        self.assertEqual(helmet["aero"]["score"], 27)
        self.assertEqual(helmet["aero"]["tier"], "neutral")
        self.assertEqual(helmet["aero"]["source_keys"], ["cyclingnews_sseh_2025"])
        self.assertEqual(helmet["aero"]["watts_saved"], 1.1)

    def test_finalize_sets_fused_tier(self) -> None:
        helmet = {
            "id": "test",
            "aero": {
                "sources": {
                    "cyclingnews_sseh_2025": {
                        "rank_pct": 0.9,
                        "watts_saved": 8.0,
                        "baseline_helmet": "Abus Powerdome",
                        "speed_kph": 40,
                    }
                }
            },
        }
        finalize_helmet_aero(helmet)
        self.assertEqual(helmet["aero"]["tier"], "elite")
        self.assertEqual(helmet["aero"]["score"], 90)
        self.assertEqual(helmet["aero"]["watts_saved"], 8.0)


if __name__ == "__main__":
    unittest.main()


def _aero_match(entry, helmets):
    from helmet_data.enrich.aero import match_aero_entry
    from helmet_data.enrich.matching import _brand_candidates

    by_id = {h["id"]: h for h in helmets}
    return match_aero_entry(entry, helmets, by_id, _brand_candidates(helmets))


AERO_HELMETS = [
    {"id": "sweet-protection-falconer-2vi-mips", "brand": "Sweet Protection", "model": "Falconer 2Vi MIPS"},
    {"id": "giant-rev-comp-mips", "brand": "Giant", "model": "Rev Comp MIPS"},
    {"id": "abus-powerdome-mips", "brand": "ABUS", "model": "Powerdome MIPS"},
]


def test_aero_does_not_map_tucker_to_falconer():
    entry = {"id": "sweet-protection-tucker-2vi", "brand": "Sweet Protection", "model": "Tucker 2Vi"}
    assert _aero_match(entry, AERO_HELMETS) is None


def test_aero_rejects_different_model_with_extra_words():
    assert _aero_match({"id": "giant-rev", "brand": "Giant", "model": "Rev"}, AERO_HELMETS) is None


def test_aero_accepts_vt_name_with_tech_suffix():
    match = _aero_match({"id": "abus-powerdome", "brand": "Abus", "model": "Powerdome"}, AERO_HELMETS)
    assert match is not None and match.helmet_id == "abus-powerdome-mips"
