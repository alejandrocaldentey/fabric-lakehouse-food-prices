"""FAOSTAT Data API client.

Base URL: https://fenixservices.fao.org/faostat/api/v1
Endpoint: GET /{lang}/data/{domain}?area=&item=&element=&year=&output_type=objects

Domains used in this project:
- ``PP`` — agricultural producer prices (farm-gate)
- ``CP`` — consumer price indices, including food

The bronze layer keeps rows exactly as the API returns them, plus run metadata,
so the silver layer can be rebuilt without calling the API again.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime

import requests

from ingestion.http import build_session

BASE_URL = "https://fenixservices.fao.org/faostat/api/v1"


class FaostatError(RuntimeError):
    """Raised when the API answers with an unexpected shape."""


def _join(values: list[str | int] | None) -> str | None:
    return ",".join(str(v) for v in values) if values else None


def fetch_domain(
    domain: str,
    areas: list[str | int] | None = None,
    items: list[str | int] | None = None,
    elements: list[str | int] | None = None,
    years: list[str | int] | None = None,
    lang: str = "en",
    session: requests.Session | None = None,
) -> list[dict]:
    """Return the rows of a FAOSTAT domain, filtered by FAO area/item/element codes and years."""
    session = session or build_session()
    params = {
        "area": _join(areas),
        "item": _join(items),
        "element": _join(elements),
        "year": _join(years),
        "output_type": "objects",
    }
    params = {k: v for k, v in params.items() if v is not None}

    response = session.get(f"{BASE_URL}/{lang}/data/{domain}", params=params, timeout=120)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise FaostatError(f"Unexpected response shape for domain {domain}")

    ingested_at = datetime.now(UTC).isoformat(timespec="seconds")
    return [
        {**row, "_source": "faostat", "_domain": domain, "_ingested_at": ingested_at}
        for row in payload["data"]
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pull a FAOSTAT domain as JSON lines.")
    parser.add_argument("domain", help="e.g. PP (producer prices) or CP (consumer prices)")
    parser.add_argument("--areas", default=None, help="FAO area codes joined by ','")
    parser.add_argument("--years", default=None, help="years joined by ','")
    args = parser.parse_args(argv)
    rows = fetch_domain(
        args.domain,
        areas=args.areas.split(",") if args.areas else None,
        years=args.years.split(",") if args.years else None,
    )
    for row in rows:
        sys.stdout.write(json.dumps(row, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
