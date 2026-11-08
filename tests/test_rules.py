from datetime import date

from etl.rules import body_group, parse_region, volume_category, weight_category
from etl.run_etl import month_chunks


def test_weight_category_boundaries():
    cases = {30.0: "G20T", 38.0: "G20T", 29.96: "G20T",
             29.9: "FTL", 10.0: "FTL", 9.96: "FTL",
             9.9: "10T", 5.0: "10T", 4.9: "5T", 2.5: "5T", 2.4: "L5T",
             0.5: "L5T", 0.46: "L5T", 0.4: "OTH", 0.0: "OTH"}
    for w, expected in cases.items():
        assert weight_category(w) == expected, (w, weight_category(w), expected)


def test_volume_category_boundaries():
    assert volume_category(0) == "OTH"
    assert volume_category(0.1) == "FTL"
    assert volume_category(120) == "FTL"
    assert volume_category(120.01) == "OTH"


def test_body_group_mapping():
    for std, grp in {56: "Tent", 4: "Reefer", 2: "Isotherm", 15: "Flatbed",
                     3: "Other", 50: "Other", None: "Other"}.items():
        assert body_group(std) == grp


def test_parse_region():
    assert parse_region("Kazan, Tatarstan Republic") == "Tatarstan Republic"
    assert parse_region("Moscow, Moscow City") == "Moscow City"
    assert parse_region("Kazan city, Tatarstan") == "Tatarstan"
    assert parse_region("No region") is None
    assert parse_region(None) is None


def test_month_chunks_cover_window_without_gaps():
    chunks = list(month_chunks(date(2026, 1, 15), date(2026, 3, 10)))
    assert chunks == [(date(2026, 1, 15), date(2026, 1, 31)),
                      (date(2026, 2, 1), date(2026, 2, 28)),
                      (date(2026, 3, 1), date(2026, 3, 10))]
    assert list(month_chunks(date(2026, 5, 5), date(2026, 5, 5))) == [(date(2026, 5, 5), date(2026, 5, 5))]
