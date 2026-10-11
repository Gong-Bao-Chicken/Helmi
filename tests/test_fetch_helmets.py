"""Tests for Virginia Tech data parsing."""

import unittest

from helmet_data.build import (
    empty_features,
    extract_features,
    parse_usd_cost,
    parse_vt_js,
)
from helmet_data.enrich.protection_tech import classify_protection_group


class ParseVtJsTests(unittest.TestCase):
    def test_parses_object_literal_keys(self) -> None:
        sample = """
        var bicycleDataRaw = [{
          brand: "Giro",
          model: "Fixture",
          score: 12.5,
          rating: 4,
          cost: "$55",
          style: "Road",
          date: "2024",
          photo: "giro-fixture.jpg",
          certifications: "CPSC",
          low: 1.0,
          high: 2.0
        }];
        """
        rows = parse_vt_js(sample)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["brand"], "Giro")
        self.assertEqual(rows[0]["score"], 12.5)

    def test_parse_usd_cost(self) -> None:
        self.assertEqual(parse_usd_cost("$379"), 379.0)
        self.assertIsNone(parse_usd_cost(None))


class ExtractFeaturesTests(unittest.TestCase):
    def test_koroyd_from_certifications(self) -> None:
        features = extract_features("XYZ", "CPSC Koroyd")
        self.assertTrue(features["koroyd"])


class ClassifyProtectionGroupTests(unittest.TestCase):
    def group_for(self, model: str, certifications: str = "") -> str:
        return classify_protection_group(extract_features(model, certifications))

    def test_spherical(self) -> None:
        self.assertEqual(self.group_for("Bell Spherical"), "spherical")
        self.assertEqual(self.group_for("Giro Aether MIPS Spherical"), "spherical")

    def test_wavecel_is_crumple(self) -> None:
        self.assertEqual(self.group_for("Bontrager WaveCel"), "crumple")

    def test_koroyd_is_crumple(self) -> None:
        self.assertEqual(self.group_for("Smart Helmet", "CPSC Koroyd"), "crumple")

    def test_mips_is_rotational(self) -> None:
        self.assertEqual(self.group_for("Giro Synthe MIPS"), "rotational")

    def test_spin_is_rotational(self) -> None:
        self.assertEqual(self.group_for("POC Ventral SPIN"), "rotational")

    def test_2vi_is_rotational(self) -> None:
        self.assertEqual(self.group_for("Sweet Protection Falconer 2Vi"), "rotational")

    def test_none(self) -> None:
        self.assertEqual(self.group_for("Generic Road"), "none")
        self.assertEqual(classify_protection_group(empty_features()), "none")

    def test_priority_spherical_over_crumple(self) -> None:
        features = empty_features()
        features["mips_spherical"] = True
        features["wavecel"] = True
        features["koroyd"] = True
        self.assertEqual(classify_protection_group(features), "spherical")

    def test_priority_crumple_over_rotational(self) -> None:
        features = empty_features()
        features["wavecel"] = True
        features["mips_standard"] = True
        features["rotational_protection"] = True
        self.assertEqual(classify_protection_group(features), "crumple")


if __name__ == "__main__":
    unittest.main()
