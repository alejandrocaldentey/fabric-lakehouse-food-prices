import pytest

from ingestion import worldbank


def _row(country: str, year: str, value: float | None) -> dict:
    return {
        "indicator": {"id": "FP.CPI.TOTL.ZG", "value": "Inflation, consumer prices (annual %)"},
        "country": {"id": country[:2], "value": f"Country {country}"},
        "countryiso3code": country,
        "date": year,
        "value": value,
        "unit": "",
        "obs_status": "",
        "decimal": 1,
    }


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append(dict(params))
        return FakeResponse(self.pages[params["page"] - 1])


def test_walks_every_page_and_flattens_rows():
    pages = [
        [
            {"page": 1, "pages": 2, "per_page": 2, "total": 3},
            [_row("ESP", "2024", 2.8), _row("ESP", "2023", 3.5)],
        ],
        [{"page": 2, "pages": 2, "per_page": 2, "total": 3}, [_row("FRA", "2024", None)]],
    ]
    session = FakeSession(pages)

    obs = worldbank.fetch_indicator("FP.CPI.TOTL.ZG", "ESP;FRA", "2023:2024", session=session)

    assert [c["page"] for c in session.calls] == [1, 2]
    assert session.calls[0]["date"] == "2023:2024"
    assert len(obs) == 3
    assert obs[0].country_iso3 == "ESP" and obs[0].year == 2024 and obs[0].value == 2.8
    assert obs[2].value is None  # missing values are kept, not dropped, so silver can flag them


def test_empty_result_returns_no_rows():
    session = FakeSession([[{"page": 1, "pages": 0, "total": 0}, None]])
    assert worldbank.fetch_indicator("X", session=session) == []


def test_api_error_message_is_raised():
    session = FakeSession([[{"message": [{"id": "120", "value": "Invalid value"}]}]])
    with pytest.raises(worldbank.WorldBankError):
        worldbank.fetch_indicator("BAD.CODE", session=session)


@pytest.mark.live
def test_live_api_returns_spain_inflation():
    obs = worldbank.fetch_indicator("FP.CPI.TOTL.ZG", "ESP", "2015:2020")
    assert {o.year for o in obs} >= {2015, 2020}
