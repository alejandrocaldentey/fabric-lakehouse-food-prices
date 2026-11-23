# Metric catalogue

Generated from [`metrics/metrics.yaml`](../metrics/metrics.yaml). Every published number comes from one definition here and is materialised in `diamond_country_year` (grain: country_iso3, year).

| Metric | Label | Unit | Status | Definition | Owner |
|---|---|---|---|---|---|
| `producer_price_change_pct` | Farm-gate price change | % | certified | Year-on-year change of the agricultural output price index (agricultural goods incl. fruit and vegetables).<br>`t.producer_yoy_pct` | Alejandro Caldentey |
| `consumer_food_price_change_pct` | Consumer food price change | % | certified | Year-on-year change of the HICP for food and non-alcoholic beverages.<br>`t.consumer_food_yoy_pct` | Alejandro Caldentey |
| `food_price_gap_pp` | Consumer vs farm-gate gap | pp | certified | Consumer food price change minus farm-gate price change. Positive means consumers paid more than the farm-gate change explains.<br>`t.consumer_food_yoy_pct - t.producer_yoy_pct` | Alejandro Caldentey |
| `pass_through_ratio_lag1` | Pass-through ratio (1-year lag) | ratio | experimental | Consumer food price change this year per point of farm-gate change last year. Undefined when last year's farm-gate change was under 1 point, where the ratio explodes.<br>`CASE WHEN ABS(t.producer_yoy_pct_lag1) >= 1 THEN t.consumer_food_yoy_pct / t.producer_yoy_pct_lag1 END` | Alejandro Caldentey |
| `producer_price_index` | Farm-gate price level | index (2020 = 100) | certified | Agricultural output price index, chain-linked across Eurostat bases and rebased to 2020 = 100. Compare levels with the consumer index directly.<br>`t.producer_index` | Alejandro Caldentey |
| `consumer_food_price_index` | Consumer food price level | index (2020 = 100) | certified | HICP food and non-alcoholic beverages, rebased to 2020 = 100.<br>`t.consumer_food_index` | Alejandro Caldentey |
| `headline_inflation_pct` | Headline inflation | % | certified | Consumer price inflation, all items (World Bank).<br>`c.cpi_inflation` | Alejandro Caldentey |
| `food_inflation_premium_pp` | Food inflation premium | pp | certified | Consumer food price change minus headline inflation. Positive means food rose faster than the overall basket.<br>`t.consumer_food_yoy_pct - c.cpi_inflation` | Alejandro Caldentey |
