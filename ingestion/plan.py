"""Turn a source's load strategy into the period range to request (ADR 0005).

The plan is pure logic, so it is unit-tested and shared by the local runner and the
Fabric notebook. The MERGE itself happens in the silver step (Delta MERGE in Fabric).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

SOURCES = Path(__file__).with_name("sources.yaml")
FIRST_YEAR = 2000


@dataclass(frozen=True)
class LoadPlan:
    source_id: str
    strategy: str
    since_year: int  # first year to request
    merge: bool  # True: MERGE on natural key; False: append


def load_sources(path: Path = SOURCES) -> list[dict]:
    return yaml.safe_load(path.read_text())["sources"]


def plan(source: dict, today: date, last_loaded_year: int | None) -> LoadPlan:
    load = source.get("load", {"strategy": "full"})
    strategy = load["strategy"]
    if last_loaded_year is None or strategy == "full":
        # first run, or explicit full reload: everything, merged so reruns stay idempotent
        return LoadPlan(source["id"], strategy, FIRST_YEAR, merge=True)
    if strategy == "window_merge":
        window = int(load.get("window_years", 3))
        since = min(last_loaded_year + 1, today.year - window + 1)
        return LoadPlan(source["id"], strategy, max(since, FIRST_YEAR), merge=True)
    if strategy == "watermark":
        return LoadPlan(source["id"], strategy, last_loaded_year + 1, merge=False)
    raise ValueError(f"Unknown load strategy {strategy!r} for source {source['id']}")
