-- GENERATED from decisions/rules.yaml by `python -m decisions.build`. Do not edit by hand.
-- decision_alert: one row per fired rule, country and year, with its severity and value.
SELECT
    rule_id || ':' || COALESCE(country_iso3, 'ALL') || ':' || CAST(year AS VARCHAR) AS alert_id,
    *
FROM (
    SELECT
        'farm_gate_shock' AS rule_id,
        'market' AS category,
        a.country_iso3, a.year,
        CASE
            WHEN ABS((a.producer_price_change_pct)) >= 20 THEN 'high'
            WHEN ABS((a.producer_price_change_pct)) >= 10 THEN 'medium'
        END AS severity,
        (a.producer_price_change_pct) AS value
    FROM decision_alert_input AS a
    WHERE (ABS((a.producer_price_change_pct)) >= 20) OR (ABS((a.producer_price_change_pct)) >= 10)

    UNION ALL

    SELECT
        'margin_squeeze' AS rule_id,
        'market' AS category,
        a.country_iso3, a.year,
        CASE
            WHEN (a.food_price_gap_pp) <= -10 THEN 'high'
            WHEN (a.food_price_gap_pp) <= -5 THEN 'medium'
        END AS severity,
        (a.food_price_gap_pp) AS value
    FROM decision_alert_input AS a
    WHERE ((a.food_price_gap_pp) <= -10) OR ((a.food_price_gap_pp) <= -5)

    UNION ALL

    SELECT
        'margin_expansion' AS rule_id,
        'market' AS category,
        a.country_iso3, a.year,
        CASE
            WHEN (a.food_price_gap_pp) >= 10 THEN 'high'
            WHEN (a.food_price_gap_pp) >= 5 THEN 'medium'
        END AS severity,
        (a.food_price_gap_pp) AS value
    FROM decision_alert_input AS a
    WHERE ((a.food_price_gap_pp) >= 10) OR ((a.food_price_gap_pp) >= 5)

    UNION ALL

    SELECT
        'food_inflation_premium' AS rule_id,
        'market' AS category,
        a.country_iso3, a.year,
        CASE
            WHEN (a.food_inflation_premium_pp) >= 6 THEN 'high'
            WHEN (a.food_inflation_premium_pp) >= 3 THEN 'medium'
        END AS severity,
        (a.food_inflation_premium_pp) AS value
    FROM decision_alert_input AS a
    WHERE ((a.food_inflation_premium_pp) >= 6) OR ((a.food_inflation_premium_pp) >= 3)

    UNION ALL

    SELECT
        'forecast_food_inflation' AS rule_id,
        'forecast' AS category,
        a.country_iso3, a.year,
        CASE
            WHEN (a.forecast_next_pct) >= 6 THEN 'high'
            WHEN (a.forecast_next_pct) >= 4 THEN 'medium'
        END AS severity,
        (a.forecast_next_pct) AS value
    FROM decision_alert_input AS a
    WHERE a.is_latest AND (((a.forecast_next_pct) >= 6) OR ((a.forecast_next_pct) >= 4))

    UNION ALL

    SELECT
        'data_stale' AS rule_id,
        'data' AS category,
        a.country_iso3, a.year,
        CASE
            WHEN (a.years_behind) >= 2 THEN 'high'
            WHEN (a.years_behind) >= 1 THEN 'medium'
        END AS severity,
        (a.years_behind) AS value
    FROM decision_alert_input AS a
    WHERE a.is_latest AND (((a.years_behind) >= 2) OR ((a.years_behind) >= 1))

    UNION ALL

    SELECT
        'model_drift' AS rule_id,
        'model' AS category,
        CAST(NULL AS VARCHAR) AS country_iso3, m.trained_through AS year,
        CASE
            WHEN (m.mae_recent / NULLIF(m.mae, 0)) >= 2 THEN 'high'
            WHEN (m.mae_recent / NULLIF(m.mae, 0)) >= 1.5 THEN 'medium'
        END AS severity,
        (m.mae_recent / NULLIF(m.mae, 0)) AS value
    FROM ml_model_registry AS m
    WHERE m.is_champion AND (((m.mae_recent / NULLIF(m.mae, 0)) >= 2) OR ((m.mae_recent / NULLIF(m.mae, 0)) >= 1.5))
) AS fired
