-- dim_country: every country that has at least one silver observation.
SELECT DISTINCT
    o.country_iso3,
    c.name AS country_name
FROM silver_price_observation AS o
JOIN seed_country AS c
    ON o.country_iso3 = c.iso3
