from helmet_data.build import load_eu_brands, parse_name_brand_model, standalone_from_unmatched


def test_decathlon_van_rysel_titles_use_van_rysel_brand():
    assert parse_name_brand_model("Decathlon Van Rysel Road R 500") == ("Van Rysel", "Road R 500")
    assert parse_name_brand_model("Van Rysel FCR MIPS") == ("Van Rysel", "FCR MIPS")
    assert parse_name_brand_model("Giro Aries Spherical") == ("Giro", "Aries Spherical")


def test_van_rysel_counts_as_european_market():
    entry = {
        "source": "nsw_helmet_star",
        "model": "Decathlon Van Rysel FCR MIPS Roubaix",
        "slug": "decathlon-van-rysel-fcr-mips-roubaix",
        "stars": 4,
    }
    helmet = standalone_from_unmatched(entry, load_eu_brands())
    assert helmet["brand"] == "Van Rysel"
    assert helmet["model"] == "FCR MIPS Roubaix"
    assert helmet["european_market"] is True
