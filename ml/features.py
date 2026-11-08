import numpy as np
import pandas as pd

CAT_FEATURES = ["origin_city", "origin_region", "dest_city", "dest_region",
                "body_group", "weight_category", "volume_category"]
NUM_FEATURES = ["distance", "total_weight", "total_volume",
                "origin_lat", "origin_lon", "dest_lat", "dest_lon",
                "year", "month_sin", "month_cos", "dow_sin", "dow_cos", "doy_sin", "doy_cos"]
FEATURES = CAT_FEATURES + NUM_FEATURES
TARGET = "price_rub"

FORBIDDEN = {"price_with_vat", "price_raw", "price_rub", "price", "price_km", "price_per_km",
             "price_per_ton", "customer_cost", "transportation_cost", "profit", "carrier_cost",
             "avg_price", "min_km_price", "max_km_price", "price_group_id", "outlier_mark", "fx_rate"}

DATASET_SQL = """
SELECT f.price_id, f.loading_date, f.loading_city_gcid, f.unloading_city_gcid,
       f.distance, f.total_weight, f.total_volume, f.weight_category, f.volume_category,
       f.body_group_primary AS body_group,
       f.price_rub, f.is_fact, f.complex, f.outlier_mark,
       lc.city_name AS origin_city, lc.region AS origin_region,
       lc.latitude AS origin_lat, lc.longitude AS origin_lon,
       uc.city_name AS dest_city,   uc.region AS dest_region,
       uc.latitude AS dest_lat,     uc.longitude AS dest_lon
FROM core.fct_price f
JOIN core.dim_city lc ON lc.gc_id = f.loading_city_gcid
JOIN core.dim_city uc ON uc.gc_id = f.unloading_city_gcid
WHERE f.loading_date >= %(from_date)s AND NOT f.complex
"""

def cyclical(values, period: float):
    ang = 2.0 * np.pi * np.asarray(values, dtype=float) / period
    return np.sin(ang), np.cos(ang)

def add_date_features(df: pd.DataFrame, date_col: str = "loading_date") -> pd.DataFrame:
    out = df.copy()
    d = pd.to_datetime(out[date_col])
    out["year"] = d.dt.year
    for name, vals, period in (("month", d.dt.month, 12.0),
                               ("dow", d.dt.dayofweek, 7.0),
                               ("doy", d.dt.dayofyear, 365.25)):
        out[f"{name}_sin"], out[f"{name}_cos"] = cyclical(vals, period)
    return out

def split_bounds(as_of):
    as_of = pd.Timestamp(as_of)
    train_start = as_of - pd.DateOffset(months=3)
    test_start = as_of - pd.Timedelta(weeks=3)
    return train_start, test_start, as_of

def assign_split(dates: pd.Series, as_of) -> pd.Series:
    train_start, test_start, as_of = split_bounds(as_of)
    d = pd.to_datetime(dates)
    return pd.Series(
        np.select([(d >= train_start) & (d < test_start),
                   (d >= test_start) & (d <= as_of),
                   d > as_of],
                  ["train", "test", "future"], default="other"),
        index=dates.index)

def prepare_sets(df: pd.DataFrame, as_of):
    df = add_date_features(df)
    df["split"] = assign_split(df["loading_date"], as_of)
    hist_ok = (df["is_fact"] & ~df["complex"] & ~df["outlier_mark"]
               & (df[TARGET] > 0) & (df["distance"] > 0))
    train = df[(df["split"] == "train") & hist_ok].copy()
    test = df[(df["split"] == "test") & hist_ok].copy()
    future = df[(df["split"] == "future") & ~df["complex"]].copy()
    for part in (train, test, future):
        part[CAT_FEATURES] = part[CAT_FEATURES].fillna("UNKNOWN").astype(str)
    return train, test, future
