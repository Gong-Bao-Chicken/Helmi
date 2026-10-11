"""Tests for manufacturer protection crawling."""

import unittest

from helmet_data.enrich.manufacturer_protection import (
    analyze_protection_html,
    extract_sku_product_urls,
    pick_best_product_url,
    score_product_url,
)

FOX_RS_PRODUCT_HTML = """
<html><body>
<h1>Speedframe RS Matte Black Helmet</h1>
<ul>
<li>Mips® Integra Split equipped</li>
<li>Features Mips® Integra Split Dual Density Protection System</li>
</ul>
<p>The all-new Speedframe RS features the exclusive Mips® Integra Split protection system.</p>
</body></html>
"""

FOX_SEARCH_HTML = """
<a href="/helmets/moto/">Moto Helmets</a>
<a href="/helmets/mtb/speedframe/speedframe-rs/">Speedframe RS</a>
<a href="/product/speedframe-rs-matte-black-helmet/32237.html">Buy</a>
"""


class UrlScoringTests(unittest.TestCase):
    def test_prefers_mtb_over_moto(self) -> None:
        moto = score_product_url("https://www.foxracing.com/helmets/moto/", "Speedframe RS")
        mtb = score_product_url(
            "https://www.foxracing.com/helmets/mtb/speedframe/speedframe-rs/",
            "Speedframe RS",
        )
        self.assertGreater(mtb, moto)

    def test_prefers_product_page(self) -> None:
        category = score_product_url(
            "https://www.foxracing.com/helmets/mtb/speedframe/speedframe-rs/",
            "Speedframe RS",
        )
        product = score_product_url(
            "https://www.foxracing.com/product/speedframe-rs-matte-black-helmet/32237.html",
            "Speedframe RS",
        )
        self.assertGreater(product, category)

    def test_pick_best_from_search(self) -> None:
        url = pick_best_product_url(
            FOX_SEARCH_HTML,
            "https://www.foxracing.com/search?q=Speedframe+RS",
            "Speedframe RS",
            brand="Fox Racing",
        )
        self.assertIn("speedframe-rs", url.lower())


class ProtectionExtractionTests(unittest.TestCase):
    def test_fox_integra_split(self) -> None:
        result = analyze_protection_html(FOX_RS_PRODUCT_HTML, product_url="https://example.com/p")
        self.assertEqual(result["mips_variant"], "integra_split")
        self.assertEqual(result["mips_label"], "MIPS Integra Split")
        self.assertEqual(result["protection_tech"], "mips_integra_split")

    def test_extract_sku_links(self) -> None:
        category_html = """
        <a href="/product/speedframe-rs-matte-black-helmet/32237.html">RS Black</a>
        <a href="/product/speedframe-pro-helmet/12345.html">Pro</a>
        """
        urls = extract_sku_product_urls(category_html, "https://www.foxracing.com/cat/", "Speedframe RS")
        self.assertEqual(len(urls), 1)
        self.assertIn("speedframe-rs", urls[0])
        self.assertNotIn("speedframe-pro", urls[0])


if __name__ == "__main__":
    unittest.main()
