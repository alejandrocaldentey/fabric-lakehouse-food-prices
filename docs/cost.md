# Cost per scenario

Generated from [`cost/model.yaml`](../cost/model.yaml). Currency: EUR. Region: West Europe. Ranges, not quotes.

## Scenarios

| Scenario | Assumptions |
|---|---|
| Demo / PoC | Daily run, < 10 GB, 1 author, single environment, capacity paused outside runs (~60 h/month) |
| SME | Hourly run, 100 GB - 1 TB, 35 report users, dev + prod, capacity always on |
| Enterprise | Near real time, 10 TB+, hundreds of viewers (free on F64), 30 authors, dev + test + prod |

## Monthly cost by component

| Process | Option | Demo / PoC | SME | Enterprise | Price checked |
|---|---|---|---|---|---|
| Compute (ingestion + transformation + serving) | Microsoft Fabric capacity | 14-24 (sku F2, cu_hours 120) | 689-1,156 (sku F8, cu_hours 5840) | 5,513-9,251 (sku F64, cu_hours 46720) | [2026-11-20](https://sparklesolutions.ee/en/insights/fabric-capacity-pricing/) |
| Storage | OneLake storage (hot) | pending (gb 10) | pending (gb 1000) | pending (gb 10000) | [not yet](https://azure.microsoft.com/pricing/details/microsoft-fabric/) |
| BI consumption | Power BI Pro licences (authors; all users below F64) | 12-12 (users 1) | 424-424 (users 35) | 363-363 (users 30) | [2026-11-20](https://www.microsoft.com/en-ie/power-platform/products/power-bi/pricing) |
| CI/CD | GitHub Actions (standard runners, public repo) | 0-0 (units 1) | 0-0 (units 1) | 0-0 (units 1) | [2026-11-20](https://docs.github.com/billing/managing-billing-for-github-actions/about-billing-for-github-actions) |

> 3 cells are pending price verification against the official calculators.
