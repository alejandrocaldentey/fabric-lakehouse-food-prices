-- silver_price_index_chained: one continuous index per country and series, rebased to 2020 = 100.
-- Eurostat publishes the farm-gate index in five bases (2000, 2005, 2010, 2015, 2020 = 100),
-- each covering only some years. Levels from different bases are not comparable, so:
--   1. the newest base wins every year it covers (seed_index_base.priority);
--   2. an older base only fills the years before every newer base starts;
--   3. it is ratio-linked at the year the next newer base starts (backward chaining),
--      which keeps each base's own growth rates;
--   4. if a link year is missing, the chain stops there (no invented values);
--   5. every series is rebased so 2020 = 100, which makes producer and consumer levels comparable.
-- See docs/adr/0010-chain-linked-price-indices.md.
WITH obs AS (
    SELECT
        s.country_iso3,
        s.year,
        s.series_code,
        s.unit,
        CAST(b.priority AS INT) AS priority,
        AVG(s.value) AS value
    FROM silver_price_observation AS s
    JOIN seed_index_base AS b
        ON s.series_code = b.series_code
        AND s.unit = b.unit
    WHERE s.value > 0
        AND s.month IS NULL
    GROUP BY s.country_iso3, s.year, s.series_code, s.unit, b.priority
),

coverage AS (
    SELECT
        country_iso3,
        series_code,
        unit,
        priority,
        MIN(year) AS first_year
    FROM obs
    GROUP BY country_iso3, series_code, unit, priority
),

-- a base is useful only if it starts before every newer base
useful AS (
    SELECT
        *,
        MIN(first_year) OVER (
            PARTITION BY country_iso3, series_code
            ORDER BY priority
            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
        ) AS newer_first_year
    FROM coverage
),

ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (PARTITION BY country_iso3, series_code ORDER BY priority) AS link_rank
    FROM useful
    WHERE newer_first_year IS NULL
        OR first_year < newer_first_year
),

links AS (
    SELECT
        o.country_iso3,
        o.series_code,
        o.unit,
        o.link_rank,
        o.first_year,
        n.first_year AS link_year,
        nv.value / ov.value AS link_ratio
    FROM ranked AS o
    LEFT JOIN ranked AS n
        ON o.country_iso3 = n.country_iso3
        AND o.series_code = n.series_code
        AND n.link_rank = o.link_rank - 1
    LEFT JOIN obs AS nv
        ON nv.country_iso3 = n.country_iso3
        AND nv.series_code = n.series_code
        AND nv.unit = n.unit
        AND nv.year = n.first_year
    LEFT JOIN obs AS ov
        ON ov.country_iso3 = o.country_iso3
        AND ov.series_code = o.series_code
        AND ov.unit = o.unit
        AND ov.year = n.first_year
),

factors AS (
    SELECT
        *,
        -- product of every link ratio from the newest base down to this one
        EXP(SUM(LN(COALESCE(link_ratio, 1.0))) OVER (
            PARTITION BY country_iso3, series_code
            ORDER BY link_rank
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        )) AS chain_factor,
        -- a missing link breaks the chain for this base and every older one
        SUM(CASE WHEN link_rank > 1 AND link_ratio IS NULL THEN 1 ELSE 0 END) OVER (
            PARTITION BY country_iso3, series_code
            ORDER BY link_rank
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS breaks
    FROM links
),

chained AS (
    SELECT
        o.country_iso3,
        o.year,
        o.series_code,
        o.unit AS source_unit,
        o.value AS source_value,
        f.chain_factor,
        f.link_year,
        o.value * f.chain_factor AS chained_value
    FROM obs AS o
    JOIN factors AS f
        ON o.country_iso3 = f.country_iso3
        AND o.series_code = f.series_code
        AND o.unit = f.unit
    WHERE f.breaks = 0
        AND (f.link_year IS NULL OR o.year < f.link_year)
),

reference AS (
    SELECT country_iso3, series_code, chained_value AS ref_value
    FROM chained
    WHERE year = 2020
)

SELECT
    c.country_iso3,
    c.year,
    c.series_code,
    100.0 * c.chained_value / r.ref_value AS index_value,
    c.source_unit,
    c.source_value,
    c.chain_factor * 100.0 / r.ref_value AS rebase_factor,
    c.link_year
FROM chained AS c
JOIN reference AS r
    ON c.country_iso3 = r.country_iso3
    AND c.series_code = r.series_code
