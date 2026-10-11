"""Tests for shop listing title matching."""

import unittest

from helmet_data.crawlers.price_sources import build_search_context, score_offer


class PriceMatchingTests(unittest.TestCase):
    def test_slash_brand_matches_either_part(self) -> None:
        ctx = build_search_context("Giant/Liv", "Rev MIPS")
        self.assertGreater(score_offer(ctx, "Giant Rev MIPS Fahrradhelm"), 0.0)
        self.assertGreater(score_offer(ctx, "Liv Rev MIPS Fahrradhelm"), 0.0)

    def test_model_tokens_must_overlap(self) -> None:
        ctx = build_search_context("Lazer", "Z1")
        self.assertEqual(score_offer(ctx, "Lazer Pnut 2.0 KinetiCore Helm"), 0.0)
        self.assertGreater(score_offer(ctx, "Lazer Z1 MIPS Fahrradhelm"), 0.0)

    def test_matching_model_passes(self) -> None:
        ctx = build_search_context("Giro", "Register MIPS")
        self.assertGreater(score_offer(ctx, "Giro Register MIPS Helm"), 0.0)

    def test_rejects_implausible_low_price(self) -> None:
        from helmet_data.crawlers.price_sources import PriceOffer, accept_offer

        ctx = build_search_context("Specialized", "Tactic 4")
        offer = PriceOffer(
            source="geizhals",
            title="Specialized Tactic 4 Helm",
            price=10.0,
            currency="EUR",
            url="https://geizhals.de/6337759056",
        )
        self.assertIsNone(accept_offer(ctx, offer))


if __name__ == "__main__":
    unittest.main()
