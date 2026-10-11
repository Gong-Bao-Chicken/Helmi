"""Tests for helmet style inference and manufacturer compatibility."""

import unittest

from helmet_data.enrich.styles import (
    infer_style,
    infer_style_from_text,
    refine_helmet_styles,
    styles_compatible,
)


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

    def test_kids_helmets_get_their_own_style(self) -> None:
        self.assertEqual(infer_style("Bell", "Spark Youth MIPS"), "Kids")
        self.assertEqual(infer_style("Fox", "Rampage Youth MIPS Full Face"), "Kids")

    def test_unknown_style_is_unclassified_not_urban(self) -> None:
        self.assertEqual(infer_style("ABUS", "Hyban 2.0"), "Unclassified")
        self.assertEqual(infer_style("ABUS", "Hyban 2.0", default="Road"), "Road")

    def test_vt_urban_kids_helmet_is_reclassified(self) -> None:
        helmets = [
            {
                "brand": "Giro",
                "model": "Hale Youth",
                "style": "Urban",
                "style_meta": {"source": "virginia_tech"},
            }
        ]
        refine_helmet_styles(helmets)
        self.assertEqual(helmets[0]["style"], "Kids")
        self.assertEqual(helmets[0]["style_meta"]["vt_style"], "Urban")


if __name__ == "__main__":
    unittest.main()
