import pytest

from ingestion import faostat


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.url = None
        self.params = None

    def get(self, url, params=None, timeout=None):
        self.url, self.params = url, params
        return FakeResponse(self.payload)


def test_builds_filters_and_keeps_rows_as_returned():
    rows = [{"Area": "Spain", "Item": "Wheat", "Year": "2023", "Value": 245.1}]
    session = FakeSession({"data": rows})

    out = faostat.fetch_domain("PP", areas=[203], years=[2022, 2023], session=session)

    assert session.url.endswith("/en/data/PP")
    assert session.params == {"area": "203", "year": "2022,2023", "output_type": "objects"}
    assert out[0]["Value"] == 245.1 and out[0]["_domain"] == "PP" and out[0]["_source"] == "faostat"


def test_unexpected_shape_raises():
    with pytest.raises(faostat.FaostatError):
        faostat.fetch_domain("PP", session=FakeSession(["not", "a", "dict"]))


@pytest.mark.live
def test_live_api_returns_producer_prices_for_spain():
    rows = faostat.fetch_domain("PP", areas=[203], years=[2022])
    assert rows, "FAOSTAT returned no rows for Spain 2022"
