import argparse
import logging
import random
from datetime import date

import numpy as np
import pandas as pd
from psycopg2.extras import execute_values

from etl.config import get_settings
from etl.db import connect, fetch_df
from etl.logging_setup import setup_logging
from ml.features import DATASET_SQL, FEATURES, TARGET, prepare_sets, split_bounds
from ml.modeling import train_and_evaluate

log = logging.getLogger("ml")


def build_predictions(model, model_name: str, part: pd.DataFrame, split: str) -> pd.DataFrame:
    out = pd.DataFrame({
        "price_id": part["price_id"].to_numpy(),
        "model_name": model_name,
        "split": split,
        "loading_date": pd.to_datetime(part["loading_date"]).dt.date.to_numpy(),
        "loading_city_gcid": part["loading_city_gcid"].to_numpy(),
        "unloading_city_gcid": part["unloading_city_gcid"].to_numpy(),
        "body_group": part["body_group"].to_numpy(),
    })
    pred = model.predict(part[FEATURES])
    out["predicted_price_rub"] = pred
    if split == "test":
        actual = part[TARGET].to_numpy(dtype=float)
        out["actual_price_rub"] = actual
        out["abs_error_rub"] = np.abs(actual - pred)
        out["ape_pct"] = np.abs(actual - pred) / actual * 100.0
    else:
        out["actual_price_rub"] = np.nan
        out["abs_error_rub"] = np.nan
        out["ape_pct"] = np.nan
    return out


def _py(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    return v.item() if hasattr(v, "item") else v


def write_predictions(conn, preds: pd.DataFrame, model_name: str) -> None:
    cols = ["price_id", "model_name", "split", "loading_date", "loading_city_gcid", "unloading_city_gcid",
            "body_group", "actual_price_rub", "predicted_price_rub", "abs_error_rub", "ape_pct"]
    rows = [tuple(_py(v) for v in r) for r in preds[cols].itertuples(index=False, name=None)]
    with conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM mart.ml_price_predictions WHERE model_name = %s", (model_name,))
            execute_values(
                cur,
                f"INSERT INTO mart.ml_price_predictions ({', '.join(cols)}) VALUES %s",
                rows, page_size=10000)
    log.info("mart.ml_price_predictions: model=%s rows written=%d", model_name, len(rows))


def write_metrics(conn, metrics: dict, as_of: date) -> None:
    with conn:
        with conn.cursor() as cur:
            for name, m in metrics.items():
                cur.execute(
                    """INSERT INTO mart.ml_model_metrics
                           (model_name, as_of, n_train, n_test, r2, mape_pct, rmse_rub, mae_rub, trained_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s, now())
                       ON CONFLICT (model_name, as_of) DO UPDATE SET
                           n_train=EXCLUDED.n_train, n_test=EXCLUDED.n_test, r2=EXCLUDED.r2,
                           mape_pct=EXCLUDED.mape_pct, rmse_rub=EXCLUDED.rmse_rub,
                           mae_rub=EXCLUDED.mae_rub, trained_at=EXCLUDED.trained_at""",
                    (name, as_of, m["n_train"], m["n_test"], m["r2"], m["mape_pct"], m["rmse_rub"], m["mae_rub"]))


def run(conn, as_of: date, seed: int) -> dict:
    random.seed(seed)
    np.random.seed(seed)
    train_start, test_start, _ = split_bounds(as_of)
    log.info("as_of=%s train=[%s; %s) test=[%s; %s] seed=%d", as_of, train_start.date(), test_start.date(),
             test_start.date(), as_of, seed)
    df = fetch_df(conn, DATASET_SQL, {"from_date": train_start.date()})
    train, test, future = prepare_sets(df, as_of)
    log.info("dataset sizes: train=%d test=%d future=%d", len(train), len(test), len(future))
    if len(train) == 0 or len(test) == 0:
        log.error("empty train or test set, check that the ETL has run")
        return {}
    primary, models, metrics = train_and_evaluate(train, test, seed)
    model = models[primary]
    parts = [build_predictions(model, primary, test, "test")]
    if len(future):
        parts.append(build_predictions(model, primary, future, "future"))
    write_predictions(conn, pd.concat(parts, ignore_index=True), primary)
    write_metrics(conn, metrics, as_of)
    return metrics


def main() -> None:
    setup_logging()
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", type=date.fromisoformat)
    a = ap.parse_args()
    s = get_settings()
    conn = connect(s)
    try:
        run(conn, a.as_of or s.as_of, s.seed)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
