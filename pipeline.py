import logging

from etl import build_marts, run_etl
from etl.config import get_settings
from etl.db import connect
from etl.logging_setup import setup_logging

log = logging.getLogger("pipeline")


def main() -> None:
    setup_logging()
    s = get_settings()
    conn = connect(s)
    try:
        run_etl.run(conn, s, s.etl_start, s.etl_end)
        build_marts.build_route_card(conn, s.as_of)
        if s.run_ml:
            from ml import run as ml_run
            ml_run.run(conn, s.as_of, s.seed)
        else:
            log.info("RUN_ML=0, ML step skipped")
    finally:
        conn.close()
    log.info("pipeline finished")


if __name__ == "__main__":
    main()
