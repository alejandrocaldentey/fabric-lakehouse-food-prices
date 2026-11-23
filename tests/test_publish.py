import re
from pathlib import Path

import pytest

from metrics import build as metrics_build
from publish import supabase
from tests.test_transform import es, wb
from transform import run_local

SCHEMA = (
    Path(__file__).resolve().parent.parent
    / "serving"
    / "supabase"
    / "001_food_prices_public_schema.sql"
)


def _con():
    rows = [
        es("apri_pi_outa", "ES", 2020, 100.0),
        es("apri_pi_outa", "ES", 2021, 120.0),
        es("prc_hicp_aind", "ES", 2020, 100.0),
        es("prc_hicp_aind", "ES", 2021, 105.0),
    ]
    return run_local.build([wb("ESP", 2021, 3.1)], rows)


def test_serving_schema_has_one_column_per_catalogued_metric():
    ddl = SCHEMA.read_text()
    block = re.search(
        r"create table public\.food_price_diamond \((.*?)\n\);", ddl, re.DOTALL
    ).group(1)
    columns = set(re.findall(r"^\s+([a-z_0-9]+) ", block, re.MULTILINE)) - {"primary"}
    expected = {"country_iso3", "year"} | {m["name"] for m in metrics_build.load()["metrics"]}
    assert columns == expected


def test_payloads_follow_fk_order_and_catalogue():
    data = supabase.payloads(_con())
    assert [c["country_iso3"] for c in data["food_price_country"]] == ["ESP"]
    assert [m["sort_order"] for m in data["food_price_metric"]] == list(range(6))
    row = next(r for r in data["food_price_diamond"] if r["year"] == 2021)
    assert row["producer_price_change_pct"] == pytest.approx(20.0)
    assert row["headline_inflation_pct"] == pytest.approx(3.1)


class FakeSession:
    def __init__(self):
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append((url.rsplit("/", 1)[1], len(json), headers["Prefer"]))

        class R:
            status_code = 201
            text = ""

        return R()


def test_publish_upserts_tables_in_order_then_logs():
    s = FakeSession()
    counts = supabase.publish(_con(), "https://x.supabase.co", "sb_secret_k", "abc123", session=s)
    assert [c[0] for c in s.calls] == [*supabase.TABLES, "food_price_publish_log"]
    assert all("merge-duplicates" in c[2] for c in s.calls)
    assert counts["food_price_country"] == 1


def test_main_without_credentials_is_a_no_op(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    assert supabase.main() == 0


def test_read_only_keys_are_rejected_before_any_call():
    s = FakeSession()
    with pytest.raises(RuntimeError, match="publishable"):
        supabase.publish(_con(), "https://x.supabase.co", "sb_publishable_abc", session=s)
    assert s.calls == []
