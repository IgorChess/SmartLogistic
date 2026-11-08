import logging
import time

import pandas as pd
import psycopg2

from etl.config import Settings

log = logging.getLogger(__name__)


def connect(s: Settings, retries: int = 30, delay: float = 2.0):
    last = None
    for attempt in range(1, retries + 1):
        try:
            return psycopg2.connect(host=s.host, port=s.port, user=s.user,
                                    password=s.password, dbname=s.dbname)
        except psycopg2.OperationalError as e:
            last = e
            log.warning("database unavailable (attempt %d/%d): %s", attempt, retries, str(e).strip())
            time.sleep(delay)
    raise last


def fetch_df(conn, sql: str, params: dict | None = None) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(sql, params or {})
        cols = [d.name for d in cur.description]
        rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)
