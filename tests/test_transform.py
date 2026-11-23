import pytest

from quality.check import ContractViolation
from transform import run_local
from transform.staging import stage_eurostat

PRODUCER = "apri_pi_outa"
FOOD = "prc_hicp_aind"


def es(dataset, geo, time, value, at="2026-11-20T08:00:00+00:00", unit=None):
    """A flattened Eurostat record, as ingestion.eurostat returns it."""
    return {
        "unit": unit or ("I20" if dataset == PRODUCER else "INX_A_AVG"),
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
        es(PRODUCER, "EL", 2020, 100.0),
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
    assert 2020 not in rows or rows[2020][0] is None  # no previous year
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


def test_older_bases_are_chain_linked_and_rebased():
    """2015 = 100 fills the years before the 2020 base, linked at 2020, rebased to 2020 = 100."""
    eurostat = [
        es(PRODUCER, "ES", 2020, 100.0, unit="I20"),
        es(PRODUCER, "ES", 2021, 110.0, unit="I20"),
        # the 2015 base covers 2018-2021; at 2020 it reads 125, so its link ratio is 100 / 125
        es(PRODUCER, "ES", 2018, 120.0, unit="I15"),
        es(PRODUCER, "ES", 2019, 115.0, unit="I15"),
        es(PRODUCER, "ES", 2020, 125.0, unit="I15"),
        es(PRODUCER, "ES", 2021, 999.0, unit="I15"),  # superseded by the newer base
        # the 2010 base has no value in 2018 (its link year): the chain stops, no invented values
        es(PRODUCER, "ES", 2016, 90.0, unit="I10"),
        es(PRODUCER, "ES", 2017, 95.0, unit="I10"),
        # HICP arrives in its own base (2015 = 100) and is rebased to 2020 = 100
        es(FOOD, "ES", 2019, 110.0),
        es(FOOD, "ES", 2020, 125.0),
        es(FOOD, "ES", 2021, 130.0),
    ]
    con = run_local.build([], eurostat)
    rows = {
        (r[0], r[1]): (r[2], r[3])
        for r in con.execute(
            "SELECT series_code, year, index_value, source_unit FROM silver_price_index_chained "
            "WHERE country_iso3 = 'ESP'"
        ).fetchall()
    }
    assert rows[("PRODUCER_PI", 2021)] == (pytest.approx(110.0), "I20")
    assert rows[("PRODUCER_PI", 2019)] == (pytest.approx(92.0), "I15")  # 115 * 100 / 125
    assert rows[("PRODUCER_PI", 2018)] == (pytest.approx(96.0), "I15")
    assert ("PRODUCER_PI", 2017) not in rows  # broken link: no I10 value in 2018
    assert rows[("CONSUMER_FOOD_PI", 2020)][0] == pytest.approx(100.0)
    assert rows[("CONSUMER_FOOD_PI", 2019)][0] == pytest.approx(88.0)  # 110 * 100 / 125
