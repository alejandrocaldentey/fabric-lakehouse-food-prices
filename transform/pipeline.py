"""End-to-end run on live data: plan each source, fetch it, build silver -> Diamond.

    python -m transform.pipeline --out data/gold

This is what CI runs before publishing to the public demo. In Fabric, the same steps
are split across a pipeline: ingestion notebook -> silver MERGE -> gold/Diamond notebook.
"""

from __future__ import annotations

import argparse
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb

from ingestion import eurostat, worldbank
from ingestion.plan import load_sources, plan
from transform import run_local


def fetch_all(
    today: date, last_loaded: dict[str, int] | None = None
) -> tuple[list[dict], list[dict]]:
    """Fetch every registered source according to its load plan. Returns (worldbank, eurostat)."""
    last_loaded = last_loaded or {}
    wb_rows: list[dict] = []
    es_rows: list[dict] = []
    for src in load_sources():
        p = plan(src, today, last_loaded.get(src["id"]))
        if src["api"] == "eurostat":
            es_rows += eurostat.fetch_dataset(src["dataset"], src.get("filters"), str(p.since_year))
        elif src["api"] == "worldbank":
            rows = worldbank.fetch_indicator(
                src["indicator"], "all", f"{p.since_year}:{today.year}"
            )
            wb_rows += [o.__dict__ for o in rows]
        else:
            raise ValueError(f"No client for api {src['api']!r}")
    return wb_rows, es_rows


def run(today: date | None = None) -> duckdb.DuckDBPyConnection:
    wb_rows, es_rows = fetch_all(today or datetime.now(UTC).date())
    return run_local.build(wb_rows, es_rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch live data and build silver, gold and Diamond."
    )
    parser.add_argument("--out", type=Path, default=Path("data/gold"))
    args = parser.parse_args(argv)
    con = run()
    args.out.mkdir(parents=True, exist_ok=True)
    for table in (
        "dim_country",
        "fact_price_annual",
        "gold_price_transmission",
        "diamond_country_year",
    ):
        con.execute(f"COPY {table} TO '{args.out / table}.parquet' (FORMAT PARQUET)")
        print(f"{table}: {con.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
