-- fact_price_annual: one value per country, year and series.
-- Monthly values are averaged to the year first, then items are averaged (unweighted).
WITH item_year AS (
    SELECT
        country_iso3,
        year,
        series_code,
        item_code,
        AVG(value) AS item_value
    FROM silver_price_observation
    WHERE value IS NOT NULL
    GROUP BY country_iso3, year, series_code, item_code
)

SELECT
    country_iso3,
    year,
    series_code,
    AVG(item_value) AS value,
    COUNT(*) AS n_items
FROM item_year
GROUP BY country_iso3, year, series_code
