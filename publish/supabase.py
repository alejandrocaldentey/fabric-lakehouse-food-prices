"""Publish the data product to the public Supabase demo (ADR 0008, 0009).

    SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... python -m publish.supabase

Two kinds of table:

- keyed tables (countries, metrics, Diamond, chained indices) are upserted on their natural
  key, so official revisions overwrite old values;
- snapshot tables (models, backtest, forecasts, alerts, playbooks, platform metadata) carry a
  run_id. The run is written, marked complete in food_price_publish_log, and only then are
  older runs deleted. Readers filter on the latest complete run, so they never see a
  half-written snapshot.

Writes go through the PostgREST API with the service role, from CI only. The browser reads
the same tables with the publishable key, limited by RLS to SELECT.
"""

from __future__ import annotations

import json
import math
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import requests
import yaml

from decisions import build as decisions_build
from governance import build as governance_build
from ingestion.http import build_session
from metrics import build as metrics_build

ROOT = Path(__file__).resolve().parent.parent
KEYED = ("food_price_country", "food_price_metric", "food_price_diamond", "food_price_index")
SNAPSHOT = (
    "food_price_model",
    "food_price_backtest",
    "food_price_forecast",
    "food_price_model_coef",
    "food_price_alert_rule",
    "food_price_alert",
    "food_price_role",
    "food_price_play",
    "food_price_artifact",
)
TABLES = KEYED  # backwards-compatible name: keyed tables in FK order
SOURCE_NOTE = (
    "Eurostat apri_pi_outa (5 bases, chain-linked), prc_hicp_aind; World Bank FP.CPI.TOTL.ZG"
)


def _clean(value):
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def _rows(con, sql: str) -> list[dict]:
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    return [{c: _clean(v) for c, v in zip(cols, row, strict=True)} for row in cur.fetchall()]


def keyed_payloads(con) -> dict[str, list[dict]]:
    catalogue = metrics_build.load()
    metric_names = [m["name"] for m in catalogue["metrics"]]
    cols = ", ".join(["country_iso3", "year", *metric_names])
    return {
        "food_price_country": _rows(
            con,
            "SELECT country_iso3, country_name FROM dim_country "
            "WHERE country_iso3 IN (SELECT country_iso3 FROM diamond_country_year) ORDER BY 1",
        ),
        "food_price_metric": [
            {k: m[k] for k in ("name", "label", "description", "unit", "status", "owner")}
            | {"sort_order": i}
            for i, m in enumerate(catalogue["metrics"])
        ],
        "food_price_diamond": _rows(
            con, f"SELECT {cols} FROM diamond_country_year ORDER BY country_iso3, year"
        ),
        "food_price_index": _rows(
            con,
            "SELECT country_iso3, series_code, year, index_value, source_unit, source_value, "
            "rebase_factor, link_year FROM silver_price_index_chained "
            "WHERE country_iso3 IN (SELECT country_iso3 FROM diamond_country_year) ORDER BY 1, 2, 3",
        ),
    }


def _jsonable(obj):
    """YAML gives dates and other non-JSON types; the API needs plain JSON."""
    return json.loads(json.dumps(obj, default=str))


def platform_artifacts(con, stats: dict) -> list[dict]:
    """Metadata documents the architecture page renders: generated from the code, never drawn."""
    edges = governance_build.lineage()
    nodes = sorted(set(edges) | {u for ups in edges.values() for u in ups})
    contracts = {
        p.stem: yaml.safe_load(p.read_text())
        for p in sorted((ROOT / "quality" / "contracts").glob("*.yaml"))
    }
    sql = {
        p.stem.split("_", 1)[1]: p.read_text()
        for p in sorted((ROOT / "transform" / "sql").glob("[0-9][0-9]_*.sql"))
    }
    sources = yaml.safe_load((ROOT / "ingestion" / "sources.yaml").read_text())["sources"]
    product = yaml.safe_load((ROOT / "governance" / "product.yaml").read_text())["product"]
    cost = yaml.safe_load((ROOT / "cost" / "model.yaml").read_text())
    docs = [
        {
            "name": "lineage",
            "body": {
                "edges": edges,
                "layers": {n: governance_build._layer(n) for n in nodes},
                "contracts": sorted(contracts),
            },
        },
        {"name": "contracts", "body": contracts},
        {"name": "sql", "body": sql},
        {"name": "sources", "body": sources},
        {"name": "product", "body": product},
        {"name": "cost", "body": cost},
        {"name": "run", "body": stats},
    ]
    return [{"name": d["name"], "body": _jsonable(d["body"])} for d in docs]


