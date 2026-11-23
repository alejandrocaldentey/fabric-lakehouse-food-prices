import pytest

from decisions import build
from tests.test_transform import es, wb
from transform import run_local


def test_rules_and_playbooks_are_valid_and_generated_files_current():
    _, books = build.load()
    assert {p for plays in books["plays"].values() for p in plays} <= {
        r["id"] for r in books["roles"]
    }
    assert build.main(["--check"]) == 0


def test_market_rules_fire_with_the_right_severity():
    eurostat = [
        es("apri_pi_outa", "ES", 2020, 100.0),
        es("apri_pi_outa", "ES", 2021, 125.0),  # +25% farm-gate: high shock
        es("prc_hicp_aind", "ES", 2020, 100.0),
        es("prc_hicp_aind", "ES", 2021, 103.0),  # gap -22 pp: high squeeze
    ]
    con = run_local.build([wb("ESP", 2021, 2.0)], eurostat)
    fired = {
        r[0]: r[1:]
        for r in con.execute(
            "SELECT rule_id, severity, value FROM decision_alert WHERE country_iso3 = 'ESP'"
        ).fetchall()
    }
    assert fired["farm_gate_shock"] == ("high", pytest.approx(25.0))
    assert fired["margin_squeeze"] == ("high", pytest.approx(-22.0))
    assert "margin_expansion" not in fired
