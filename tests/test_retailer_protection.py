"""Tests for retailer product-page protection crawling."""

import unittest

from helmet_data.enrich.protection_tech import detect_mips_variant
from helmet_data.enrich.retailer_protection import (
    collect_retailer_product_urls,
    extract_geizhals_product_text,
    protection_result_from_html,
    variant_rank,
)

GEIZHALS_HTML = """
<html><body>
<h1>Specialized S-Works Prevail 3 Helm</h1>
<meta name="description" content="Specialized road helmet">
<div class="specs">
  Einsatzbereich Rennroad Visier nein
  Größen 51-56cm (S), 55-59cm (M), 58-62cm (L)
  Besonderheiten MIPS Air Node, Verstellsystem
</div>
</body></html>
"""

GALAXUS_HTML = """
<html><body>
<h1 data-test="product-title">POC Cularis MIPS Air Node</h1>
<dl>
  <dt>Schutzsystem</dt><dd>MIPS Air Node</dd>
</dl>
</body></html>
"""


class RetailerProtectionTests(unittest.TestCase):
    def test_node_air_pattern(self) -> None:
        self.assertEqual(
            detect_mips_variant("MIPS Node Air technology integrated into padding"),
            "air_node",
        )

    def test_collect_urls_from_listings(self) -> None:
        helmet = {
            "id": "specialized-prevail-3",
            "listings": {
                "de": {
                    "source": "geizhals",
                    "url": "https://geizhals.de/specialized-s-works-prevail-3-helm-v106241.html",
                    "sources": [
                        {
                            "source": "geizhals",
                            "url": "https://geizhals.de/specialized-s-works-prevail-3-helm-v106241.html",
                        }
                    ],
                }
            },
        }
        urls = collect_retailer_product_urls(helmet)
        self.assertEqual(len(urls), 1)
        self.assertEqual(urls[0][0], "geizhals")

    def test_geizhals_extracts_besonderheiten(self) -> None:
        text = extract_geizhals_product_text(GEIZHALS_HTML)
        self.assertIn("MIPS Air Node", text)

    def test_geizhals_detects_air_node(self) -> None:
        result = protection_result_from_html(
            GEIZHALS_HTML,
            product_url="https://geizhals.de/example-v123.html",
            model="Prevail 3",
            source="geizhals",
        )
        self.assertEqual(result["mips_variant"], "air_node")
        self.assertEqual(result["protection_tech"], "mips_air_node")

    def test_galaxus_detects_air_node(self) -> None:
        result = protection_result_from_html(
            GALAXUS_HTML,
            product_url="https://www.galaxus.ch/de/product/123",
            model="Cularis",
            source="galaxus",
        )
        self.assertEqual(result["mips_variant"], "air_node")

    def test_variant_rank_prefers_specific(self) -> None:
        self.assertGreater(variant_rank("air_node"), variant_rank("standard"))


if __name__ == "__main__":
    unittest.main()
