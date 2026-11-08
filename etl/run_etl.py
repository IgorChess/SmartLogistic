import argparse
import logging
from calendar import monthrange
from datetime import date, timedelta

from etl.config import SQL_DIR, Settings, get_settings
from etl.db import connect
from etl.logging_setup import setup_logging
from etl.sqlutil import load_statements

log = logging.getLogger("etl")


def month_chunks(start: date, end: date):
    cur = start
    while cur <= end:
        last_day = date(cur.year, cur.month, monthrange(cur.year, cur.month)[1])
        yield cur, min(last_day, end)
        cur = last_day + timedelta(days=1)


def init_dwh(conn) -> None:
    with conn:
        with conn.cursor() as cur:
            for name, sql in load_statements(SQL_DIR / "01_init_dwh.sql"):
                cur.execute(sql)
    log.info("core and mart DDL applied")


def load_dims(conn) -> None:
    with conn:
        with conn.cursor() as cur:
            for name, sql in load_statements(SQL_DIR / "02_load_dims.sql"):
                cur.execute(sql)
                log.info("dim %-14s upserted rows: %d", name, cur.rowcount)


def load_chunk(conn, start: date, end: date) -> dict:
    params = {"start_date": start, "end_date": end}
    stats: dict = {}
    with conn:
        with conn.cursor() as cur:
            for name, sql in load_statements(SQL_DIR / "03_load_core.sql"):
                cur.execute(sql, params)
                stats[name] = cur.rowcount
                if name == "stg_prices":
                    cur.execute("SELECT coalesce(reason_code, 'OK'), count(*) FROM stg_prices GROUP BY 1 ORDER BY 1")
                    stats["by_reason"] = dict(cur.fetchall())
            cur.execute(
                "INSERT INTO core.etl_run_log (step, window_start, window_end, rows_read, rows_loaded, rows_quarantined)"
                " VALUES ('load_core', %s, %s, %s, %s, %s)",
                (start, end, stats["stg_prices"], stats["insert_fct_price"], stats["insert_quarantine"]),
            )
    return stats


def run(conn, s: Settings, start: date | None = None, end: date | None = None) -> None:
    init_dwh(conn)
    load_dims(conn)
    if start is None or end is None:
        with conn.cursor() as cur:
            cur.execute("SELECT min(loading_date), max(loading_date) FROM prices")
            src_min, src_max = cur.fetchone()
        conn.commit()
        start, end = start or src_min, end or src_max
    if start is None or end is None or start > end:
        log.warning("empty ETL window (%s..%s), nothing to load", start, end)
        return
    log.info("ETL window: %s .. %s", start, end)
    tot_read = tot_ok = tot_q = 0
    for cs, ce in month_chunks(start, end):
        st = load_chunk(conn, cs, ce)
        tot_read += st["stg_prices"]
        tot_ok += st["insert_fct_price"]
        tot_q += st["insert_quarantine"]
        log.info("%s..%s read=%d loaded=%d quarantined=%d reasons=%s",
                 cs, ce, st["stg_prices"], st["insert_fct_price"], st["insert_quarantine"], st["by_reason"])
    log.info("ETL total: read=%d loaded=%d quarantined=%d", tot_read, tot_ok, tot_q)
    log.info("source limitation: deals of the last snapshot day (%s) may have not passed the nightly "
             "outlier marking job and carry outlier_mark=false by default", s.as_of)


def main() -> None:
    setup_logging()
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-date", type=date.fromisoformat)
    ap.add_argument("--end-date", type=date.fromisoformat)
    a = ap.parse_args()
    s = get_settings()
    conn = connect(s)
    try:
        run(conn, s, a.start_date or s.etl_start, a.end_date or s.etl_end)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
