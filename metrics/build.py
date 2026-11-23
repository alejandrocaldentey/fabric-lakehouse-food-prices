"""Generate the Diamond SQL and the metric docs from metrics/metrics.yaml.

python -m metrics.build          # write the generated files
python -m metrics.build --check  # fail if they are out of date (used in CI)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CATALOGUE = ROOT / "metrics" / "metrics.yaml"
SQL_OUT = ROOT / "transform" / "sql" / "06_diamond_country_year.sql"
DOC_OUT = ROOT / "docs" / "metrics.md"

NAME = re.compile(r"^[a-z][a-z0-9_]*$")
STATUSES = {"certified", "experimental", "deprecated"}
REQUIRED = ("name", "label", "description", "unit", "expression", "status", "owner")


class CatalogueError(ValueError):
    pass


def load(path: Path = CATALOGUE) -> dict:
    catalogue = yaml.safe_load(path.read_text())
    seen = set()
    for m in catalogue["metrics"]:
        missing = [k for k in REQUIRED if not m.get(k)]
        if missing:
            raise CatalogueError(f"metric {m.get('name')!r} is missing {missing}")
        if not NAME.match(m["name"]) or m["name"] in seen:
            raise CatalogueError(f"metric name {m['name']!r} is invalid or duplicated")
        if m["status"] not in STATUSES:
            raise CatalogueError(f"metric {m['name']!r} has unknown status {m['status']!r}")
        seen.add(m["name"])
    return catalogue


def render_sql(catalogue: dict) -> str:
    cols = ",\n".join(f"    {m['expression']} AS {m['name']}" for m in catalogue["metrics"])
    return f"""-- GENERATED from metrics/metrics.yaml by `python -m metrics.build`. Do not edit by hand.
-- {catalogue["table"]}: one row per country and year, one column per catalogued metric.
WITH c AS (
    SELECT country_iso3, year, value AS cpi_inflation
    FROM fact_price_annual
    WHERE series_code = 'CPI_INFLATION'
)

SELECT
    t.country_iso3,
    t.year,
{cols}
FROM gold_price_transmission AS t
LEFT JOIN c
    ON t.country_iso3 = c.country_iso3
    AND t.year = c.year
"""


def render_doc(catalogue: dict) -> str:
    lines = [
        "# Metric catalogue",
        "",
        (
            "Generated from [`metrics/metrics.yaml`](../metrics/metrics.yaml). Every published "
            f"number comes from one definition here and is materialised in `{catalogue['table']}` "
            f"(grain: {', '.join(catalogue['grain'])})."
        ),
        "",
        "| Metric | Label | Unit | Status | Definition | Owner |",
        "|---|---|---|---|---|---|",
    ]
    for m in catalogue["metrics"]:
        expr = m["expression"].replace("|", "\\|")
        lines.append(
            f"| `{m['name']}` | {m['label']} | {m['unit']} | {m['status']} | "
            f"{m['description']}<br>`{expr}` | {m['owner']} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if generated files are stale")
    args = parser.parse_args(argv)
    catalogue = load()
    outputs = {SQL_OUT: render_sql(catalogue), DOC_OUT: render_doc(catalogue)}
    stale = [p for p, text in outputs.items() if not p.exists() or p.read_text() != text]
    if args.check:
        for p in stale:
            print(f"stale: {p.relative_to(ROOT)} — run `python -m metrics.build`", file=sys.stderr)
        return 1 if stale else 0
    for p, text in outputs.items():
        p.write_text(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
