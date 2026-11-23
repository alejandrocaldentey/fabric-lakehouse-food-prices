-- fact_price_annual: one value per country, year and series.
-- Price indices come from the chained, rebased series (2020 = 100); rates are averaged to the year.
SELECT
    country_iso3,
    year,
    series_code,
    index_value AS value,
    1 AS n_items
FROM silver_price_index_chained

UNION ALL

SELECT
    country_iso3,
    year,
    series_code,
    AVG(value) AS value,
    COUNT(*) AS n_items
FROM silver_price_observation
WHERE value IS NOT NULL
    AND series_code = 'CPI_INFLATION'
GROUP BY country_iso3, year, series_code