def snapshot_payloads(con, run_id: str, stats: dict) -> dict[str, list[dict]]:
    rules, books = decisions_build.load()
    data = {
        "food_price_model": _rows(
            con,
            "SELECT *, ROW_NUMBER() OVER (ORDER BY CASE model_id WHEN 'naive' THEN 0 "
            "WHEN 'panel_dl' THEN 1 ELSE 2 END) - 1 AS sort_order FROM ml_model_registry",
        ),
        "food_price_backtest": _rows(con, "SELECT * FROM ml_backtest"),
        "food_price_forecast": _rows(con, "SELECT * FROM ml_forecast"),
        "food_price_model_coef": _rows(
            con,
            "SELECT model_id, kind, COALESCE(country_iso3, '') AS country_iso3, term, value "
            "FROM ml_coefficient",
        ),
        "food_price_alert_rule": [
            {
                "rule_id": r["id"],
                "label": r["label"],
                "category": r["category"],
                "scope": r["scope"],
                "value_expression": r["value"],
                "unit": r["unit"],
                "levels": r["levels"],
                "message": r["message"],
                "sort_order": i,
            }
            for i, r in enumerate(rules)
        ],
        "food_price_alert": _rows(con, "SELECT * FROM decision_alert"),
        "food_price_role": [
            {"role_id": r["id"], "label": r["label"], "focus": r["focus"], "sort_order": i}
            for i, r in enumerate(books["roles"])
        ],
        "food_price_play": [
            {"rule_id": rule_id, "role_id": role_id, **play}
            for rule_id, plays in books["plays"].items()
            for role_id, play in plays.items()
        ],
        "food_price_artifact": platform_artifacts(con, stats),
    }
    for rows in data.values():
        for row in rows:
            row["run_id"] = run_id
    return data


def run_stats(con, started: datetime | None = None) -> dict:
    tables = [
        r[0]
        for r in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main' "
            "ORDER BY 1"
        ).fetchall()
    ]
    counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
    checked = [p.stem for p in (ROOT / "quality" / "contracts").glob("*.yaml") if p.stem in counts]
    champion = con.execute("SELECT model_id FROM ml_model_registry WHERE is_champion").fetchone()
    years = con.execute("SELECT MIN(year), MAX(year) FROM diamond_country_year").fetchone()
    finished = datetime.now(UTC)
    return {
        "finished_at": finished.isoformat(),
        "duration_s": round((finished - started).total_seconds(), 1) if started else None,
        "row_counts": counts,
        "contracts_passed": sorted(checked),
        "champion": champion[0] if champion else None,
        "years": list(years),
        "git_sha": os.environ.get("GITHUB_SHA"),
    }


def _headers(key: str, prefer: str) -> dict:
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }


def upsert(url: str, key: str, table: str, rows: list[dict], session: requests.Session) -> None:
    for i in range(0, len(rows), 1000):
        response = session.post(
            f"{url.rstrip('/')}/rest/v1/{table}",
            json=rows[i : i + 1000],
            headers=_headers(key, "resolution=merge-duplicates,return=minimal"),
            timeout=60,
        )
        if response.status_code >= 300:
            raise RuntimeError(
                f"Upsert into {table} failed: {response.status_code} {response.text[:300]}"
            )


def delete_other_runs(url: str, key: str, table: str, run_id: str, session) -> None:
    response = session.delete(
        f"{url.rstrip('/')}/rest/v1/{table}",
        params={"run_id": f"neq.{run_id}"},
        headers=_headers(key, "return=minimal"),
        timeout=60,
    )
    if response.status_code >= 300:
        raise RuntimeError(
            f"Cleanup of {table} failed: {response.status_code} {response.text[:300]}"
        )


def check_write_key(key: str) -> None:
    """Fail fast, with a clear message, if the key cannot write (a publishable/anon key)."""
    if key.startswith("sb_publishable_"):
        raise RuntimeError(
            "SUPABASE_SERVICE_ROLE_KEY holds the publishable key, which is read-only by design. "
            "Use the secret key (sb_secret_...) from Supabase > Settings > API keys."
        )
    if key.count(".") == 2:  # legacy JWT key: check its role claim without verifying it
        import base64
        import json

        body = key.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        if claims.get("role") != "service_role":
            raise RuntimeError(
                f"The Supabase key has role {claims.get('role')!r}; publishing needs service_role."
            )


def publish(
    con,
    url: str,
    key: str,
    git_sha: str | None = None,
    session=None,
    started: datetime | None = None,
    run_id: str | None = None,
) -> dict[str, int]:
    check_write_key(key)
    session = session or build_session()
    run_id = run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:6]
    stats = run_stats(con, started) | {"run_id": run_id, "git_sha": git_sha}
    keyed = keyed_payloads(con)
    snap = snapshot_payloads(con, run_id, stats)
    for table in KEYED:
        upsert(url, key, table, keyed[table], session)
    for table in SNAPSHOT:
        upsert(url, key, table, snap[table], session)
    log = {
        "git_sha": git_sha,
        "rows_diamond": len(keyed["food_price_diamond"]),
        "source_note": SOURCE_NOTE,
        "run_id": run_id,
        "status": "complete",
        "stats": stats,
    }
    upsert(url, key, "food_price_publish_log", [log], session)
    for table in SNAPSHOT:  # only after the new run is marked complete
        delete_other_runs(url, key, table, run_id, session)
    return {t: len(r) for t, r in (keyed | snap).items()}


def main() -> int:
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print(
            "SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set: nothing published.", file=sys.stderr
        )
        return 0
    from transform.pipeline import run

    started = datetime.now(UTC)
    counts = publish(run(), url, key, os.environ.get("GITHUB_SHA"), started=started)
    print(counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
