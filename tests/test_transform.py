import pytest

from quality.check import ContractViolation
from transform import run_local
from transform.staging import snake, stage_faostat

PPI = "Producer Price Index (2014-2016 = 100)"
FOOD = "Consumer Prices, Food Indices (2015 = 100)"


def fao(
    domain,
    m49,
    item_code,
    item,
    element,
    year,
    value,
    months="7021",
    at="2026-11-20T08:00:00+00:00",
):
    """A raw FAOSTAT row, with the labels the API uses."""
    return {
        "Area Code (M49)": f"'{m49}",
        "Area": "x",
        "Item Code": item_code,
        "Item": item,
        "Element": element,
        "Year": str(year),
        "Months Code": months,
        "Unit": "",
        "Value": value,
        "Flag": "A",
        "_domain": domain,
        "_ingested_at": at,
    }


def wb(country, year, value):
    return {
        "indicator_id": "FP.CPI.TOTL.ZG",
        "indicator_name": "Inflation, consumer prices (annual %)",
        "country_iso3": country,
        "country_name": country,
        "year": year,
        "value": value,
        "unit": "",
        "obs_status": "",
        "ingested_at": "2026-11-20T08:00:00+00:00",
    }


@pytest.fixture
def bronze():
    faostat = [
        # Spain producer prices: two items, three years
        fao("PP", 724, "15", "Wheat", PPI, 2020, 100.0),
        fao("PP", 724, "44", "Barley", PPI, 2020, 100.0),
        fao("PP", 724, "15", "Wheat", PPI, 2021, 110.0),
        fao("PP", 724, "44", "Barley", PPI, 2021, 130.0),
        fao("PP", 724, "15", "Wheat", PPI, 2022, 132.0),
        fao("PP", 724, "44", "Barley", PPI, 2022, 156.0),
        # a re-ingested correction: the later row must win
        fao("PP", 724, "44", "Barley", PPI, 2022, 144.0, at="2026-11-21T08:00:00+00:00"),
        # Spain consumer food prices: monthly, averaged to the year
        fao("CP", 724, "23013", FOOD, "Value", 2020, 100.0, months="7001"),
        fao("CP", 724, "23013", FOOD, "Value", 2020, 100.0, months="7002"),
        fao("CP", 724, "23013", FOOD, "Value", 2021, 104.0, months="7001"),
        fao("CP", 724, "23013", FOOD, "Value", 2021, 106.0, months="7002"),
        fao("CP", 724, "23013", FOOD, "Value", 2022, 115.5, months="7001"),
        fao("CP", 724, "23013", FOOD, "Value", 2022, 115.5, months="7002"),
        # a regional aggregate (M49 001 = World) has no country and is dropped
        fao("PP", 1, "15", "Wheat", PPI, 2022, 999.0),
    ]
    worldbank = [wb("ESP", 2021, 3.1), wb("ESP", 2022, 8.4)]
    return worldbank, faostat


def test_snake_case_labels():
    assert snake("Area Code (M49)") == "area_code_m49"
    assert (
        stage_faostat({"Area Code (M49)": "'724", "Months Code": "7003"})["area_code_m49"] == "724"
    )


def test_silver_conforms_dedupes_and_drops_aggregates(bronze):
    con = run_local.build(*bronze)
    countries = con.execute("SELECT DISTINCT country_iso3 FROM silver_price_observation").fetchall()
    assert countries == [("ESP",)]
    barley_2022 = con.execute(
        "SELECT value FROM silver_price_observation WHERE item_code = '44' AND year = 2022"
    ).fetchall()
    assert barley_2022 == [(144.0,)]
    months = con.execute(
        "SELECT DISTINCT month FROM silver_price_observation WHERE series_code = 'CONSUMER_FOOD_PI' ORDER BY month"
    ).fetchall()
    assert months == [(1,), (2,)]


def test_fact_averages_months_then_items(bronze):
    con = run_local.build(*bronze)
    rows = dict(
        con.execute(
            "SELECT series_code || '-' || CAST(year AS VARCHAR), value FROM fact_price_annual "
            "WHERE country_iso3 = 'ESP'"
        ).fetchall()
    )
    assert rows["PRODUCER_PI-2021"] == pytest.approx(120.0)  # (110 + 130) / 2
    assert rows["PRODUCER_PI-2022"] == pytest.approx(138.0)  # (132 + 144) / 2, correction applied
    assert rows["CONSUMER_FOOD_PI-2021"] == pytest.approx(105.0)  # (104 + 106) / 2
    assert rows["CPI_INFLATION-2022"] == pytest.approx(8.4)


def test_price_transmission(bronze):
    con = run_local.build(*bronze)
    rows = {
        r[0]: r[1:]
        for r in con.execute(
            "SELECT year, producer_yoy_pct, consumer_food_yoy_pct, gap_pp, producer_yoy_pct_lag1 "
            "FROM gold_price_transmission WHERE country_iso3 = 'ESP' ORDER BY year"
        ).fetchall()
    }
    assert rows[2020] == (None, None, None, None)  # no previous year
    producer, consumer, gap, lag1 = rows[2022]
    assert producer == pytest.approx(15.0)  # 138 / 120 - 1
    assert consumer == pytest.approx(10.0)  # 115.5 / 105 - 1
    assert gap == pytest.approx(-5.0)
    assert lag1 == pytest.approx(20.0)  # 2021: 120 / 100 - 1


def test_contract_stops_the_run_before_gold(bronze):
    worldbank, faostat = bronze
    worldbank.append(wb("ESP", 1800, 1.0))
    with pytest.raises(ContractViolation, match="year"):
        run_local.build(worldbank, faostat)
