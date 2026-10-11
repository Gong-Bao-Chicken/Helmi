"""Tests for protection technology detection."""

import unittest

from helmet_data.build import empty_features, extract_features
from helmet_data.enrich.protection_tech import (
    apply_protection_to_helmet,
    detect_mips_variant,
    lookup_mips_variant,
)


class DetectMipsVariantTests(unittest.TestCase):
    def test_air_node(self) -> None:
        self.assertEqual(
            detect_mips_variant("Fox Speedframe Pro with MIPS Air Node system"),
            "air_node",
        )

    def test_node_air_ordering(self) -> None:
        self.assertEqual(
            detect_mips_variant("Our MIPS Node Air technology is integrated into the padding"),
            "air_node",
        )

    def test_evolve(self) -> None:
        self.assertEqual(
            detect_mips_variant("POC Cularis Pure Mips Evolve Core"),
            "evolve",
        )

    def test_spherical(self) -> None:
        self.assertEqual(
            detect_mips_variant("Giro Aries Spherical MIPS"),
            "spherical",
        )

    def test_standard(self) -> None:
        self.assertEqual(detect_mips_variant("Giro Fixture MIPS"), "standard")

    def test_no_mips(self) -> None:
        self.assertIsNone(detect_mips_variant("Generic road helmet"))


class ApplyProtectionTests(unittest.TestCase):
    def test_poc_cularis_lookup(self) -> None:
        helmet = {
            "id": "poc-cularis",
            "brand": "POC",
            "model": "Cularis",
            "certifications": "CPSC",
            "features": extract_features("Cularis", "CPSC"),
        }
        protection = apply_protection_to_helmet(helmet)
        self.assertTrue(protection["has_mips"])
        self.assertEqual(protection["mips_variant"], "air_node")
        self.assertEqual(protection["mips_label"], "MIPS Air Node")
        self.assertIn("MIPS Air Node", helmet["feature_labels"])
        self.assertTrue(helmet["features"]["mips_standard"])

    def test_spin_not_mips(self) -> None:
        helmet = {
            "id": "poc-octal-x-spin",
            "brand": "POC",
            "model": "Octal X SPIN",
            "certifications": "",
            "features": extract_features("Octal X SPIN", ""),
        }
        protection = apply_protection_to_helmet(helmet)
        self.assertFalse(protection["has_mips"])
        self.assertEqual(protection["rotational_tech"], "spin")

    def test_listing_text_detects_air_node(self) -> None:
        helmet = {
            "id": "fox-racing-speedframe-pro",
            "brand": "Fox Racing",
            "model": "Speedframe Pro",
            "certifications": "",
            "features": empty_features(),
        }
        protection = apply_protection_to_helmet(
            helmet,
            extra_texts=["MIPS Air Node Schutzsystem"],
        )
        self.assertEqual(protection["mips_variant"], "air_node")
        self.assertEqual(protection["source"], "text")

    def test_pattern_lookup_evolve(self) -> None:
        lookup = {
            "helmets": {},
            "patterns": [
                {
                    "brand": "POC",
                    "model_contains": "Cularis Pure",
                    "variant": "evolve",
                }
            ],
        }
        variant, source = lookup_mips_variant("extra-poc-x", "POC", "Cularis Pure", lookup)
        self.assertEqual(variant, "evolve")
        self.assertEqual(source, "lookup")


if __name__ == "__main__":
    unittest.main()
