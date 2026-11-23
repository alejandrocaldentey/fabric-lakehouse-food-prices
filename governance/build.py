"""Build table-level lineage from the SQL files and render docs/governance.md.

Lineage is read from the code, not drawn by hand, so it cannot drift from what runs.
The same JSON (``lineage()``) feeds the governance portal of case 3.

    python -m governance.build          # write docs/governance.md
    python -m governance.build --check  # fail if it is out of date (used in CI)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = ROOT / "transform" / "sql"
PRODUCT = ROOT / "governance" / "product.yaml"
SOURCES = ROOT / "ingestion" / "sources.yaml"
CONTRACTS = ROOT / "quality" / "contracts"
DOC_OUT = ROOT / "docs" / "governance.md"

_REF = re.compile(r"\b(?:FROM|JOIN)\s+([a-z_][a-z0-9_]*)", re.IGNORECASE)
_CTE = re.compile(r"(?:\bWITH|,)\s*([a-z_][a-z0-9_]*)\s+AS\s*\(", re.IGNORECASE)
_COMMENT = re.compile(r"--[^\n]*")


def table_refs(sql: str) -> set[str]:
    """Tables a SELECT reads from, excluding its own CTEs."""
    sql = _COMMENT.sub("", sql)
    ctes = {c.lower() for c in _CTE.findall(sql)}
    return {r.lower() for r in _REF.findall(sql)} - ctes


def lineage() -> dict[str, list[str]]:
    """table -> sorted upstream tables, for every SQL file in build order."""
    out = {}
    for path in sorted(SQL_DIR.glob("[0-9][0-9]_*.sql")):
        out[path.stem.split("_", 1)[1]] = sorted(table_refs(path.read_text()))
    return out


def _layer(table: str) -> str:
    for prefix, layer in (
        ("bronze_", "Bronze"),
        ("seed_", "Seeds"),
        ("silver_", "Silver"),
        ("diamond_", "Diamond"),
    ):
        if table.startswith(prefix):
            return layer
    return "Gold"


def render(product: dict, sources: list[dict], edges: dict[str, list[str]]) -> str:
    p = product["product"]
    contracts = sorted(c.stem for c in CONTRACTS.glob("*.yaml"))
    lines = [
        f"# Governance — {p['title']}",
        "",
        "Generated from [`governance/product.yaml`](../governance/product.yaml), the source registry and the SQL itself by `python -m governance.build`.",
        "",
        "## Data product",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Name | `{p['name']}` |",
        f"| Domain | {p['domain']} |",
        f"| Owner | {p['owner']} |",
        f"| Purpose | {p['purpose']} |",
        f"| Classification | {p['classification']} (personal data: {'yes' if p['personal_data'] else 'no'}) |",
        f"| Licence | {p['licence']} |",
        f"| Freshness SLA | {p['sla']['freshness']} |",
        f"| Consumers | {'; '.join(p['consumers'])} |",
        "",
        "## Output ports",
        "",
        "| Table | Description | Contract |",
        "|---|---|---|",
    ]
    for port in p["output_ports"]:
        lines.append(
            f"| `{port['table']}` | {port['description']} | [{port['contract']}](../{port['contract']}) |"
        )
    lines += [
        "",
        "## Sources",
        "",
        "| Source | Dataset / indicator | Load strategy |",
        "|---|---|---|",
    ]
    for s in sources:
        ref = s.get("dataset") or s.get("indicator")
        load = s["load"]
        window = f" ({load['window_years']} years)" if "window_years" in load else ""
        lines.append(f"| {s['api']} | `{ref}` | {load['strategy']}{window} |")

    lines += ["", "## Lineage", "", "```mermaid", "flowchart LR"]
    nodes = set(edges) | {u for ups in edges.values() for u in ups}
    by_layer: dict[str, list[str]] = {}
    for n in sorted(nodes):
        by_layer.setdefault(_layer(n), []).append(n)
    for layer in ("Seeds", "Bronze", "Silver", "Gold", "Diamond"):
        if layer in by_layer:
            lines.append(f"    subgraph {layer}")
            lines += [
                f"        {n}{'[(' + n + ')]' if n in contracts else ''}" for n in by_layer[layer]
            ]
            lines.append("    end")
    for table, ups in edges.items():
        lines += [f"    {u} --> {table}" for u in ups]
    lines += [
        "```",
        "",
        "Tables drawn as cylinders have a data contract, checked right after they are built.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    text = render(
        yaml.safe_load(PRODUCT.read_text()),
        yaml.safe_load(SOURCES.read_text())["sources"],
        lineage(),
    )
    stale = not DOC_OUT.exists() or DOC_OUT.read_text() != text
    if args.check:
        if stale:
            print("stale: docs/governance.md — run `python -m governance.build`", file=sys.stderr)
        return 1 if stale else 0
    DOC_OUT.write_text(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
