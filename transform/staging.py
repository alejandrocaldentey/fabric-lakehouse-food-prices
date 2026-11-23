"""Normalise raw bronze rows into flat, snake_case staging records.

Raw FAOSTAT rows use labels such as ``"Area Code (M49)"``. Quoting those differs between
Spark SQL and DuckDB, so names are normalised here, once, and the shared SQL only ever
sees plain identifiers. The same functions run in the Fabric notebook.
"""

from __future__ import annotations

import re

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

BRONZE_FAOSTAT_COLUMNS = [
    "domain",
    "area_code_m49",
    "area",
    "item_code",
    "item",
    "element",
    "year",
    "months_code",
    "unit",
    "value",
    "flag",
    "ingested_at",
]

# Raw FAOSTAT label -> staging column. Several spellings map to the same column.
_FAOSTAT_ALIASES = {
    "area_code_m49": "area_code_m49",
    "area_code_m49_": "area_code_m49",
    "area": "area",
    "item_code": "item_code",
    "item": "item",
    "element": "element",
    "year": "year",
    "months_code": "months_code",
    "unit": "unit",
    "value": "value",
    "flag": "flag",
    "_domain": "domain",
    "_ingested_at": "ingested_at",
}


def snake(label: str) -> str:
    """'Area Code (M49)' -> 'area_code_m49'."""
    return re.sub(r"_+", "_", re.sub(r"[^0-9a-zA-Z]+", "_", label)).strip("_").lower() or label


def _digits(value: object) -> str | None:
    """FAOSTAT prefixes M49 codes with an apostrophe ("'724"); keep only the digits."""
    if value is None:
        return None
    digits = re.sub(r"\D", "", str(value))
    return digits or None


def stage_faostat(row: dict) -> dict:
    out: dict = dict.fromkeys(BRONZE_FAOSTAT_COLUMNS)
    for key, value in row.items():
        name = _FAOSTAT_ALIASES.get(key) or _FAOSTAT_ALIASES.get(snake(key))
        if name:
            out[name] = value
    out["area_code_m49"] = _digits(out["area_code_m49"])
    out["months_code"] = _digits(out["months_code"])
    for text in ("item_code", "element", "item", "unit", "flag", "year"):
        if out[text] is not None:
            out[text] = str(out[text])
    return out


def stage_worldbank(row: dict) -> dict:
    return {col: row.get(col) for col in BRONZE_WORLDBANK_COLUMNS}
