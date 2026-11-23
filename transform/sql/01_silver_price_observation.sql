-- silver_price_observation: typed, conformed and deduplicated observations from every source.
-- One row per base (unit) as well: the farm-gate index arrives in several bases.
-- Portable SQL (Spark SQL and DuckDB). See docs/adr/0003-portable-sql-transformations.md.
-- In Fabric this result is MERGEd into the Delta table on the natural key (ADR 0005).
WITH worldbank AS (
    SELECT
        'worldbank' AS source,
        country_iso3,
        CAST(year AS INT) AS year,
        CAST(NULL AS INT) AS month,
        'CPI_INFLATION' AS series_code,
        'ALL' AS item_code,
        indicator_name AS item_name,
        CAST(value AS DOUBLE) AS value,
        unit,
        CAST(ingested_at AS TIMESTAMP) AS ingested_at
    FROM bronze_worldbank
    WHERE indicator_id = 'FP.CPI.TOTL.ZG'
),

eurostat AS (
    SELECT
        'eurostat' AS source,
        c.iso3 AS country_iso3,
        CAST(SUBSTR(e.time, 1, 4) AS INT) AS year,
        -- annual periods are 'YYYY'; monthly are 'YYYY-MM' or 'YYYYMmm'
        CASE WHEN LENGTH(e.time) >= 7 THEN CAST(SUBSTR(e.time, 6, 2) AS INT) END AS month,
        e.series_code,
        'ALL' AS item_code,
        e.dataset AS item_name,
        CAST(e.value AS DOUBLE) AS value,
        e.unit,
        CAST(e.ingested_at AS TIMESTAMP) AS ingested_at
    FROM bronze_eurostat AS e
    -- aggregates such as EU27_2020 or EA20 have no ISO code and drop out here
    JOIN seed_country AS c
        ON e.geo_iso2 = c.iso2
    WHERE e.series_code IS NOT NULL
),

unioned AS (
    SELECT * FROM worldbank
    UNION ALL
    SELECT * FROM eurostat
),

ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY source, country_iso3, year, month, series_code, item_code, unit
            ORDER BY ingested_at DESC
        ) AS rn
    FROM unioned
)

SELECT
    source, country_iso3, year, month, series_code, item_code, item_name, value, unit, ingested_at
FROM ranked
WHERE rn = 1
