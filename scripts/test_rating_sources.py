"""Tests for lab safety rating percentiles and fusion."""

from __future__ import annotations

import unittest

from rating_sources import (
    RATING_SOURCES,
    compute_min_max_norm,
    compute_rank_percentiles,
    finalize_all_ratings,
    fuse_ratings,
)


class MinMaxNormTests(unittest.TestCase):
    def test_lower_is_better_maps_min_to_one(self) -> None:
        ranks = compute_min_max_norm(
            [("best", 10.0), ("mid", 15.0), ("worst", 20.0)],
            lower_is_better=True,
        )
        self.assertEqual(ranks["best"], 1.0)
        self.assertEqual(ranks["worst"], 0.0)
        self.assertAlmostEqual(ranks["mid"], 0.5)

    def test_tied_scores_share_top_norm(self) -> None:
        ranks = compute_min_max_norm(
            [("a", 10.0), ("b", 10.0), ("c", 20.0)],
            lower_is_better=True,
        )
        self.assertEqual(ranks["a"], 1.0)
        self.assertEqual(ranks["b"], 1.0)
        self.assertEqual(ranks["c"], 0.0)


class RankPercentileTests(unittest.TestCase):
    def test_tied_scores_share_percentile(self) -> None:
        ranks = compute_rank_percentiles(
            [("a", 10.0), ("b", 10.0), ("c", 20.0)],
            lower_is_better=True,
        )
        self.assertEqual(ranks["a"], ranks["b"])
        self.assertGreater(ranks["a"], ranks["c"])

    def test_higher_is_better_orders_descending(self) -> None:
        ranks = compute_rank_percentiles(
            [("low", 1.0), ("mid", 2.0), ("high", 3.0)],
            lower_is_better=False,
        )
        self.assertEqual(ranks["high"], 1.0)
        self.assertEqual(ranks["low"], 0.0)


class FinalizeRatingsTests(unittest.TestCase):
    def test_recomputes_on_full_pool(self) -> None:
        helmets = [
            {
                "id": "a",
                "ratings": {
                    "certimoov": {"score": 2.0, "rank_pct": 0.99},
                },
            },
            {
                "id": "b",
                "ratings": {
                    "certimoov": {"score": 4.0, "rank_pct": 0.1},
                },
            },
        ]
        finalize_all_ratings(helmets)
        self.assertGreater(
            helmets[1]["ratings"]["certimoov"]["rank_pct"],
            helmets[0]["ratings"]["certimoov"]["rank_pct"],
        )

    def test_virginia_tech_uses_percentile_and_min_max(self) -> None:
        helmets = [
            {
                "id": "best",
                "ratings": {"virginia_tech": {"score": 4.0, "rank_pct": None, "score_norm": None}},
            },
            {
                "id": "mid",
                "ratings": {"virginia_tech": {"score": 6.0, "rank_pct": None, "score_norm": None}},
            },
            {
                "id": "worst",
                "ratings": {"virginia_tech": {"score": 8.0, "rank_pct": None, "score_norm": None}},
            },
        ]
        finalize_all_ratings(helmets)
        best = helmets[0]["ratings"]["virginia_tech"]
        worst = helmets[2]["ratings"]["virginia_tech"]
        self.assertEqual(best["score_norm"], 1.0)
        self.assertEqual(worst["score_norm"], 0.0)
        self.assertGreater(best["rank_pct"], worst["rank_pct"])

    def test_folksam_uses_overall_result_pct(self) -> None:
        helmets = [
            {
                "id": "a",
                "ratings": {"folksam": {"overall_result_pct": -10.0, "rank_pct": 0.5}},
            },
            {
                "id": "b",
                "ratings": {"folksam": {"overall_result_pct": 20.0, "rank_pct": 0.5}},
            },
        ]
        finalize_all_ratings(helmets)
        self.assertGreater(
            helmets[1]["ratings"]["folksam"]["rank_pct"],
            helmets[0]["ratings"]["folksam"]["rank_pct"],
        )

    def test_fusion_only_uses_safety_sources(self) -> None:
        ratings = {
            "virginia_tech": {"rank_pct": 0.8},
            "folksam": {"rank_pct": 0.6},
            "shop_reviews": {"rank_pct": 0.95},
        }
        fused = fuse_ratings(ratings, ["virginia_tech", "folksam", "shop_reviews"])
        self.assertIsNotNone(fused)
        assert fused is not None
        self.assertEqual(set(fused["sources"]), {"virginia_tech", "folksam"})
        for key in fused["sources"]:
            self.assertIn(key, RATING_SOURCES)


if __name__ == "__main__":
    unittest.main()
