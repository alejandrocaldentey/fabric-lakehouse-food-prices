from datetime import date

import pytest

from ingestion.plan import FIRST_YEAR, load_sources, plan

TODAY = date(2026, 11, 23)


def src(strategy, window=3):
    return {"id": "s", "load": {"strategy": strategy, "window_years": window}}


def test_first_run_loads_everything():
    p = plan(src("window_merge"), TODAY, last_loaded_year=None)
    assert p.since_year == FIRST_YEAR and p.merge


def test_window_merge_reloads_last_years_to_catch_revisions():
    p = plan(src("window_merge", 3), TODAY, last_loaded_year=2025)
    assert p.since_year == 2024 and p.merge  # 2024, 2025, 2026 re-pulled and merged


def test_window_merge_never_skips_a_gap():
    p = plan(src("window_merge", 3), TODAY, last_loaded_year=2019)
    assert p.since_year == 2020


def test_watermark_appends_only_new_periods():
    p = plan(src("watermark"), TODAY, last_loaded_year=2025)
    assert p.since_year == 2026 and not p.merge


def test_full_ignores_watermark():
    assert plan(src("full"), TODAY, last_loaded_year=2025).since_year == FIRST_YEAR


def test_unknown_strategy_fails_loudly():
    with pytest.raises(ValueError):
        plan(src("magic"), TODAY, last_loaded_year=2025)


def test_registry_is_valid():
    for s in load_sources():
        plan(s, TODAY, last_loaded_year=2025)
