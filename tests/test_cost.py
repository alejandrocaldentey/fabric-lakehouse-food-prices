from cost import render


def _model(low, high):
    return {
        "currency": "EUR",
        "region": "West Europe",
        "scenarios": {k: {"label": k.upper(), "assumptions": "a"} for k in render.SCENARIOS},
        "components": [
            {
                "process": "Storage",
                "option": "OneLake",
                "unit": "GB-month",
                "unit_price": {"low": low, "high": high},
                "source": "https://example.org",
                "verified_on": "2026-11-19" if low is not None else None,
                "usage_per_month": {
                    "demo": {"gb": 10},
                    "sme": {"gb": 100},
                    "enterprise": {"gb": 1000},
                },
            }
        ],
    }


def test_verified_price_is_multiplied_by_usage():
    comp = _model(0.02, 0.03)["components"][0]
    assert render.monthly_range(comp, "sme") == (2.0, 3.0)


def test_unverified_price_is_reported_as_pending_never_guessed():
    report = render.render(_model(None, None))
    assert "pending (gb 10)" in report
    assert "3 cells are pending" in report


def test_shipped_model_renders():
    import yaml

    model = yaml.safe_load(render.MODEL.read_text())
    assert "# Cost per scenario" in render.render(model)
