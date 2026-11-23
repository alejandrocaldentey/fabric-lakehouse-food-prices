"""Normalise raw bronze rows into flat staging records with plain column names.

The shared SQL only ever sees these columns, whatever each API calls them.
The same functions run in the Fabric notebook.
"""

from __future__ import annotations

from ingestion.plan import load_sources

BRONZE_WORLDBANK_COLUMNS = [
    "indicator_id",
    "indicator_name",
    "country_iso3",
    "country_name",
    "year",
    "value",
    "unit",
    "obs_status",
    "ingested_at",
]

BRONZE_EUROSTAT_COLUMNS = [
    "dataset",
    "series_code",
    "geo_iso2",
    "time",
    "value",
    "unit",
    "ingested_at",
]

# Eurostat uses EU protocol codes for two countries; everything else is ISO 3166-1 alpha-2.
EUROSTAT_GEO_TO_ISO2 = {"EL": "GR", "UK": "GB"}


def series_by_dataset() -> dict[str, str]:
    return {s["dataset"]: s["series_code"] for s in load_sources() if s["api"] == "eurostat"}


def stage_eurostat(row: dict, series: dict[str, str] | None = None) -> dict:
    series = series or series_by_dataset()
    geo = str(row.get("geo", ""))
    return {
        "dataset": row.get("_dataset"),
        "series_code": series.get(row.get("_dataset")),
        "geo_iso2": EUROSTAT_GEO_TO_ISO2.get(geo, geo),
        "time": str(row.get("time")),
        "value": row.get("value"),
        "unit": row.get("unit", ""),
        "ingested_at": row.get("_ingested_at"),
    }


def stage_worldbank(row: dict) -> dict:
    return {col: row.get(col) for col in BRONZE_WORLDBANK_COLUMNS}
