# Semantic model

Generated from [`semantic/model.yaml`](../semantic/model.yaml), the [metric catalogue](metrics.md) and the column types of the tables the pipeline builds, by `python -m semantic.build` ([ADR 0013](adr/0013-direct-lake-semantic-model.md)).

**Food price transmission** — Direct Lake on OneLake, lakehouse schema `dbo`. TMDL item: [`fabric/FoodPriceTransmission.SemanticModel/`](../fabric/FoodPriceTransmission.SemanticModel/).

## Tables

| Table | Columns | Hidden | Description |
|---|---|---|---|
| `dim_country` | 2 | 0 | One row per country with at least one observation. |
| `dim_series` | 4 | 0 | The price series the lakehouse measures. |
| `fact_price_annual` | 5 | 3 | Annual value per country and series. Index series are chain-linked and rebased to 2020 = 100. |
| `diamond_country_year` | 10 | 9 | Certified metrics, one row per country and year. Read the measures, not the columns. |

## Relationships (many to one, single direction)

- `fact_price_annual.country_iso3` → `dim_country.country_iso3`
- `fact_price_annual.series_code` → `dim_series.series_code`
- `diamond_country_year.country_iso3` → `dim_country.country_iso3`

## Measures

| Measure | Folder | Format | DAX |
|---|---|---|---|
| Farm-gate price change | Certified | `0.0"%"` | `AVERAGE ( diamond_country_year[producer_price_change_pct] )` |
| Consumer food price change | Certified | `0.0"%"` | `AVERAGE ( diamond_country_year[consumer_food_price_change_pct] )` |
| Consumer vs farm-gate gap | Certified | `+0.0" pp";-0.0" pp";0.0" pp"` | `AVERAGE ( diamond_country_year[food_price_gap_pp] )` |
| Pass-through ratio (1-year lag) | Experimental | `0.00` | `IF ( COUNTROWS ( diamond_country_year ) = 1, MAX ( diamond_country_year[pass_through_ratio_lag1] ) )` |
| Farm-gate price level | Certified | `0.0` | `AVERAGE ( diamond_country_year[producer_price_index] )` |
| Consumer food price level | Certified | `0.0` | `AVERAGE ( diamond_country_year[consumer_food_price_index] )` |
| Headline inflation | Certified | `0.0"%"` | `AVERAGE ( diamond_country_year[headline_inflation_pct] )` |
| Food inflation premium | Certified | `+0.0" pp";-0.0" pp";0.0" pp"` | `AVERAGE ( diamond_country_year[food_inflation_premium_pp] )` |
