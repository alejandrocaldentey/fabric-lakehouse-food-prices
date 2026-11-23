import pytest

from ingestion import eurostat


def cube(values):
    """A tiny JSON-stat 2.0 cube: 1 unit x 2 countries x 3 years."""
    return {
        "version": "2.0",
        "class": "dataset",
        "id": ["unit", "geo", "time"],
        "size": [1, 2, 3],
        "dimension": {
            "unit": {"category": {"index": {"I20": 0}}},
            "geo": {"category": {"index": {"ES": 0, "EL": 1}}},
            "time": {"category": {"index": {"2021": 0, "2022": 1, "2023": 2}}},
        },
        "value": values,
    }


def test_flatten_sparse_dict_maps_positions_to_codes():
    recs = eurostat.flatten(cube({"0": 100.0, "4": 120.5}))  # ES-2021 and EL-2022
    assert recs == [
        {"unit": "I20", "geo": "ES", "time": "2021", "value": 100.0},
        {"unit": "I20", "geo": "EL", "time": "2022", "value": 120.5},
    ]


def test_flatten_dense_list_skips_missing_values():
    recs = eurostat.flatten(cube([1.0, None, 3.0, 4.0, 5.0, 6.0]))
    assert len(recs) == 5
    assert {"unit": "I20", "geo": "EL", "time": "2023", "value": 6.0} in recs


def test_error_payload_raises():
    with pytest.raises(eurostat.EurostatError):
        eurostat.flatten({"error": {"status": 400, "label": "bad query"}})


class FakeSession:
    def __init__(self, payload):
        self.payload, self.params = payload, None

    def get(self, url, params=None, timeout=None):
        self.url, self.params = url, params
        payload = self.payload

        class R:
            def raise_for_status(self):
                return None

            def json(self):
                return payload

        return R()


def test_fetch_builds_repeated_filters_and_since():
    s = FakeSession(cube({"0": 1.0}))
    recs = eurostat.fetch_dataset(
        "apri_pi_outa", {"geo": ["ES", "FR"], "unit": "I20"}, "2021", session=s
    )
    assert ("geo", "ES") in s.params and ("geo", "FR") in s.params
    assert ("sinceTimePeriod", "2021") in s.params
    assert recs[0]["_dataset"] == "apri_pi_outa"


@pytest.mark.live
def test_live_producer_and_food_prices_for_spain():
    from ingestion.plan import load_sources

    for src in [s for s in load_sources() if s["api"] == "eurostat"]:
        recs = eurostat.fetch_dataset(src["dataset"], {**src["filters"], "geo": "ES"}, "2020")
        assert recs, f"no rows for {src['dataset']}"
