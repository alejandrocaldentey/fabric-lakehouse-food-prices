# Governance — Food price transmission in Europe

Generated from [`governance/product.yaml`](../governance/product.yaml), the source registry and the SQL itself by `python -m governance.build`.

## Data product

| Field | Value |
|---|---|
| Name | `food-price-transmission` |
| Domain | Agri-food economics |
| Owner | Alejandro Caldentey |
| Purpose | Show how changes in farm-gate prices reach consumer food prices, by country and year. |
| Classification | public (personal data: no) |
| Licence | Derived from Eurostat (reuse with attribution) and World Bank (CC BY 4.0) |
| Freshness SLA | weekly |
| Consumers | Power BI semantic model (Fabric, Direct Lake); Public dashboard (Vercel, read-only API on Supabase); Fabric data agent (natural-language questions) |

## Output ports

| Table | Description | Contract |
|---|---|---|
| `diamond_country_year` | Certified metrics, one row per country and year | [quality/contracts/diamond_country_year.yaml](../quality/contracts/diamond_country_year.yaml) |
| `gold_price_transmission` | Producer vs consumer food price changes, side by side | [quality/contracts/gold_price_transmission.yaml](../quality/contracts/gold_price_transmission.yaml) |

## Sources

| Source | Dataset / indicator | Load strategy |
|---|---|---|
| eurostat | `apri_pi_outa` | window_merge (3 years) |
| eurostat | `prc_hicp_aind` | window_merge (3 years) |
| worldbank | `FP.CPI.TOTL.ZG` | window_merge (3 years) |

## Lineage

```mermaid
flowchart LR
    subgraph Seeds
        seed_country
        seed_dim_series
    end
    subgraph Bronze
        bronze_eurostat
        bronze_worldbank
    end
    subgraph Silver
        silver_price_observation[(silver_price_observation)]
    end
    subgraph Gold
        dim_country
        dim_series
        fact_price_annual
        gold_price_transmission[(gold_price_transmission)]
    end
    subgraph Diamond
        diamond_country_year[(diamond_country_year)]
    end
    bronze_eurostat --> silver_price_observation
    bronze_worldbank --> silver_price_observation
    seed_country --> silver_price_observation
    seed_country --> dim_country
    silver_price_observation --> dim_country
    seed_dim_series --> dim_series
    silver_price_observation --> fact_price_annual
    fact_price_annual --> gold_price_transmission
    fact_price_annual --> diamond_country_year
    gold_price_transmission --> diamond_country_year
```

Tables drawn as cylinders have a data contract, checked right after they are built.
