import re
from pathlib import Path

import pytest

from metrics import build as metrics_build
from publish import supabase
from tests.test_transform import es, wb
from transform import run_local

SERVING = Path(__file__).resolve().parent.parent / "serving" / "supabase"
SCHEMA = SERVING / "001_food_prices_public_schema.sql"


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
    # later migrations add columns with ALTER TABLE ... ADD COLUMN
    for path in sorted(SERVING.glob("[0-9][0-9][0-9]_*.sql"))[1:]:
        columns |= set(re.findall(r"add column ([a-z_0-9]+) ", path.read_text())) & {
            m["name"] for m in metrics_build.load()["metrics"]
        }
    expected = {"country_iso3", "year"} | {m["name"] for m in metrics_build.load()["metrics"]}
    assert columns == expected


def test_payloads_follow_fk_order_and_catalogue():
    data = supabase.keyed_payloads(_con())
    assert [c["country_iso3"] for c in data["food_price_country"]] == ["ESP"]
    n_metrics = len(metrics_build.load()["metrics"])
    assert [m["sort_order"] for m in data["food_price_metric"]] == list(range(n_metrics))
    row = next(r for r in data["food_price_diamond"] if r["year"] == 2021)
    assert row["producer_price_change_pct"] == pytest.approx(20.0)
    assert row["headline_inflation_pct"] == pytest.approx(3.1)


class FakeSession:
    def __init__(self):
        self.calls = []

    class R:
        status_code = 201
        text = ""

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append(("post", url.rsplit("/", 1)[1], len(json), json))
        return self.R()

    def delete(self, url, params=None, headers=None, timeout=None):
        self.calls.append(("delete", url.rsplit("/", 1)[1], params, None))
        return self.R()


def test_publish_marks_run_complete_before_deleting_older_runs():
    s = FakeSession()
    counts = supabase.publish(
        _con(), "https://x.supabase.co", "sb_secret_k", "abc123", session=s, run_id="r1"
    )
    posts = [c[1] for c in s.calls if c[0] == "post"]
    assert posts[: len(supabase.KEYED)] == list(supabase.KEYED)
    log_at = next(i for i, c in enumerate(s.calls) if c[1] == "food_price_publish_log")
    deletes = [i for i, c in enumerate(s.calls) if c[0] == "delete"]
    assert deletes and min(deletes) > log_at  # never delete before the new run is complete
    assert all(c[2] == {"run_id": "neq.r1"} for c in s.calls if c[0] == "delete")
    log = s.calls[log_at][3][0]
    assert log["run_id"] == "r1" and log["status"] == "complete"
    assert counts["food_price_country"] == 1 and counts["food_price_artifact"] >= 5


def test_main_without_credentials_is_a_no_op(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    assert supabase.main() == 0


def test_read_only_keys_are_rejected_before_any_call():
    s = FakeSession()
    with pytest.raises(RuntimeError, match="publishable"):
        supabase.publish(_con(), "https://x.supabase.co", "sb_publishable_abc", session=s)
    assert s.calls == []
