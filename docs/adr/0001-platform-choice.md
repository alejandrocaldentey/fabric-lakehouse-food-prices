# ADR 0001 — Data platform: Microsoft Fabric

- **Status:** Accepted — signed off by Alejandro Caldentey on 2026-11-20
- **Date:** 2026-11-19
- **Deciders:** Alejandro Caldentey

## Context

We need a platform to ingest three public APIs (World Bank, FAOSTAT, Eurostat), refine them through bronze, silver and gold layers, and serve a semantic model that both humans (BI) and AI agents can query.

Constraints:

1. The target client is a **mid-sized company already on Microsoft 365**: identity, licensing and BI tooling are Microsoft.
2. Data volume is small (well under 10 GB in the demo) but the design must scale to the Enterprise scenario in [cost.md](../cost.md).
3. The serving layer must be **AI-ready**: a governed semantic model that an agent can query, not raw tables.
4. Deployment must be **code-first** and promotable from dev to prod (see [ADR 0002](0002-cicd-github-actions.md)).

## Options considered

| Criterion | Microsoft Fabric | Databricks + Unity Catalog | Snowflake + dbt |
|---|---|---|---|
| Fit with a Microsoft 365 client | Native (Entra ID, Power BI, OneLake) | Good via Azure Databricks | Needs extra integration |
| Lakehouse storage | OneLake, Delta | Delta, Unity Catalog | Proprietary storage (Iceberg optional) |
| BI serving | Direct Lake, no import copy | Power BI over SQL warehouse | Power BI over Snowflake |
| AI on governed metrics | Semantic model + Fabric data agent | Genie / AI/BI on Unity Catalog | Cortex Analyst |
| CI/CD maturity | Git integration + fabric-cicd (younger) | Asset Bundles (mature) | dbt + Terraform (mature) |
| Pricing model | Capacity (F SKU), pausable | DBUs per workload | Credits per warehouse-second |
| Cost per scenario | see [cost.md](../cost.md) | see [cost.md](../cost.md) | see [cost.md](../cost.md) |

## Decision

**Microsoft Fabric**, with a Lakehouse in a medallion layout, PySpark notebooks for transformation, a Direct Lake semantic model prepared for AI, and a Fabric data agent on top.

## Consequences

- ✅ One platform from ingestion to BI and AI, one identity model, one capacity to size and pause.
- ✅ Matches the stack most mid-sized Microsoft clients will run.
- ⚠️ Vendor lock-in: mitigated by keeping data in open Delta format and transformations in plain PySpark/SQL.
- ⚠️ Fabric CI/CD tooling is younger than Databricks Asset Bundles; we accept that and document gaps.
- ⚠️ Capacity is billed while running: the demo pauses capacity outside scheduled runs.

## When we would revisit

- The workload becomes engineering-heavy (streaming, ML training at scale) → Databricks.
- The client is not on Microsoft and wants a SQL-first warehouse → Snowflake.
- Capacity cost in the SME scenario exceeds the alternatives by more than the integration savings.
