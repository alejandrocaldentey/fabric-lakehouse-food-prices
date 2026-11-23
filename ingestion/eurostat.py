"""Eurostat Statistics API client (JSON-stat 2.0, no API key).

Docs: https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access/api-getting-started
URL:  https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}?lang=en&{filters}

JSON-stat stores observations as one flat array (or a sparse dict keyed by position)
over the cartesian product of the dimensions, in the order given by ``id`` and ``size``.
``flatten`` turns that cube back into one record per observation.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from itertools import product

import requests

from ingestion.http import build_session

BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"


class EurostatError(RuntimeError):
    """Raised when the API returns an error payload or an unexpected shape."""


def _codes_by_position(dimension: dict) -> list[str]:
    index = dimension["category"]["index"]
    if isinstance(index, list):
        return list(index)
    return [code for code, _ in sorted(index.items(), key=lambda kv: kv[1])]


def flatten(payload: dict) -> list[dict]:
    """One dict per non-missing observation: every dimension code plus ``value``."""
    if "error" in payload:
        raise EurostatError(f"API error: {payload['error']}")
    try:
        ids, sizes, dims = payload["id"], payload["size"], payload["dimension"]
    except KeyError as exc:
        raise EurostatError(f"Not a JSON-stat dataset: missing {exc}") from exc

    codes = [_codes_by_position(dims[d]) for d in ids]
    values = payload.get("value", {})
    if isinstance(values, list):
        values = {i: v for i, v in enumerate(values) if v is not None}
    else:
        values = {int(k): v for k, v in values.items() if v is not None}

    # stride of each dimension in the flat array (row-major, last dimension fastest)
    strides = [1] * len(sizes)
    for i in range(len(sizes) - 2, -1, -1):
        strides[i] = strides[i + 1] * sizes[i + 1]

    records = []
    for combo in product(*(range(s) for s in sizes)):
        pos = sum(c * s for c, s in zip(combo, strides, strict=True))
        if pos in values:
            rec = {d: codes[i][combo[i]] for i, d in enumerate(ids)}
            rec["value"] = values[pos]
            records.append(rec)
    return records


def fetch_dataset(
    dataset: str,
    filters: dict[str, str | list[str]] | None = None,
    since_period: str | None = None,
    session: requests.Session | None = None,
) -> list[dict]:
    """Fetch a dataset, filtered by dimension codes and optionally from ``since_period`` on."""
    session = session or build_session()
    params: list[tuple[str, str]] = [("lang", "en")]
    for dim, value in (filters or {}).items():
        for v in value if isinstance(value, list) else [value]:
            params.append((dim, str(v)))
    if since_period:
        params.append(("sinceTimePeriod", since_period))

    response = session.get(f"{BASE_URL}/{dataset}", params=params, timeout=60)
    response.raise_for_status()
    ingested_at = datetime.now(UTC).isoformat(timespec="seconds")
    return [
        {**rec, "_source": "eurostat", "_dataset": dataset, "_ingested_at": ingested_at}
        for rec in flatten(response.json())
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pull a Eurostat dataset as JSON lines.")
    parser.add_argument("dataset", help="e.g. apri_pi20_outa")
    parser.add_argument("--filter", action="append", default=[], help="dim=code, repeatable")
    parser.add_argument("--since", default=None, help="first period, e.g. 2015")
    args = parser.parse_args(argv)
    filters: dict[str, list[str]] = {}
    for item in args.filter:
        dim, code = item.split("=", 1)
        filters.setdefault(dim, []).append(code)
    for rec in fetch_dataset(args.dataset, filters, args.since):
        sys.stdout.write(json.dumps(rec) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
