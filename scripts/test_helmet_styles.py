"""Tests for helmet style inference and manufacturer compatibility."""

from __future__ import annotations

import unittest

from helmet_styles import infer_style, infer_style_from_text, styles_compatible


class StyleInferenceTests(unittest.TestCase):
    def test_infer_style_from_manufacturer_text(self) -> None:
        self.assertEqual(
            infer_style_from_text("Fox Racing Speedframe Pro MTB Helmet - Trail"),
            "Mountain",
        )
        self.assertEqual(
            infer_style_from_text("Giro Aries Spherical Road Helmet"),
            "Road",
        )

    def test_styles_compatible_allows_aero_road(self) -> None:
        self.assertTrue(styles_compatible("Road", "Aero"))
        self.assertTrue(styles_compatible("Mountain", "Full-Face"))
        self.assertFalse(styles_compatible("Mountain", "Road"))


class ModelInferenceTests(unittest.TestCase):
    def test_infer_style_from_model_tokens(self) -> None:
        self.assertEqual(infer_style("MET", "Trenta 3K Carbon MIPS"), "Aero")
        self.assertEqual(infer_style("Giro", "Fixture Road"), "Road")


if __name__ == "__main__":
    unittest.main()
