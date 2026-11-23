# ADR 0005 — Load strategy: rolling window + MERGE by default, per-source override

- **Status:** Accepted — decided by Alejandro Caldentey on 2026-11-23
- **Date:** 2026-11-23

## Context

Official statistics are **revised after first publication**: Eurostat and the World Bank routinely correct the last two or three years. A load strategy that only appends new periods would freeze the first, wrong estimate forever.

## Options considered

| Strategy | Catches revisions | Cost per run | Fits |
|---|---|---|---|
| **Rolling window + MERGE** — re-pull the last N periods, MERGE on the natural key | Yes, within the window | Low, bounded by N | Revised statistics (default) |
| Watermark append — pull only periods after the last one loaded | No | Lowest | Immutable event or log data |
| Full reload — re-pull everything | Yes, all history | Grows with history | Small reference tables, or rebuilds |

## Decision

**Rolling window + MERGE** is the default (`window_years: 3`). Each source declares its strategy in [`ingestion/sources.yaml`](../../ingestion/sources.yaml), so watermark or full reload are one line away when a source needs them. [`ingestion/plan.py`](../../ingestion/plan.py) turns the strategy into the period range to request; it is pure logic and unit-tested.

- **Bronze** is append-only, partitioned by ingestion date: every pull is kept, so any revision can be audited.
- **Silver** is a Delta table MERGEd on `source, country_iso3, year, month, series_code, item_code`; the newest ingestion wins. Delta time travel keeps the previous values.
- **Gold and Diamond** are rebuilt from silver: they are small, and a rebuild is simpler and safer than incremental logic.

## Consequences

- ✅ Revisions inside the window flow through automatically; time travel answers "what did we report last month?".
- ⚠️ Revisions older than the window are missed until a scheduled full reload (monthly).
- ⚠️ Bronze grows with every run; a retention policy (e.g. 13 months) keeps it bounded.

## When we would revisit

A source starts publishing real-time or event data (watermark), or gold grows large enough to need incremental builds.
