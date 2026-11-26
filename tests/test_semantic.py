import copy
import re

import pytest
import yaml

from metrics import build as metrics_build
from semantic import build


@pytest.fixture(scope="module")
def parts():
    spec = yaml.safe_load(build.MODEL_SPEC.read_text())
    catalogue = metrics_build.load()
    schemas = build.table_schemas(list(spec["tables"]))
    return spec, catalogue, schemas


def test_generated_model_agent_and_docs_are_current():
    assert build.main(["--check"]) == 0


def test_one_measure_per_live_metric_and_none_for_deprecated(parts):
    spec, catalogue, _ = parts
    cat = copy.deepcopy(catalogue)
    cat["metrics"][0]["status"] = "deprecated"
    got = {m["metric"] for m in build.measures(cat, spec)}
    assert got == {m["name"] for m in cat["metrics"][1:]}


def test_rollup_none_is_blank_above_the_grain(parts):
    spec, catalogue, _ = parts
    by_metric = {m["metric"]: m for m in build.measures(catalogue, spec)}
    ratio = by_metric["pass_through_ratio_lag1"]["expression"][-1]
    assert ratio.startswith("IF ( COUNTROWS ( diamond_country_year ) = 1,")
    gap = by_metric["food_price_gap_pp"]["expression"][-1]
    assert gap == "AVERAGE ( diamond_country_year[food_price_gap_pp] )"


def test_columns_and_types_come_from_the_pipeline(parts):
    _, catalogue, schemas = parts
    diamond = dict(schemas["diamond_country_year"])
    assert diamond["year"] == "int64"
    assert all(diamond[m["name"]] == "double" for m in catalogue["metrics"])


def test_metric_columns_are_hidden_so_only_measures_are_offered():
    text = (
        build.item_dir(yaml.safe_load(build.MODEL_SPEC.read_text()))
        / "definition"
        / "tables"
        / "diamond_country_year.tmdl"
    ).read_text()
    for m in metrics_build.load()["metrics"]:
        block = text.split(f"\tcolumn {m['name']}\n", 1)[1].split("\n\n", 1)[0]
        assert "\t\tisHidden" in block, m["name"]


def test_measure_reading_a_missing_column_fails_the_build(parts):
    spec, catalogue, schemas = parts
    ms = build.measures(catalogue, spec)
    ms[0]["expression"][-1] = "AVERAGE ( diamond_country_year[not_a_column] )"
    with pytest.raises(build.ModelError, match="not_a_column"):
        build.validate(spec, schemas, ms)


def test_unknown_unit_and_bad_relationship_fail_the_build(parts):
    spec, catalogue, schemas = parts
    cat = copy.deepcopy(catalogue)
    cat["metrics"][0]["unit"] = "EUR/t"
    with pytest.raises(build.ModelError, match="number format"):
        build.measures(cat, spec)
    bad = copy.deepcopy(spec)
    bad["relationships"].append({"from": "diamond_country_year.nope", "to": "dim_country.x"})
    with pytest.raises(build.ModelError, match="relationship"):
        build.validate(bad, schemas, build.measures(catalogue, spec))


def test_lineage_tags_are_stable_and_unique():
    files = build.outputs()
    tmdl = "\n".join(t for p, t in files.items() if p.suffix == ".tmdl")
    tags = re.findall(r"lineageTag: ([0-9a-f-]{36})", tmdl)
    assert len(tags) == len(set(tags)) > 0
    assert build.outputs() == files


def test_tmdl_is_indented_with_tabs_only():
    for path, text in build.outputs().items():
        if path.suffix == ".tmdl":
            for line in text.splitlines():
                assert not line.startswith(" "), f"{path.name}: {line!r}"


def test_names_are_quoted_when_not_identifiers():
    assert build.quote("dim_country") == "dim_country"
    assert build.quote("Pass-through ratio (1-year lag)") == "'Pass-through ratio (1-year lag)'"
    assert build.quote("Farmer's share") == "'Farmer''s share'"


def test_agent_lists_every_measure_and_flags_experimental(parts):
    spec, catalogue, _ = parts
    ms = build.measures(catalogue, spec)
    text = build.render_agent(ms, spec)
    certified, experimental = text.split("## Experimental measures", 1)
    for m in ms:
        assert f"| {m['name']} |" in (certified if m["status"] == "certified" else experimental)
