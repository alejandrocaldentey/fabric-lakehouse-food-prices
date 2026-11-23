-- GENERATED from metrics/metrics.yaml by `python -m metrics.build`. Do not edit by hand.
-- diamond_country_year: one row per country and year, one column per catalogued metric.
WITH c AS (
    SELECT country_iso3, year, value AS cpi_inflation
    FROM fact_price_annual
    WHERE series_code = 'CPI_INFLATION'
)

SELECT
    t.country_iso3,
    t.year,
    t.producer_yoy_pct AS producer_price_change_pct,
    t.consumer_food_yoy_pct AS consumer_food_price_change_pct,
    t.consumer_food_yoy_pct - t.producer_yoy_pct AS food_price_gap_pp,
    CASE WHEN ABS(t.producer_yoy_pct_lag1) >= 1 THEN t.consumer_food_yoy_pct / t.producer_yoy_pct_lag1 END AS pass_through_ratio_lag1,
    t.producer_index AS producer_price_index,
    t.consumer_food_index AS consumer_food_price_index,
    c.cpi_inflation AS headline_inflation_pct,
    t.consumer_food_yoy_pct - c.cpi_inflation AS food_inflation_premium_pp
FROM gold_price_transmission AS t
LEFT JOIN c
    ON t.country_iso3 = c.country_iso3
    AND t.year = c.year
