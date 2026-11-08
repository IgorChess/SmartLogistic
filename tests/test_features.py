import math

import numpy as np
import pandas as pd

from ml.features import (CAT_FEATURES, FEATURES, FORBIDDEN, add_date_features, assign_split,
                         cyclical, prepare_sets, split_bounds)
from ml.modeling import regression_metrics

AS_OF = "2026-10-26"


def test_split_bounds_match_assignment():
    train_start, test_start, as_of = split_bounds(AS_OF)
    assert train_start.date().isoformat() == "2026-07-26"
    assert test_start.date().isoformat() == "2026-10-05"
    assert as_of.date().isoformat() == AS_OF


def test_split_boundaries():
    dates = pd.Series(pd.to_datetime(
        ["2026-07-25", "2026-07-26", "2026-10-04", "2026-10-05", "2026-10-26", "2026-10-27"]))
    got = assign_split(dates, AS_OF).tolist()
    assert got == ["other", "train", "train", "test", "test", "future"]


def test_no_forbidden_or_leaky_features():
    assert not (set(FEATURES) & FORBIDDEN)
    assert len(FEATURES) == len(set(FEATURES))
    assert "origin_region" in CAT_FEATURES and "dest_region" in CAT_FEATURES


def test_cyclical_encoding_is_continuous_over_year_boundary():
    s, c = cyclical([12, 1], 12.0)
    d_dec_jan = math.hypot(s[0] - s[1], c[0] - c[1])
    s2, c2 = cyclical([1, 2], 12.0)
    d_jan_feb = math.hypot(s2[0] - s2[1], c2[0] - c2[1])
    assert abs(d_dec_jan - d_jan_feb) < 1e-9
    s3, c3 = cyclical([0, 7], 7.0)
    assert abs(s3[0] - s3[1]) < 1e-9 and abs(c3[0] - c3[1]) < 1e-9


def test_date_features_columns():
    df = add_date_features(pd.DataFrame({"loading_date": ["2026-12-31", "2027-01-01"]}))
    for col in ["year", "month_sin", "month_cos", "dow_sin", "dow_cos", "doy_sin", "doy_cos"]:
        assert col in df.columns
    assert df["year"].tolist() == [2026, 2027]


def _frame():
    rows = []
    base = dict(loading_city_gcid=1001, unloading_city_gcid=1003, distance=900.0, total_weight=20.0,
                total_volume=80.0, weight_category="FTL", volume_category="FTL", body_group="Tent",
                is_fact=True, complex=False, outlier_mark=False, origin_city="Moscow",
                origin_region="Moscow City", origin_lat=55.7, origin_lon=37.6, dest_city="Kazan",
                dest_region=None, dest_lat=55.8, dest_lon=49.1)
    specs = [
        (1, "2026-07-25", 80000, {}),
        (2, "2026-07-26", 80000, {}),
        (3, "2026-10-04", 81000, {}),
        (4, "2026-10-05", 82000, {}),
        (5, "2026-10-20", 83000, {"outlier_mark": True}),
        (6, "2026-10-21", 83000, {"complex": True}),
        (7, "2026-10-22", 83000, {"is_fact": False}),
        (8, "2026-10-23", 0, {}),
        (9, "2026-10-24", 84000, {}),
        (10, "2026-11-10", 152000, {}),
        (11, "2026-11-11", 90000, {"complex": True}),
    ]
    for pid, d, price, ov in specs:
        r = dict(base, price_id=pid, loading_date=d, price_rub=float(price))
        r.update(ov)
        rows.append(r)
    return pd.DataFrame(rows)


def test_prepare_sets_filters_and_no_overlap():
    train, test, future = prepare_sets(_frame(), AS_OF)
    assert sorted(train["price_id"]) == [2, 3]
    assert sorted(test["price_id"]) == [4, 9]
    assert sorted(future["price_id"]) == [10]
    assert not set(train["price_id"]) & set(test["price_id"])
    assert train["loading_date"].max() < test["loading_date"].min()
    assert (future["dest_region"] == "UNKNOWN").all()


def test_regression_metrics_known_values():
    m = regression_metrics([100.0, 200.0, 300.0], [110.0, 190.0, 330.0])
    assert abs(m["mae_rub"] - 50 / 3) < 1e-9
    assert abs(m["rmse_rub"] - math.sqrt((100 + 100 + 900) / 3)) < 1e-9
    assert abs(m["mape_pct"] - np.mean([10 / 100, 10 / 200, 30 / 300]) * 100) < 1e-9
    assert abs(m["r2"] - (1 - 1100 / 20000)) < 1e-9
