"""Generate the Direct Lake semantic model (TMDL) and the data agent instructions.

Inputs, none of them repeated here:
  semantic/model.yaml      which tables, relationships, hidden columns and number formats
  metrics/metrics.yaml     every measure: name, description, unit, status and rollup (ADR 0006)
  transform/sql/*.sql      the column types, read from the tables the pipeline really builds

Outputs:
  fabric/FoodPriceTransmission.SemanticModel/   TMDL item folder for Fabric Git integration
  fabric/data-agent/instructions.md             instructions for the Fabric data agent
  docs/semantic-model.md                        human-readable model reference

    python -m semantic.build          # write the generated files
    python -m semantic.build --check  # fail if they are out of date (used in CI)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from pathlib import Path

import yaml

from metrics import build as metrics_build

ROOT = Path(__file__).resolve().parent.parent
MODEL_SPEC = ROOT / "semantic" / "model.yaml"
FABRIC_DIR = ROOT / "fabric"
AGENT_OUT = FABRIC_DIR / "data-agent" / "instructions.md"
DOC_OUT = ROOT / "docs" / "semantic-model.md"

# Stable ids: regenerating the model never changes a lineage tag, so Git diffs stay readable
# and Fabric keeps report bindings across deployments.
_NAMESPACE = uuid.UUID("6f1c2a4e-9d3b-5e7a-8c1f-2b4d6e8f0a13")

# DuckDB type of the locally built table -> TMDL dataType (Delta types map the same way)
_TYPES = {
    "VARCHAR": "string",
    "INTEGER": "int64",
    "BIGINT": "int64",
    "SMALLINT": "int64",
    "HUGEINT": "int64",
    "DOUBLE": "double",
    "FLOAT": "double",
    "BOOLEAN": "boolean",
    "DATE": "dateTime",
    "TIMESTAMP": "dateTime",
    "TIMESTAMP WITH TIME ZONE": "dateTime",
}
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_DAX_COLUMN_REF = re.compile(r"\b([a-z_][a-z0-9_]*)\[([a-z_][a-z0-9_]*)\]")


class ModelError(ValueError):
    pass


def tag(*parts: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, "/".join(parts)))


def quote(name: str) -> str:
    """TMDL object name: bare when it is an identifier, single-quoted otherwise."""
    return name if _IDENT.match(name) else "'" + name.replace("'", "''") + "'"


def item_dir(spec: dict) -> Path:
    return FABRIC_DIR / f"{spec['name']}.SemanticModel"


def table_schemas(tables: list[str]) -> dict[str, list[tuple[str, str]]]:
    """Column names and TMDL types of each table, read from an empty local build of the pipeline."""
    from transform import run_local

    con = run_local.build([], [])
    out = {}
    for table in tables:
        cols = []
        for name, duck_type, *_ in con.execute(f"DESCRIBE {table}").fetchall():
            if duck_type not in _TYPES:
                raise ModelError(f"{table}.{name}: no TMDL type for {duck_type}")
            cols.append((name, _TYPES[duck_type]))
        out[table] = cols
    return out


def measures(catalogue: dict, spec: dict) -> list[dict]:
    """One measure per non-deprecated metric. Deprecated metrics leave the model."""
    table = catalogue["table"]
    out = []
    for m in catalogue["metrics"]:
        if m["status"] == "deprecated":
            continue
        if m["unit"] not in spec["formats"]:
            raise ModelError(f"metric {m['name']!r}: no number format for unit {m['unit']!r}")
        col = f"{table}[{m['name']}]"
        if m["rollup"] == "mean":
            rule = "Above the grain: unweighted mean of the country-year values in the filter."
            dax = [f"AVERAGE ( {col} )"]
        else:
            rule = (
                "Defined at the grain only: blank unless exactly one country and year is selected."
            )
            dax = [f"IF ( COUNTROWS ( {table} ) = 1, MAX ( {col} ) )"]
        out.append(
            {
                "name": m["label"],
                "metric": m["name"],
                "status": m["status"],
                "unit": m["unit"],
                "description": m["description"],
                "rule": rule,
                "expression": [
                    f"// {m['name']} · {m['status']} · metrics/metrics.yaml",
                    f"// {rule}",
                ]
                + dax,
                "format": spec["formats"][m["unit"]],
                "folder": m["status"].capitalize(),
            }
        )
    return out


def validate(spec: dict, schemas: dict, model_measures: list[dict]) -> None:
    """Fail the build on anything Fabric would reject or that would silently break a measure."""
    names = [m["name"] for m in model_measures]
    if len(names) != len(set(names)):
        raise ModelError("two metrics share a label, so two measures would share a name")
    for table, conf in spec["tables"].items():
        cols = {c for c, _ in schemas[table]}
        for c in conf.get("hidden_columns", []) + list(conf.get("columns", {})):
            if c not in cols:
                raise ModelError(f"model.yaml names {table}.{c}, which the pipeline does not build")
        clash = cols & set(names) if conf.get("measures_from_catalogue") else set()
        if clash:
            raise ModelError(f"measure names clash with columns of {table}: {sorted(clash)}")
    for rel in spec["relationships"]:
        for end in (rel["from"], rel["to"]):
            table, col = end.split(".")
            if table not in schemas or col not in {c for c, _ in schemas[table]}:
                raise ModelError(f"relationship end {end} is not a column of the model")
    for m in model_measures:
        body = "\n".join(line for line in m["expression"] if not line.startswith("//"))
        if body.count("(") != body.count(")"):
            raise ModelError(f"measure {m['name']!r}: unbalanced parentheses")
        for table, col in _DAX_COLUMN_REF.findall(body):
            if table not in schemas or col not in {c for c, _ in schemas[table]}:
                raise ModelError(f"measure {m['name']!r} reads {table}[{col}], not in the model")


# ---------------------------------------------------------------- TMDL rendering


def _description(text: str, indent: str) -> list[str]:
    return [f"{indent}/// {text}"]


def render_table(table: str, conf: dict, cols, catalogue: dict, model_measures, spec) -> str:
    metric_desc = {m["name"]: m["description"] for m in catalogue["metrics"]}
    hidden = set(conf.get("hidden_columns", []))
    if conf.get("hide_metric_columns"):
        hidden |= set(metric_desc)
    lines = _description(conf["description"], "")
    lines += [
        f"table {table}",
        f"\tlineageTag: {tag(spec['name'], 'table', table)}",
        f"\tsourceLineageTag: [{spec['source']['schema']}].[{table}]",
        "",
    ]
    if conf.get("measures_from_catalogue"):
        for m in model_measures:
            lines += _description(m["description"], "\t")
            lines.append(f"\tmeasure {quote(m['name'])} =")
            lines += [f"\t\t\t{line}" for line in m["expression"]]
            lines += [
                f"\t\tformatString: {m['format']}",
                f"\t\tdisplayFolder: {m['folder']}",
                f"\t\tlineageTag: {tag(spec['name'], 'measure', m['metric'])}",
                "",
                f"\t\tannotation catalogue_metric = {m['metric']}",
                "",
                f"\t\tannotation catalogue_status = {m['status']}",
                "",
            ]
    col_desc = {c: v.get("description") for c, v in conf.get("columns", {}).items()}
    for name, dtype in cols:
        desc = col_desc.get(name) or metric_desc.get(name)
        if desc:
            lines += _description(desc, "\t")
        lines.append(f"\tcolumn {quote(name)}")
        lines.append(f"\t\tdataType: {dtype}")
        if name in hidden:
            lines.append("\t\tisHidden")
        lines += [
            f"\t\tlineageTag: {tag(spec['name'], 'column', table, name)}",
            f"\t\tsourceLineageTag: {name}",
            "\t\tsummarizeBy: none",
            f"\t\tsourceColumn: {name}",
            "",
            "\t\tannotation SummarizationSetBy = Automatic",
            "",
        ]
    src = spec["source"]
    lines += [
        f"\tpartition {table} = entity",
        "\t\tmode: directLake",
        "\t\tsource",
        f"\t\t\tentityName: {table}",
        f"\t\t\tschemaName: {src['schema']}",
        f"\t\t\texpressionSource: {quote(src['expression'])}",
        "",
    ]
    return "\n".join(lines)


def render_item(spec: dict, catalogue: dict, schemas: dict, model_measures) -> dict[Path, str]:
    base = item_dir(spec)
    src = spec["source"]
    onelake = (
        f"https://onelake.dfs.fabric.microsoft.com/{src['workspace_id']}/{src['lakehouse_id']}"
    )
    files = {
        base / ".platform": json.dumps(
            {
                "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
                "metadata": {
                    "type": "SemanticModel",
                    "displayName": spec["display_name"],
                    "description": spec["description"],
                },
                "config": {"version": "2.0", "logicalId": tag(spec["name"], "item")},
            },
            indent=2,
        )
        + "\n",
        base / "definition.pbism": json.dumps(
            {
                "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
                "version": "4.2",
                "settings": {},
            },
            indent=2,
        )
        + "\n",
        base / "definition" / "database.tmdl": "database\n\tcompatibilityLevel: 1604\n",
        base / "definition" / "model.tmdl": "\n".join(
            [
                "model Model",
                "\tculture: en-US",
                "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
                "\tsourceQueryCulture: en-US",
                "\tdataAccessOptions",
                "\t\tlegacyRedirects",
                "\t\treturnErrorValuesAsNull",
                "",
                *[f"ref table {quote(t)}" for t in spec["tables"]],
                "",
            ]
        ),
        base / "definition" / "expressions.tmdl": "\n".join(
            [
                f"expression {quote(src['expression'])} =",
                "\t\tlet",
                f'\t\t    Source = AzureStorage.DataLake("{onelake}", [HierarchicalNavigation=true])',
                "\t\tin",
                "\t\t    Source",
                f"\tlineageTag: {tag(spec['name'], 'expression', src['expression'])}",
                "",
                "\tannotation PBI_IncludeFutureArtifacts = False",
                "",
            ]
        ),
        base / "definition" / "relationships.tmdl": "\n".join(
            line
            for rel in spec["relationships"]
            for line in (
                f"relationship {tag(spec['name'], 'relationship', rel['from'], rel['to'])}",
                f"\tfromColumn: {rel['from']}",
                f"\ttoColumn: {rel['to']}",
                "",
            )
        ),
    }
    for table, conf in spec["tables"].items():
        files[base / "definition" / "tables" / f"{table}.tmdl"] = render_table(
            table, conf, schemas[table], catalogue, model_measures, spec
        )
    return files


# ---------------------------------------------------------------- data agent and docs


def render_agent(model_measures: list[dict], spec: dict) -> str:
    certified = [m for m in model_measures if m["status"] == "certified"]
    experimental = [m for m in model_measures if m["status"] == "experimental"]

    def rows(ms):
        return "\n".join(
            f"| {m['name']} | {m['unit']} | {m['description']} {m['rule']} |" for m in ms
        )

    return f"""# Data agent instructions

