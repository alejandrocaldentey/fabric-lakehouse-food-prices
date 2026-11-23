# ADR 0007 — Governance as code, structured as a data product

- **Status:** Accepted — decided by Alejandro Caldentey on 2026-11-23
- **Date:** 2026-11-23

## Context

Governance usually lives in a catalogue tool that the code never sees, and drifts from what actually runs. In this repo, governance must be reviewable in a pull request and true by construction.

## Options considered

| Option | Visible in the repo | Has a UI | Runs without a tenant |
|---|---|---|---|
| **Data product as code** — descriptor, contracts per layer, lineage generated from SQL | Yes | Generated docs; portal in case 3 | Yes |
| Microsoft Purview scanning the Fabric workspace | No | Yes | No |
| Contracts and tests only | Partly | No | Yes |

## Decision

**Data product as code**, in three parts:

1. **Descriptor** — [`governance/product.yaml`](../../governance/product.yaml): owner, purpose, consumers, classification, personal data, licence, SLA, input and output ports.
2. **Contracts at every published layer** — [`quality/contracts/`](../../quality/contracts/): silver, gold and Diamond. The run stops at the first broken contract, before anything downstream is built.
3. **Lineage from the code** — `python -m governance.build` parses the SQL and renders [`docs/governance.md`](../governance.md); CI fails if it is stale.

The same descriptor, contracts and lineage are exported as JSON for **our own governance portal**, built as its own portfolio case (case 3) and published on Vercel: a catalogue UI over every repo's data products.

How this maps to Purview, for a client that runs it: descriptor → data product and glossary terms in Purview Unified Catalog; contracts → data quality rules; lineage → Fabric lineage, already captured natively.

## Consequences

- ✅ Ownership, classification and lineage change in the same pull request as the code they describe.
- ✅ A portable pattern: the same files can feed Purview, Collibra, OpenMetadata or our own portal.
- ⚠️ Table-level lineage only; column-level lineage would need a SQL parser (e.g. sqlglot) and is a planned refinement.
