-- gold_price_transmission: producer vs consumer food price changes, side by side.
-- Year-on-year changes are only computed between consecutive years (no silent gaps).
WITH indexed AS (
    SELECT
        country_iso3,
        year,
        series_code,
        value,
        LAG(value) OVER (PARTITION BY country_iso3, series_code ORDER BY year) AS prev_value,
        LAG(year) OVER (PARTITION BY country_iso3, series_code ORDER BY year) AS prev_year
    FROM fact_price_annual
    WHERE series_code IN ('PRODUCER_PI', 'CONSUMER_FOOD_PI')
),

yoy AS (
    SELECT
        country_iso3,
        year,
        series_code,
        CASE
            WHEN prev_year = year - 1 AND prev_value <> 0 THEN 100.0 * (value / prev_value - 1)
            ELSE CAST(NULL AS DOUBLE)
        END AS yoy_pct
    FROM indexed
),

paired AS (
    SELECT
        p.country_iso3,
        p.year,
        p.yoy_pct AS producer_yoy_pct,
        c.yoy_pct AS consumer_food_yoy_pct
    FROM yoy AS p
    JOIN yoy AS c
        ON p.country_iso3 = c.country_iso3
        AND p.year = c.year
        AND c.series_code = 'CONSUMER_FOOD_PI'
    WHERE p.series_code = 'PRODUCER_PI'
),

lagged AS (
    SELECT
        *,
        LAG(producer_yoy_pct) OVER (PARTITION BY country_iso3 ORDER BY year) AS prev_producer_yoy,
        LAG(year) OVER (PARTITION BY country_iso3 ORDER BY year) AS prev_year
    FROM paired
)

SELECT
    country_iso3,
    year,
    producer_yoy_pct,
    consumer_food_yoy_pct,
    consumer_food_yoy_pct - producer_yoy_pct AS gap_pp,
    CASE WHEN prev_year = year - 1 THEN prev_producer_yoy END AS producer_yoy_pct_lag1
FROM lagged
