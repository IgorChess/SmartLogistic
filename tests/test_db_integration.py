import os
from datetime import date

import pytest

pytestmark = pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="requires a database: RUN_DB_TESTS=1")

from etl import build_marts, run_etl
from etl.config import get_settings
from etl.db import connect
from etl.rules import volume_category, weight_category

START, END = date(2026, 9, 1), date(2026, 10, 31)


def _scalar(conn, sql, *a):
    with conn.cursor() as cur:
        cur.execute(sql, a)
        return cur.fetchone()[0]


def _fingerprint(conn):
    with conn.cursor() as cur:
        cur.execute("""SELECT count(*), round(sum(price_rub)::numeric, 2), count(DISTINCT price_id)
                       FROM core.fct_price WHERE loading_date BETWEEN %s AND %s""", (START, END))
        core = cur.fetchone()
        cur.execute("SELECT count(*) FROM core.dq_quarantine_prices WHERE loading_date BETWEEN %s AND %s", (START, END))
        q = cur.fetchone()
        cur.execute("SELECT count(*), round(sum(median_trip)::numeric, 2) FROM mart.route_card")
        mart = cur.fetchone()
    return core, q, mart


def test_etl_is_idempotent_and_has_no_duplicates():
    s = get_settings()
    conn = connect(s)
    try:
        run_etl.run(conn, s, START, END)
        build_marts.build_route_card(conn, s.as_of)
        first = _fingerprint(conn)
        run_etl.run(conn, s, START, END)
        build_marts.build_route_card(conn, s.as_of)
        assert _fingerprint(conn) == first
        assert _scalar(conn, "SELECT count(*) - count(DISTINCT price_id) FROM core.fct_price") == 0
        assert _scalar(conn, "SELECT count(*) FROM (SELECT price_id, body_group FROM core.fct_price_body_group "
                             "GROUP BY 1, 2 HAVING count(*) > 1) t") == 0
    finally:
        conn.close()


def test_dq_rules_no_bad_rows_in_core_and_every_reject_has_reason():
    s = get_settings()
    conn = connect(s)
    try:
        run_etl.run(conn, s, START, END)
        assert _scalar(conn, "SELECT count(*) FROM core.fct_price WHERE price_rub <= 0 OR distance <= 0 "
                             "OR total_weight < 0 OR total_volume < 0") == 0
        assert _scalar(conn, "SELECT count(*) FROM core.fct_price WHERE currency_code = '643' AND price_raw <= 1000") == 0
        assert _scalar(conn, "SELECT count(*) FROM core.dq_quarantine_prices WHERE reason_code IS NULL") == 0
        src = _scalar(conn, "SELECT count(*) FROM prices WHERE loading_date BETWEEN %s AND %s", START, END)
        ok = _scalar(conn, "SELECT count(*) FROM core.fct_price WHERE loading_date BETWEEN %s AND %s", START, END)
        q = _scalar(conn, "SELECT count(*) FROM core.dq_quarantine_prices WHERE loading_date BETWEEN %s AND %s", START, END)
        assert src == ok + q
    finally:
        conn.close()


def test_sql_categories_match_python_reference():
    s = get_settings()
    conn = connect(s)
    try:
        run_etl.run(conn, s, START, END)
        with conn.cursor() as cur:
            cur.execute("""SELECT f.total_weight, f.weight_category
                           FROM core.fct_price f JOIN prices p ON p.id = f.price_id
                           WHERE p.weight_category IS NULL LIMIT 20000""")
            for w, wc in cur.fetchall():
                assert wc == weight_category(w), (w, wc)
            cur.execute("SELECT total_volume, volume_category FROM core.fct_price LIMIT 20000")
            for v, vc in cur.fetchall():
                assert vc == volume_category(v), (v, vc)
    finally:
        conn.close()


def test_mart_rules():
    s = get_settings()
    conn = connect(s)
    try:
        build_marts.build_route_card(conn, s.as_of)
        assert _scalar(conn, "SELECT count(*) FROM mart.route_card WHERE month_start > %s", s.as_of) == 0
        assert _scalar(conn, "SELECT count(*) FROM mart.route_card WHERE carriers_count > trips_count") == 0
        assert _scalar(conn, "SELECT count(*) FROM mart.route_card WHERE NOT (p25_trip <= median_trip "
                             "AND median_trip <= p75_trip)") == 0
        assert _scalar(conn, "SELECT count(*) FROM mart.route_card WHERE trips_count < 2 AND cv_rate IS NOT NULL") == 0
    finally:
        conn.close()
