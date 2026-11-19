# Cost per scenario

Generated from [`cost/model.yaml`](../cost/model.yaml). Currency: EUR. Region: West Europe. Ranges, not quotes.

## Scenarios

| Scenario | Assumptions |
|---|---|
| Demo / PoC | Daily run, < 10 GB, 1-5 users, single environment, capacity paused outside runs |
| SME | Hourly run, 100 GB - 1 TB, 20-50 users, dev + prod |
| Enterprise | Near real time, 10 TB+, hundreds of users, dev + test + prod |

## Monthly cost by component

| Process | Option | Demo / PoC | SME | Enterprise | Price checked |
|---|---|---|---|---|---|
| Compute (ingestion + transformation + serving) | Microsoft Fabric capacity | pending (sku F2, hours 60) | pending (sku F8, hours 730) | pending (sku F64, hours 730) | [not yet](https://azure.microsoft.com/pricing/details/microsoft-fabric/) |
| Storage | OneLake storage | pending (gb 10) | pending (gb 1000) | pending (gb 10000) | [not yet](https://azure.microsoft.com/pricing/details/microsoft-fabric/) |
| BI consumption | Power BI Pro licences (viewers below F64) | pending (users 0) | pending (users 35) | pending (users 0) | [not yet](https://www.microsoft.com/power-platform/products/power-bi/pricing) |
| CI/CD | GitHub Actions (public repo) | pending (units 1) | pending (units 1) | pending (units 1) | [not yet](https://docs.github.com/billing/managing-billing-for-github-actions/about-billing-for-github-actions) |

> 12 cells are pending price verification against the official calculators.
