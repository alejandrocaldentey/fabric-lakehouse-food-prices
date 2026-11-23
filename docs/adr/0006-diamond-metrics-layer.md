# ADR 0006 — Diamond layer: a metric catalogue that generates materialised tables

- **Status:** Accepted — decided by Alejandro Caldentey on 2026-11-23
- **Date:** 2026-11-23

## Context

Gold is a star schema: it says *what happened*, not *what the number means*. Without a metrics layer, "food price gap" would be re-implemented in DAX, in the public dashboard's SQL and in an agent's prompt — three definitions that drift apart.

## Options considered

| Option | Single definition | Reusable outside Power BI | Fast to query |
|---|---|---|---|
| **Metric catalogue (YAML) + generated, materialised Diamond table** | Yes | Yes — SQL, API, agents | Yes |
| Measures only in the Power BI semantic model (DAX) | Inside Power BI only | No | Yes, in Power BI |
| Pre-aggregated Diamond tables in hand-written SQL, no catalogue | No formal definition | Yes | Yes |

## Decision

A combination of the first and third options: **[`metrics/metrics.yaml`](../../metrics/metrics.yaml) is the only place a metric is defined** (name, label, unit, formula, owner, status). `python -m metrics.build` generates:

- `transform/sql/07_diamond_country_year.sql` — the **materialised Diamond table**, one column per metric;
- [`docs/metrics.md`](../metrics.md) — the human-readable catalogue;
- next: the DAX measures of the Fabric semantic model and the read-only API views of the public demo.

CI fails if a generated file is stale, so the catalogue and what runs cannot diverge. Each metric carries a `status` (`certified`, `experimental`, `deprecated`): consumers see which numbers are safe to publish.

## Consequences

- ✅ One definition per number across BI, API and AI agents.
- ✅ Agents get governed metrics with descriptions, not raw columns — the precondition for trustworthy natural-language answers.
- ⚠️ Metric expressions must stay in portable SQL ([ADR 0003](0003-portable-sql-transformations.md)); time-intelligence measures that only make sense in DAX are added on top in the semantic model and listed in the catalogue as such.

## When we would revisit

The number of metrics or consumers grows to the point where a dedicated semantic layer (dbt Semantic Layer, Cube) pays for its operational cost.
