"""Generate the alert SQL and the decision docs from decisions/rules.yaml and playbooks.yaml.

python -m decisions.build          # write the generated files
python -m decisions.build --check  # fail if they are out of date (used in CI)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
RULES = ROOT / "decisions" / "rules.yaml"
PLAYBOOKS = ROOT / "decisions" / "playbooks.yaml"
SQL_OUT = ROOT / "transform" / "sql" / "09_decision_alert.sql"
DOC_OUT = ROOT / "docs" / "decisions.md"

SEVERITIES = ("high", "medium")
CATEGORIES = {"market", "forecast", "data", "model"}


class RuleError(ValueError):
    pass


def load() -> tuple[list[dict], dict]:
    rules = yaml.safe_load(RULES.read_text())["rules"]
    books = yaml.safe_load(PLAYBOOKS.read_text())
    roles = {r["id"] for r in books["roles"]}
    ids = set()
    for r in rules:
        if r["id"] in ids:
            raise RuleError(f"duplicate rule {r['id']}")
        ids.add(r["id"])
        if r["category"] not in CATEGORIES or r["scope"] not in {"country", "platform"}:
            raise RuleError(f"rule {r['id']}: bad category or scope")
        if [lv["severity"] for lv in r["levels"]] != [
            s for s in SEVERITIES if s in {lv["severity"] for lv in r["levels"]}
        ]:
            raise RuleError(f"rule {r['id']}: levels must go from most to least severe")
    for rule_id, plays in books["plays"].items():
        if rule_id not in ids:
            raise RuleError(f"playbook for unknown rule {rule_id}")
        unknown = set(plays) - roles
        if unknown:
            raise RuleError(f"playbook {rule_id}: unknown roles {sorted(unknown)}")
    return rules, books


def _rule_sql(r: dict) -> str:
    value = f"({r['value']})"
    cases = "\n".join(
        f"            WHEN {lv['when'].format(value=value)} THEN '{lv['severity']}'"
        for lv in r["levels"]
    )
    fires = " OR ".join(f"({lv['when'].format(value=value)})" for lv in r["levels"])
    if r["scope"] == "country":
        source = "decision_alert_input AS a"
        keys = "a.country_iso3, a.year"
        where = f"{r['filter']} AND ({fires})" if r.get("filter") else fires
    else:
        source = "ml_model_registry AS m"
        keys = "CAST(NULL AS VARCHAR) AS country_iso3, m.trained_through AS year"
        where = f"m.is_champion AND ({fires})"
    return f"""    SELECT
        '{r["id"]}' AS rule_id,
        '{r["category"]}' AS category,
        {keys},
        CASE
{cases}
        END AS severity,
        {value} AS value
    FROM {source}
    WHERE {where}"""


def render_sql(rules: list[dict]) -> str:
    body = "\n\n    UNION ALL\n\n".join(_rule_sql(r) for r in rules)
    return f"""-- GENERATED from decisions/rules.yaml by `python -m decisions.build`. Do not edit by hand.
-- decision_alert: one row per fired rule, country and year, with its severity and value.
SELECT
    rule_id || ':' || COALESCE(country_iso3, 'ALL') || ':' || CAST(year AS VARCHAR) AS alert_id,
    *
FROM (
{body}
) AS fired
"""


def render_doc(rules: list[dict], books: dict) -> str:
    roles = {r["id"]: r for r in books["roles"]}
    lines = [
        "# Decision layer: alerts and playbooks",
        "",
        (
            "Generated from [`decisions/rules.yaml`](../decisions/rules.yaml) and "
            "[`decisions/playbooks.yaml`](../decisions/playbooks.yaml) by "
            "`python -m decisions.build` ([ADR 0012](adr/0012-decision-layer.md))."
        ),
        "",
        "## Rules",
        "",
        "| Rule | Category | Tests | High | Medium |",
        "|---|---|---|---|---|",
    ]
    for r in rules:
        lv = {x["severity"]: x["when"].format(value="value") for x in r["levels"]}
        lines.append(
            f"| `{r['id']}` {r['label']} | {r['category']} | `{r['value']}` | "
            f"`{lv.get('high', '-')}` | `{lv.get('medium', '-')}` |"
        )
    lines += ["", "## Roles", ""]
    lines += [f"- **{r['label']}** — {r['focus']}" for r in books["roles"]]
    for r in rules:
        plays = books["plays"].get(r["id"], {})
        if not plays:
            continue
        lines += [
            "",
            f"## When `{r['id']}` fires",
            "",
            "| Role | Business action | Data action | KPI | Horizon |",
            "|---|---|---|---|---|",
        ]
        for role_id, p in plays.items():
            lines.append(
                f"| {roles[role_id]['label']} | {p['business']} | {p['data']} | {p['kpi']} | {p['horizon']} |"
            )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    rules, books = load()
    outputs = {SQL_OUT: render_sql(rules), DOC_OUT: render_doc(rules, books)}
    stale = [p for p, text in outputs.items() if not p.exists() or p.read_text() != text]
    if args.check:
        for p in stale:
            print(
                f"stale: {p.relative_to(ROOT)} — run `python -m decisions.build`", file=sys.stderr
            )
        return 1 if stale else 0
    for p, text in outputs.items():
        p.write_text(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
