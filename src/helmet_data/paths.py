"""Central filesystem locations for reference data, caches and generated output."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = REPO_ROOT / "data"
REFERENCE_DIR = DATA_DIR / "reference"
CACHE_DIR = DATA_DIR / "cache"

# Hand-maintained reference inputs
BRANDS_PATH = REFERENCE_DIR / "brands.json"
EU_BRANDS_PATH = REFERENCE_DIR / "eu_brands.json"
EU_EXCLUDED_BRANDS_PATH = REFERENCE_DIR / "eu_excluded_brands.json"
MIPS_LOOKUP_PATH = REFERENCE_DIR / "mips_lookup.json"
# Curated aero list; numeric fields are refreshed by `helmet-data fetch-aero --fetch`.
AERO_RATINGS_PATH = REFERENCE_DIR / "aero_ratings.json"

# Generated caches (tracked: extra ratings + protection caches, so `update --quick` works offline)
EXTRA_RATINGS_PATH = CACHE_DIR / "extra_ratings.json"
EXTRA_RATINGS_RAW_PATH = CACHE_DIR / "extra_ratings_raw.json"
MANUFACTURER_PROTECTION_CACHE_PATH = CACHE_DIR / "manufacturer_protection_cache.json"
RETAILER_PROTECTION_CACHE_PATH = CACHE_DIR / "retailer_protection_cache.json"
# Generated caches (gitignored)
PRICE_CACHE_PATH = CACHE_DIR / "price_cache.json"
STYLE_CACHE_PATH = CACHE_DIR / "manufacturer_style_cache.json"
STEALTH_COOKIES_PATH = CACHE_DIR / ".stealth-cookies.json"

# Final output consumed by the frontend
HELMETS_JSON_PATH = REPO_ROOT / "web" / "public" / "data" / "helmets.json"
