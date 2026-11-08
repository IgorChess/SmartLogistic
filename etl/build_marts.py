import argparse
import logging
from datetime import date

from etl.config import SQL_DIR, get_settings
from etl.db import connect
from etl.logging_setup import setup_logging
from etl.sqlutil import load_statements

log = logging.getLogger("mart")


def build_route_card(conn, as_of: date) -> int:
    with conn:
        with conn.cursor() as cur:
            for name, sql in load_statements(SQL_DIR / "04_mart_route_card.sql"):
                cur.execute(sql, {"as_of": as_of})
                if name == "build_mart":
                    rows = cur.rowcount
            cur.execute("SELECT reliability_level, count(*) FROM mart.route_card GROUP BY 1 ORDER BY 1")
            dist = dict(cur.fetchall())
    log.info("mart.route_card rebuilt as_of=%s rows=%d reliability=%s", as_of, rows, dist)
    return rows


def main() -> None:
    setup_logging()
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", type=date.fromisoformat)
    a = ap.parse_args()
    s = get_settings()
    conn = connect(s)
    try:
        build_route_card(conn, a.as_of or s.as_of)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
