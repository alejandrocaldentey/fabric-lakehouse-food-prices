-- silver_price_observation: typed, conformed and deduplicated observations from every source.
-- Portable SQL (Spark SQL and DuckDB). See docs/adr/0003-portable-sql-transformations.md.
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

faostat AS (
    SELECT
        'faostat' AS source,
        c.iso3 AS country_iso3,
        CAST(f.year AS INT) AS year,
        -- FAOSTAT months codes: 7001-7012 = January-December, 7021 = annual value
        CASE
            WHEN CAST(f.months_code AS INT) BETWEEN 7001 AND 7012 THEN CAST(f.months_code AS INT) - 7000
            ELSE CAST(NULL AS INT)
        END AS month,
        s.series_code,
        COALESCE(f.item_code, 'ALL') AS item_code,
        f.item AS item_name,
        CAST(f.value AS DOUBLE) AS value,
        f.unit,
        CAST(f.ingested_at AS TIMESTAMP) AS ingested_at
    FROM bronze_faostat AS f
    JOIN seed_country AS c
        ON CAST(f.area_code_m49 AS INT) = c.m49
    JOIN seed_faostat_series AS s
        ON f.domain = s.domain
        AND f.element LIKE s.element_like
        AND f.item LIKE s.item_like
),

unioned AS (
    SELECT * FROM worldbank
    UNION ALL
    SELECT * FROM faostat
),

ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY source, country_iso3, year, month, series_code, item_code
            ORDER BY ingested_at DESC
        ) AS rn
    FROM unioned
)

SELECT
    source, country_iso3, year, month, series_code, item_code, item_name, value, unit, ingested_at
FROM ranked
WHERE rn = 1
