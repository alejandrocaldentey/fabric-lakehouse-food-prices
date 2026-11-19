"""World Bank Indicators API v2 client (no API key required).

Docs: https://datahelpdesk.worldbank.org/knowledgebase/articles/889392-about-the-indicators-api

The v2 API returns a two-element JSON array: ``[page_metadata, observations]``.
This client walks every page and returns flat records ready for the bronze layer.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

import requests

from ingestion.http import build_session

BASE_URL = "https://api.worldbank.org/v2"
PER_PAGE = 1000


class WorldBankError(RuntimeError):
    """Raised when the API answers with an error payload or an unexpected shape."""


@dataclass(frozen=True)
class Observation:
    indicator_id: str
    indicator_name: str
    country_iso3: str
    country_name: str
    year: int
    value: float | None
    unit: str
    obs_status: str
    ingested_at: str
    source: str = "worldbank"


def _parse_page(payload: object) -> tuple[dict, list[dict]]:
    if not isinstance(payload, list) or not payload:
        raise WorldBankError(f"Unexpected response shape: {type(payload).__name__}")
    meta = payload[0]
    if isinstance(meta, dict) and "message" in meta:
        raise WorldBankError(f"API error: {meta['message']}")
    rows = payload[1] if len(payload) > 1 and payload[1] is not None else []
    return meta, rows


def fetch_indicator(
    indicator: str,
    countries: str = "all",
    dates: str | None = None,
    session: requests.Session | None = None,
) -> list[Observation]:
    """Fetch every observation of ``indicator`` for ``countries`` (ISO3 codes joined by ';')."""
    session = session or build_session()
    url = f"{BASE_URL}/country/{countries}/indicator/{indicator}"
    params: dict[str, str | int] = {"format": "json", "per_page": PER_PAGE, "page": 1}
    if dates:
        params["date"] = dates

    ingested_at = datetime.now(UTC).isoformat(timespec="seconds")
    observations: list[Observation] = []
    while True:
        response = session.get(url, params=params, timeout=60)
        response.raise_for_status()
        meta, rows = _parse_page(response.json())
        for row in rows:
            observations.append(
                Observation(
                    indicator_id=row["indicator"]["id"],
                    indicator_name=row["indicator"]["value"],
                    country_iso3=row.get("countryiso3code") or row["country"]["id"],
                    country_name=row["country"]["value"],
                    year=int(row["date"]),
                    value=row.get("value"),
                    unit=row.get("unit") or "",
                    obs_status=row.get("obs_status") or "",
                    ingested_at=ingested_at,
                )
            )
        pages = int(meta.get("pages", 1) or 1)
        if int(params["page"]) >= pages:
            break
        params["page"] = int(params["page"]) + 1
    return observations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pull a World Bank indicator as JSON lines.")
    parser.add_argument("indicator", help="e.g. FP.CPI.TOTL.ZG (inflation, consumer prices)")
    parser.add_argument("--countries", default="all", help="ISO3 codes joined by ';'")
    parser.add_argument("--dates", default=None, help="e.g. 2015:2024")
    args = parser.parse_args(argv)
    for obs in fetch_indicator(args.indicator, args.countries, args.dates):
        sys.stdout.write(json.dumps(asdict(obs)) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
