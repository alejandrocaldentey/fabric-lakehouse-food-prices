import copy

import pytest

from metrics import build


def test_catalogue_is_valid_and_generated_files_are_current():
    assert build.main(["--check"]) == 0


def test_duplicate_metric_names_are_rejected(tmp_path):
    cat = build.load()
    bad = copy.deepcopy(cat)
    bad["metrics"].append(bad["metrics"][0])
    path = tmp_path / "m.yaml"
    import yaml

    path.write_text(yaml.safe_dump(bad))
    with pytest.raises(build.CatalogueError):
        build.load(path)


def test_unknown_rollup_is_rejected(tmp_path):
    import yaml

    cat = build.load()
    cat["metrics"][0]["rollup"] = "sum"
    path = tmp_path / "m.yaml"
    path.write_text(yaml.safe_dump(cat))
    with pytest.raises(build.CatalogueError, match="rollup"):
        build.load(path)


def test_diamond_matches_catalogue_definitions():
    from tests.test_transform import es, wb  # reuse the hand-checked bronze rows
    from transform import run_local

    eurostat = [
        es("apri_pi_outa", "ES", 2020, 100.0),
        es("apri_pi_outa", "ES", 2021, 120.0),
        es("apri_pi_outa", "ES", 2022, 138.0),
        es("prc_hicp_aind", "ES", 2020, 100.0),
        es("prc_hicp_aind", "ES", 2021, 105.0),
        es("prc_hicp_aind", "ES", 2022, 115.5),
    ]
    con = run_local.build([wb("ESP", 2022, 8.4)], eurostat)
    row = con.execute(
        "SELECT producer_price_change_pct, consumer_food_price_change_pct, food_price_gap_pp, "
        "pass_through_ratio_lag1, headline_inflation_pct, food_inflation_premium_pp "
        "FROM diamond_country_year WHERE country_iso3 = 'ESP' AND year = 2022"
    ).fetchone()
    assert row == pytest.approx((15.0, 10.0, -5.0, 0.5, 8.4, 1.6))
