# ADR 0003 — Transformations as portable SQL, tested locally on DuckDB

- **Status:** Proposed — awaiting sign-off by Alejandro Caldentey
- **Date:** 2026-11-23
- **Deciders:** Alejandro Caldentey

## Context

Silver and gold logic will run in Fabric (Spark), but we want every rule to be testable in seconds on a laptop and in CI, without a Fabric capacity running. Capacity time is the largest cost line in [cost.md](../cost.md).

## Options considered

| Option | Pros | Cons |
|---|---|---|
| **SQL files in a portable subset (Spark SQL ∩ DuckDB), executed by Spark in Fabric and by DuckDB in tests** | Business rules readable by analysts; tests run in < 1 s; zero capacity cost for development | Must avoid dialect-specific functions; a few helpers differ |
| PySpark DataFrame code in notebooks | Native to Fabric; full Spark API | Needs a JVM and Spark to test; rules hidden in Python |
| dbt on Fabric (dbt-fabricspark) | Lineage, docs and tests out of the box | Another tool and adapter to operate; adapter maturity |

## Decision

**Portable SQL files** in `transform/sql/`, one file per table, executed in dependency order. Locally and in CI they run on DuckDB over the bronze JSON lines; in Fabric a thin notebook runs the same files with `spark.sql`.

Allowed SQL: `SELECT`, CTEs, joins, `GROUP BY`, `CASE`, window functions (`ROW_NUMBER`, `LAG`), `CAST`, `COALESCE`, `AVG`, `COUNT`. No engine-specific functions in the shared files.

## Consequences

- ✅ Every silver/gold rule has a unit test with hand-written bronze rows.
- ✅ Development costs nothing on the Fabric capacity.
- ⚠️ Discipline needed to stay inside the portable subset; CI runs the files on DuckDB, and a Fabric smoke run validates them on Spark.

## When we would revisit

The model grows past ~30 tables or needs incremental materialisations, lineage docs and exposures → move to dbt.
