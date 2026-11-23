import duckdb
import numpy as np
import pytest

from ml import forecast


def _gold(con, n_countries=6, years=range(2000, 2026), seed=1):
    """Synthetic gold table where consumer prices follow farm-gate prices with a one-year lag."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n_countries):
        p_prev, c = 0.0, 2.0
        p = rng.normal(2, 6)
        for t in years:
            c_next = 1.0 + 0.4 * p + rng.normal(0, 0.3)
            rows.append((f"C{i}", t, p, c, p_prev))
            p_prev, p, c = p, rng.normal(2, 6), c_next
    con.execute(
        "CREATE TABLE gold_price_transmission (country_iso3 VARCHAR, year INT, "
        "producer_yoy_pct DOUBLE, consumer_food_yoy_pct DOUBLE, producer_yoy_pct_lag1 DOUBLE)"
    )
    con.executemany("INSERT INTO gold_price_transmission VALUES (?, ?, ?, ?, ?)", rows)


def test_backtest_never_trains_on_the_year_it_predicts():
    con = duckdb.connect()
    _gold(con)
    s = forecast.samples(forecast.history(con))
    rows = forecast.backtest(s, 2010)
    assert rows and min(r[2] for r in rows) >= 2010
    # a model trained on years < T must not change when year T's data changes
    t = 2015
    train = s.mask(s.year < t)
    before = forecast.PanelDL().fit(train).beta
    s.y[s.year == t] += 100
    after = forecast.PanelDL().fit(s.mask(s.year < t)).beta
    assert np.allclose(before, after)


def test_regression_recovers_the_pass_through_and_beats_naive():
    con = duckdb.connect()
    _gold(con)
    champion = forecast.run(con)
    slope = dict(
        con.execute("SELECT term, value FROM ml_coefficient WHERE kind = 'slope'").fetchall()
    )
    assert slope["producer_yoy_pct"] == pytest.approx(0.4, abs=0.05)
    skill = dict(con.execute("SELECT model_id, skill_vs_naive FROM ml_model_registry").fetchall())
    assert skill["panel_dl"] > 0.5
    assert champion in {"panel_dl", "gbm"}
    assert (
        con.execute("SELECT COUNT(*) FROM ml_model_registry WHERE is_champion").fetchone()[0] == 1
    )


def test_simplest_model_within_tolerance_wins():
    cfg = forecast.load_config()
    stats = {
        "naive": {"mae": 3.0, "skill_vs_naive": 0.0},
        "panel_dl": {"mae": 2.41, "skill_vs_naive": 0.2},
        "gbm": {"mae": 2.40, "skill_vs_naive": 0.2},
    }
    assert forecast.pick_champion(stats, cfg) == "panel_dl"
    stats["gbm"]["mae"] = 2.0
    stats["gbm"]["skill_vs_naive"] = 0.33
    assert forecast.pick_champion(stats, cfg) == "gbm"
    # nothing beats the baseline by 5%: the baseline stays champion
    worse = {m: {"mae": 2.95, "skill_vs_naive": 0.017} for m in ("panel_dl", "gbm")}
    assert forecast.pick_champion({"naive": stats["naive"], **worse}, cfg) == "naive"


def test_published_coefficients_reproduce_the_forecast():
    """Parity: the browser simulator applies these coefficients; they must give the same number."""
    con = duckdb.connect()
    _gold(con)
    forecast.run(con)
    slope = dict(
        con.execute("SELECT term, value FROM ml_coefficient WHERE kind = 'slope'").fetchall()
    )
    alpha = dict(
        con.execute(
            "SELECT country_iso3, value FROM ml_coefficient WHERE kind = 'intercept' "
            "AND term = 'country'"
        ).fetchall()
    )
    for c, pred, x0, x1, x2 in con.execute(
        "SELECT country_iso3, predicted, input_consumer_yoy, input_producer_yoy, "
        "input_producer_yoy_lag1 FROM ml_forecast WHERE model_id = 'panel_dl'"
    ).fetchall():
        manual = (
            alpha[c]
            + slope["consumer_food_yoy_pct"] * x0
            + slope["producer_yoy_pct"] * x1
            + slope["producer_yoy_pct_lag1"] * x2
        )
        assert manual == pytest.approx(pred)


def test_no_data_builds_empty_tables():
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE gold_price_transmission (country_iso3 VARCHAR, year INT, "
        "producer_yoy_pct DOUBLE, consumer_food_yoy_pct DOUBLE, producer_yoy_pct_lag1 DOUBLE)"
    )
    assert forecast.run(con) is None
    assert con.execute("SELECT COUNT(*) FROM ml_forecast").fetchone()[0] == 0
