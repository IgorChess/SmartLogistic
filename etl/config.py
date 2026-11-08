import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = ROOT / "sql" / "dwh"


def _date(name: str, default: str | None = None) -> date | None:
    raw = os.getenv(name, default)
    return date.fromisoformat(raw) if raw else None


@dataclass(frozen=True)
class Settings:
    host: str = os.getenv("PGHOST", "localhost")
    port: int = int(os.getenv("PGPORT", "5432"))
    user: str = os.getenv("PGUSER", "postgres")
    password: str = os.getenv("PGPASSWORD", "")
    dbname: str = os.getenv("PGDATABASE", "deals_bigdata")
    as_of: date = _date("AS_OF_DATE", "2026-10-26")
    etl_start: date | None = _date("ETL_START_DATE")
    etl_end: date | None = _date("ETL_END_DATE")
    seed: int = int(os.getenv("RANDOM_SEED", "42"))
    run_ml: bool = os.getenv("RUN_ML", "1") == "1"


def get_settings() -> Settings:
    return Settings()