Generated from `metrics/metrics.yaml` and `semantic/model.yaml` by `python -m semantic.build`. \
Do not edit by hand: change the catalogue.

These are the instructions of the Fabric data agent that answers questions over the \
**{spec["display_name"]}** semantic model.

## Role

You answer questions about how farm-gate (producer) price changes reach consumer food prices in \
European countries, using only the measures of the semantic model.

## Rules

1. Answer with a measure from the lists below. Never compute a metric from table columns, and \
never invent a formula: if no measure answers the question, say so.
2. Always state the country and the year (or year range) the number refers to.
3. When several countries or years are selected, say that the value is an unweighted mean of \
country-year values, not a European aggregate weighted by population or spend.
4. Prefer certified measures. When you use an experimental measure, say it is experimental and \
give its caveat.
5. Percent changes are year-on-year. Index levels are 2020 = 100 and comparable across countries \
and series.
6. Data are annual and come from Eurostat and the World Bank. Say so when asked where a number \
comes from; do not speculate about causes the data do not show.

## Certified measures

| Measure | Unit | Meaning |
|---|---|---|
{rows(certified)}

## Experimental measures (state the caveat)

| Measure | Unit | Meaning |
|---|---|---|
{rows(experimental)}

## Dimensions

- `dim_country[country_name]` for countries; `diamond_country_year[year]` for years.
"""


def render_doc(spec: dict, schemas: dict, model_measures: list[dict]) -> str:
    lines = [
        "# Semantic model",
        "",
        (
            "Generated from [`semantic/model.yaml`](../semantic/model.yaml), the "
            "[metric catalogue](metrics.md) and the column types of the tables the pipeline "
            "builds, by `python -m semantic.build` "
            "([ADR 0013](adr/0013-direct-lake-semantic-model.md))."
        ),
        "",
        (
            f"**{spec['display_name']}** — Direct Lake on OneLake, lakehouse schema "
            f"`{spec['source']['schema']}`. TMDL item: "
            f"[`fabric/{item_dir(spec).name}/`](../fabric/{item_dir(spec).name}/)."
        ),
        "",
        "## Tables",
        "",
        "| Table | Columns | Hidden | Description |",
        "|---|---|---|---|",
    ]
    metric_names = {m["metric"] for m in model_measures}
    for table, conf in spec["tables"].items():
        hidden = set(conf.get("hidden_columns", []))
        if conf.get("hide_metric_columns"):
            hidden |= {c for c, _ in schemas[table] if c in metric_names}
        lines.append(
            f"| `{table}` | {len(schemas[table])} | {len(hidden)} | {conf['description']} |"
        )
    lines += ["", "## Relationships (many to one, single direction)", ""]
    lines += [f"- `{r['from']}` → `{r['to']}`" for r in spec["relationships"]]
    lines += [
        "",
        "## Measures",
        "",
        "| Measure | Folder | Format | DAX |",
        "|---|---|---|---|",
    ]
    for m in model_measures:
        dax = " ".join(line for line in m["expression"] if not line.startswith("//"))
        fmt = m["format"].replace("|", "\\|")
        lines.append(f"| {m['name']} | {m['folder']} | `{fmt}` | `{dax}` |")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- entry point


def outputs() -> dict[Path, str]:
    spec = yaml.safe_load(MODEL_SPEC.read_text())
    catalogue = metrics_build.load()
    schemas = table_schemas(list(spec["tables"]))
    model_measures = measures(catalogue, spec)
    validate(spec, schemas, model_measures)
    files = render_item(spec, catalogue, schemas, model_measures)
    files[AGENT_OUT] = render_agent(model_measures, spec)
    files[DOC_OUT] = render_doc(spec, schemas, model_measures)
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if generated files are stale")
    args = parser.parse_args(argv)
    files = outputs()
    tables_dir = next(iter(files)).parent / "definition" / "tables"
    orphans = (
        [p for p in tables_dir.glob("*.tmdl") if p not in files] if tables_dir.exists() else []
    )
    stale = [p for p, text in files.items() if not p.exists() or p.read_text() != text]
    if args.check:
        for p in stale + orphans:
            print(f"stale: {p.relative_to(ROOT)} — run `python -m semantic.build`", file=sys.stderr)
        return 1 if stale or orphans else 0
    for p in orphans:
        p.unlink()
    for p, text in files.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
