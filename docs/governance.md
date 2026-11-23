# Governance — Food price transmission in Europe

Generated from [`governance/product.yaml`](../governance/product.yaml), the source registry and the SQL itself by `python -m governance.build`.

## Data product

| Field | Value |
|---|---|
| Name | `food-price-transmission` |
| Domain | Agri-food economics |
| Owner | Alejandro Caldentey |
| Purpose | Show how changes in farm-gate prices reach consumer food prices, forecast next year and turn signals into role-specific actions. |
| Classification | public (personal data: no) |
| Licence | Derived from Eurostat (reuse with attribution) and World Bank (CC BY 4.0) |
| Freshness SLA | weekly |
| Consumers | Power BI semantic model (Fabric, Direct Lake); Public dashboard (Vercel, read-only API on Supabase); Fabric data agent (natural-language questions) |

## Output ports

| Table | Description | Contract |
|---|---|---|
| `diamond_country_year` | Certified metrics, one row per country and year | [quality/contracts/diamond_country_year.yaml](../quality/contracts/diamond_country_year.yaml) |
| `ml_forecast` | Next year's consumer food price change per country and model, with an 80% interval | [quality/contracts/ml_forecast.yaml](../quality/contracts/ml_forecast.yaml) |
| `ml_model_registry` | Catalogued models scored on a rolling-origin backtest, champion flagged | [quality/contracts/ml_model_registry.yaml](../quality/contracts/ml_model_registry.yaml) |
| `decision_alert` | Fired alert rules by country and year, linked to role playbooks | [quality/contracts/decision_alert.yaml](../quality/contracts/decision_alert.yaml) |
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
        seed_index_base
    end
    subgraph Bronze
        bronze_eurostat
        bronze_worldbank
    end
    subgraph Silver
        silver_price_index_chained[(silver_price_index_chained)]
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
    subgraph Predictive
        ml_backtest
        ml_coefficient
        ml_forecast[(ml_forecast)]
        ml_model_registry[(ml_model_registry)]
    end
    subgraph Decision
        decision_alert[(decision_alert)]
        decision_alert_input
    end
    bronze_eurostat --> silver_price_observation
    bronze_worldbank --> silver_price_observation
    seed_country --> silver_price_observation
    seed_index_base --> silver_price_index_chained
    silver_price_observation --> silver_price_index_chained
    seed_country --> dim_country
    silver_price_observation --> dim_country
    seed_dim_series --> dim_series
    silver_price_index_chained --> fact_price_annual
    silver_price_observation --> fact_price_annual
    fact_price_annual --> gold_price_transmission
    fact_price_annual --> diamond_country_year
    gold_price_transmission --> diamond_country_year
    gold_price_transmission --> ml_model_registry
    gold_price_transmission --> ml_backtest
    gold_price_transmission --> ml_forecast
    gold_price_transmission --> ml_coefficient
    diamond_country_year --> decision_alert_input
    ml_forecast --> decision_alert_input
    decision_alert_input --> decision_alert
    ml_model_registry --> decision_alert
```

Tables drawn as cylinders have a data contract, checked right after they are built.
