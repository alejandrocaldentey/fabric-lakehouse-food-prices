"""Publish Diamond, countries and the metric catalogue to the public Supabase demo.

    SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... python -m publish.supabase

Writes go through the PostgREST API with the service role, from CI only. The browser
reads the same tables with the publishable key, limited by RLS to SELECT
(serving/supabase/001_food_prices_public_schema.sql).
"""

from __future__ import annotations

import math
import os
import sys

import requests

from ingestion.http import build_session
from metrics import build as metrics_build

TABLES = ("food_price_country", "food_price_metric", "food_price_diamond")  # FK order


def _clean(value):
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def payloads(con) -> dict[str, list[dict]]:
    """Rows for each serving table, built from a finished DuckDB run."""
    catalogue = metrics_build.load()
    metric_names = [m["name"] for m in catalogue["metrics"]]

    diamond_cols = ["country_iso3", "year", *metric_names]
    diamond = [
        {c: _clean(v) for c, v in zip(diamond_cols, row, strict=True)}
        for row in con.execute(
            f"SELECT {', '.join(diamond_cols)} FROM diamond_country_year ORDER BY country_iso3, year"
        ).fetchall()
    ]
    countries = [
        {"country_iso3": iso3, "country_name": name}
        for iso3, name in con.execute(
            "SELECT country_iso3, country_name FROM dim_country "
            "WHERE country_iso3 IN (SELECT country_iso3 FROM diamond_country_year) ORDER BY 1"
        ).fetchall()
    ]
    metrics = [
        {k: m[k] for k in ("name", "label", "description", "unit", "status", "owner")}
        | {"sort_order": i}
        for i, m in enumerate(catalogue["metrics"])
    ]
    return {
        "food_price_country": countries,
        "food_price_metric": metrics,
        "food_price_diamond": diamond,
    }


def upsert(url: str, key: str, table: str, rows: list[dict], session: requests.Session) -> None:
    if not rows:
        return
    response = session.post(
        f"{url.rstrip('/')}/rest/v1/{table}",
        json=rows,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
        timeout=60,
    )
    if response.status_code >= 300:
        raise RuntimeError(
            f"Upsert into {table} failed: {response.status_code} {response.text[:300]}"
        )


def publish(con, url: str, key: str, git_sha: str | None = None, session=None) -> dict[str, int]:
    session = session or build_session()
    data = payloads(con)
    for table in TABLES:
        upsert(url, key, table, data[table], session)
    log = {
        "git_sha": git_sha,
        "rows_diamond": len(data["food_price_diamond"]),
        "source_note": "Eurostat apri_pi_outa, prc_hicp_aind; World Bank FP.CPI.TOTL.ZG",
    }
    upsert(url, key, "food_price_publish_log", [log], session)
    return {t: len(rows) for t, rows in data.items()}


def main() -> int:
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print(
            "SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set: nothing published.", file=sys.stderr
        )
        return 0
    from transform.pipeline import run

    counts = publish(run(), url, key, os.environ.get("GITHUB_SHA"))
    print(counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
