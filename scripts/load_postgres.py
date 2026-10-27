"""Copy the generated DWP SQLite tables into Postgres (used by docker compose).

Usage: python scripts/load_postgres.py postgresql+psycopg://unclaimed:unclaimed@localhost:5432/dwp
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]


def main(url: str) -> None:
    src = sqlite3.connect(ROOT / "data" / "generated" / "dwp.sqlite")
    eng = create_engine(url)
    with eng.begin() as dst:
        for (name, ddl) in src.execute("SELECT name, sql FROM sqlite_master WHERE type='table'"):
            dst.execute(text(f"DROP TABLE IF EXISTS {name}"))
            dst.execute(text(ddl))
            cur = src.execute(f"SELECT * FROM {name}")
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur]
            if rows:
                dst.execute(text(f"INSERT INTO {name} ({', '.join(cols)}) VALUES ({', '.join(':' + c for c in cols)})"), rows)
            print(f"{name}: {len(rows)} rows")


if __name__ == "__main__":
    main(sys.argv[1])
