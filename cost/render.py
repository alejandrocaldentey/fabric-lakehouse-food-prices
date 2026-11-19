"""Render cost/model.yaml into docs/cost.md.

Unverified prices (null) are reported as "pending" — the report never invents a number.
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "cost" / "model.yaml"
REPORT = ROOT / "docs" / "cost.md"
SCENARIOS = ("demo", "sme", "enterprise")


def _quantity(usage: dict) -> float:
    """The numeric usage driver of a component in one scenario (hours, gb, users, units)."""
    numbers = [v for k, v in usage.items() if k != "sku" and isinstance(v, int | float)]
    return float(numbers[0]) if numbers else 0.0


def _usage_label(usage: dict) -> str:
    return ", ".join(f"{k} {v}" for k, v in usage.items())


def monthly_range(component: dict, scenario: str) -> tuple[float, float] | None:
    price = component.get("unit_price") or {}
    low, high = price.get("low"), price.get("high")
    if low is None or high is None:
        return None
    qty = _quantity(component["usage_per_month"][scenario])
    return qty * float(low), qty * float(high)


def render(model: dict) -> str:
    cur = model["currency"]
    lines = [
        "# Cost per scenario",
        "",
        (
            f"Generated from [`cost/model.yaml`](../cost/model.yaml). Currency: {cur}. "
            f"Region: {model['region']}. Ranges, not quotes."
        ),
        "",
        "## Scenarios",
        "",
        "| Scenario | Assumptions |",
        "|---|---|",
    ]
    for key in SCENARIOS:
        sc = model["scenarios"][key]
        lines.append(f"| {sc['label']} | {sc['assumptions']} |")

    header = " | ".join(model["scenarios"][k]["label"] for k in SCENARIOS)
    lines += [
        "",
        "## Monthly cost by component",
        "",
        f"| Process | Option | {header} | Price checked |",
    ]
    lines.append("|---|---|" + "---|" * len(SCENARIOS) + "---|")
    pending = 0
    for comp in model["components"]:
        cells = []
        for key in SCENARIOS:
            usage = _usage_label(comp["usage_per_month"][key])
            rng = monthly_range(comp, key)
            if rng is None:
                pending += 1
                cells.append(f"pending ({usage})")
            else:
                cells.append(f"{rng[0]:,.0f}-{rng[1]:,.0f} ({usage})")
        checked = comp.get("verified_on") or "not yet"
        src = f"[{checked}]({comp['source']})"
        lines.append(
            f"| {comp['process']} | {comp['option']} | " + " | ".join(cells) + f" | {src} |"
        )

    if pending:
        lines += [
            "",
            f"> {pending} cells are pending price verification against the official calculators.",
        ]
    return "\n".join(lines) + "\n"


def main() -> int:
    model = yaml.safe_load(MODEL.read_text())
    REPORT.write_text(render(model))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
