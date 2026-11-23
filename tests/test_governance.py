from governance import build


def test_table_refs_ignore_ctes_and_comments():
    sql = """
    -- FROM not_a_table
    WITH x AS (SELECT * FROM a), y AS (SELECT * FROM x JOIN b ON 1 = 1)
    SELECT * FROM y LEFT JOIN c ON 1 = 1
    """
    assert build.table_refs(sql) == {"a", "b", "c"}


def test_lineage_reaches_diamond_from_bronze():
    edges = build.lineage()
    assert "gold_price_transmission" in edges["diamond_country_year"]
    assert {"bronze_eurostat", "bronze_worldbank"} <= set(edges["silver_price_observation"])


def test_governance_doc_is_current():
    assert build.main(["--check"]) == 0
