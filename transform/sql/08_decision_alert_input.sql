-- decision_alert_input: everything an alert rule may test, one row per country and year.
-- Built after the predictive layer, so the champion forecast for next year sits on the latest row.
WITH latest AS (
    SELECT country_iso3, MAX(year) AS last_year
    FROM diamond_country_year
    WHERE consumer_food_price_change_pct IS NOT NULL
    GROUP BY country_iso3
),

frontier AS (
    SELECT MAX(last_year) AS max_year FROM latest
),

champion AS (
    SELECT country_iso3, target_year, predicted, lower_80, upper_80
    FROM ml_forecast
    WHERE is_champion
)

SELECT
    d.*,
    d.year = l.last_year AS is_latest,
    CASE WHEN d.year = l.last_year THEN f.max_year - l.last_year END AS years_behind,
    c.predicted AS forecast_next_pct,
    c.lower_80 AS forecast_next_lower_pct,
    c.upper_80 AS forecast_next_upper_pct
FROM diamond_country_year AS d
JOIN latest AS l
    ON d.country_iso3 = l.country_iso3
CROSS JOIN frontier AS f
LEFT JOIN champion AS c
    ON d.country_iso3 = c.country_iso3
    AND c.target_year = d.year + 1
