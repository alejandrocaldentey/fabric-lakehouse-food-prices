"""Run the silver and gold SQL on DuckDB — locally and in CI.

In Fabric, a notebook runs the same files in the same order with ``spark.sql`` and
``saveAsTable``. Each ``NN_<table>.sql`` file is a single SELECT; the table takes the
file name without its numeric prefix.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import duckdb

from quality.check import check_contract
from transform.staging import (
    BRONZE_EUROSTAT_COLUMNS,
    BRONZE_WORLDBANK_COLUMNS,
    series_by_dataset,
    stage_eurostat,
    stage_worldbank,
)

ROOT = Path(__file__).resolve().parent
SQL_DIR = ROOT / "sql"
SEED_DIR = ROOT / "seeds"
# every table with a contract in quality/contracts/ is checked right after it is built
CONTRACTS = {p.stem: p for p in (ROOT.parent / "quality" / "contracts").glob("*.yaml")}


def _create(
    con: duckdb.DuckDBPyConnection, table: str, columns: list[str], rows: list[dict]
) -> None:
    cols = ", ".join(f"{c} VARCHAR" for c in columns)
    con.execute(f"CREATE OR REPLACE TABLE {table} ({cols})")
    if rows:
        marks = ", ".join("?" for _ in columns)
        con.executemany(
            f"INSERT INTO {table} VALUES ({marks})",
            [[None if r.get(c) is None else str(r.get(c)) for c in columns] for r in rows],
        )


def load_seeds(con: duckdb.DuckDBPyConnection) -> None:
    for path in sorted(SEED_DIR.glob("*.csv")):
        with path.open(newline="") as f:
            rows = list(csv.DictReader(f))
        table = f"seed_{path.stem}" if path.stem != "country_codes" else "seed_country"
        _create(con, table, list(rows[0].keys()), rows)
    con.execute(
        "CREATE OR REPLACE TABLE seed_country AS SELECT CAST(m49 AS INT) AS m49, iso2, iso3, name FROM seed_country"
    )


def table_name(sql_file: Path) -> str:
    return sql_file.stem.split("_", 1)[1]


def build(
    worldbank_rows: list[dict],
    eurostat_rows: list[dict],
    con: duckdb.DuckDBPyConnection | None = None,
) -> duckdb.DuckDBPyConnection:
    """Load bronze rows, run every SQL file in order and check contracts. Returns the connection."""
    con = con or duckdb.connect()
    load_seeds(con)
    _create(
        con,
        "bronze_worldbank",
        BRONZE_WORLDBANK_COLUMNS,
        [stage_worldbank(r) for r in worldbank_rows],
    )
    series = series_by_dataset()
    _create(
        con,
        "bronze_eurostat",
        BRONZE_EUROSTAT_COLUMNS,
        [stage_eurostat(r, series) for r in eurostat_rows],
    )
    for sql_file in sorted(SQL_DIR.glob("[0-9][0-9]_*.sql")):
        name = table_name(sql_file)
        con.execute(f"CREATE OR REPLACE TABLE {name} AS {sql_file.read_text()}")
        if name in CONTRACTS:
            check_contract(con, CONTRACTS[name])  # fail before any gold table is built
    return con


def _read_jsonl(path: Path | None) -> list[dict]:
    if not path:
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build silver and gold on DuckDB from bronze JSON lines."
    )
    parser.add_argument(
        "--worldbank", type=Path, help="JSON lines from `python -m ingestion.worldbank`"
    )
    parser.add_argument(
        "--eurostat", type=Path, help="JSON lines from `python -m ingestion.eurostat`"
    )
    parser.add_argument(
        "--out", type=Path, default=Path("data/gold"), help="folder for Parquet output"
    )
    args = parser.parse_args(argv)
    con = build(_read_jsonl(args.worldbank), _read_jsonl(args.eurostat))
    args.out.mkdir(parents=True, exist_ok=True)
    for table in (
        "dim_country",
        "dim_series",
        "fact_price_annual",
        "gold_price_transmission",
        "diamond_country_year",
    ):
        con.execute(f"COPY {table} TO '{args.out / table}.parquet' (FORMAT PARQUET)")
        count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"{table}: {count} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
