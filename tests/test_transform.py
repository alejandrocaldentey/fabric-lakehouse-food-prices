import pytest

from quality.check import ContractViolation
from transform import run_local
from transform.staging import stage_eurostat

PRODUCER = "apri_pi20_outa"
FOOD = "prc_hicp_aind"


def es(dataset, geo, time, value, at="2026-11-20T08:00:00+00:00"):
    """A flattened Eurostat record, as ingestion.eurostat returns it."""
    return {
        "unit": "I20",
        "geo": geo,
        "time": str(time),
        "value": value,
        "_source": "eurostat",
        "_dataset": dataset,
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
    eurostat = [
        es(PRODUCER, "ES", 2020, 100.0),
        es(PRODUCER, "ES", 2021, 120.0),
        es(PRODUCER, "ES", 2022, 150.0),
        # a revision published later: the newer row must win
        es(PRODUCER, "ES", 2022, 138.0, at="2026-11-21T08:00:00+00:00"),
        es(FOOD, "ES", 2020, 100.0),
        es(FOOD, "ES", 2021, 105.0),
        es(FOOD, "ES", 2022, 115.5),
        # Greece uses the EU protocol code EL
        es(PRODUCER, "EL", 2022, 110.0),
        # EU aggregate has no ISO code and is dropped
        es(PRODUCER, "EU27_2020", 2022, 125.0),
    ]
    worldbank = [wb("ESP", 2021, 3.1), wb("ESP", 2022, 8.4)]
    return worldbank, eurostat


def test_staging_maps_eu_protocol_codes_and_series():
    row = stage_eurostat(es(PRODUCER, "EL", 2022, 1.0))
    assert row["geo_iso2"] == "GR" and row["series_code"] == "PRODUCER_PI"


def test_silver_conforms_dedupes_and_drops_aggregates(bronze):
    con = run_local.build(*bronze)
    countries = con.execute(
        "SELECT DISTINCT country_iso3 FROM silver_price_observation ORDER BY 1"
    ).fetchall()
    assert countries == [("ESP",), ("GRC",)]
    revised = con.execute(
        "SELECT value FROM silver_price_observation "
        "WHERE series_code = 'PRODUCER_PI' AND country_iso3 = 'ESP' AND year = 2022"
    ).fetchall()
    assert revised == [(138.0,)]


def test_fact_annual_values(bronze):
    con = run_local.build(*bronze)
    rows = dict(
        con.execute(
            "SELECT series_code || '-' || CAST(year AS VARCHAR), value FROM fact_price_annual "
            "WHERE country_iso3 = 'ESP'"
        ).fetchall()
    )
    assert rows["PRODUCER_PI-2022"] == pytest.approx(138.0)
    assert rows["CONSUMER_FOOD_PI-2021"] == pytest.approx(105.0)
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
    worldbank, eurostat = bronze
    worldbank.append(wb("ESP", 1800, 1.0))
    with pytest.raises(ContractViolation, match="year"):
        run_local.build(worldbank, eurostat)
