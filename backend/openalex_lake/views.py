"""Analysis views over the OpenAlex lake star schema.

Four axes (the ones chosen for this lake), expressed as DuckDB views so they stay
in sync with the facts and cost nothing until queried:

1. Journal scientometrics  — output/impact/OA per journal per year, citation accrual.
2. Collaboration networks   — co-author and co-institution pairs.
3. Topic trends             — topic/field prevalence over time.
4. Coverage / cross-source  — per-journal coverage + join keys for the app DB.

Cross-source note: to join against the app's journal_metrics (SQLite/Postgres),
ATTACH it from DuckDB and join on issn_l — see README. These views expose the
lake side (issn_l / doi / orcid / ror) so that join is a one-liner.
"""
from __future__ import annotations

# name -> CREATE OR REPLACE VIEW statement. Order is irrelevant (no view depends
# on another). All are defensive against NULLs and empty tables.
ANALYSIS_VIEWS: dict[str, str] = {
    # ---- 1. Journal scientometrics ---------------------------------------
    "v_journal_yearly": """
        CREATE OR REPLACE VIEW v_journal_yearly AS
        SELECT
            source_issn_l                              AS issn_l,
            publication_year,
            count(*)                                   AS works,
            sum(cited_by_count)                        AS citations,
            avg(cited_by_count)                        AS mean_citations,
            avg(CASE WHEN is_oa THEN 1.0 ELSE 0.0 END) AS oa_share
        FROM fact_works
        WHERE source_issn_l IS NOT NULL
        GROUP BY source_issn_l, publication_year
    """,
    # Citations *received* per journal per calendar year (accrual over time).
    "v_journal_citation_trend": """
        CREATE OR REPLACE VIEW v_journal_citation_trend AS
        SELECT
            w.source_issn_l        AS issn_l,
            c.year                 AS cited_year,
            sum(c.cited_by_count)  AS citations
        FROM fact_work_counts_by_year c
        JOIN fact_works w USING (work_id)
        WHERE w.source_issn_l IS NOT NULL
        GROUP BY w.source_issn_l, c.year
    """,
    # ---- 2. Collaboration networks ---------------------------------------
    "v_coauthor_pairs": """
        CREATE OR REPLACE VIEW v_coauthor_pairs AS
        SELECT
            a.author_id                 AS author_a,
            b.author_id                 AS author_b,
            count(DISTINCT a.work_id)   AS collaborations
        FROM fact_authorship a
        JOIN fact_authorship b
          ON a.work_id = b.work_id AND a.author_id < b.author_id
        GROUP BY a.author_id, b.author_id
    """,
    "v_institution_collab": """
        CREATE OR REPLACE VIEW v_institution_collab AS
        SELECT
            a.institution_id            AS inst_a,
            b.institution_id            AS inst_b,
            count(DISTINCT a.work_id)   AS collaborations
        FROM fact_authorship a
        JOIN fact_authorship b
          ON a.work_id = b.work_id AND a.institution_id < b.institution_id
        WHERE a.institution_id <> '' AND b.institution_id <> ''
        GROUP BY a.institution_id, b.institution_id
    """,
    # ---- 3. Topic trends --------------------------------------------------
    "v_topic_yearly": """
        CREATE OR REPLACE VIEW v_topic_yearly AS
        SELECT
            t.topic_id,
            any_value(dt.display_name)                 AS topic,
            any_value(dt.field)                        AS field,
            w.publication_year,
            count(*)                                   AS works,
            sum(CASE WHEN t.is_primary THEN 1 ELSE 0 END) AS primary_works
        FROM fact_work_topic t
        JOIN fact_works w USING (work_id)
        LEFT JOIN dim_topic dt USING (topic_id)
        GROUP BY t.topic_id, w.publication_year
    """,
    "v_field_yearly": """
        CREATE OR REPLACE VIEW v_field_yearly AS
        SELECT
            field,
            publication_year,
            count(*)             AS works,
            sum(cited_by_count)  AS citations
        FROM fact_works
        WHERE field IS NOT NULL
        GROUP BY field, publication_year
    """,
    # ---- 4. Coverage / cross-source --------------------------------------
    "v_source_coverage": """
        CREATE OR REPLACE VIEW v_source_coverage AS
        SELECT
            source_issn_l             AS issn_l,
            count(*)                  AS works,
            min(publication_year)     AS first_year,
            max(publication_year)     AS last_year,
            count(DISTINCT doi)       AS works_with_doi
        FROM fact_works
        WHERE source_issn_l IS NOT NULL
        GROUP BY source_issn_l
    """,
    # Join keys for matching the lake against the app DB / other sources.
    "v_work_keys": """
        CREATE OR REPLACE VIEW v_work_keys AS
        SELECT work_id, doi, source_issn_l AS issn_l, publication_year
        FROM fact_works
    """,
}

# For docs / UI: which views serve which analytical axis.
VIEWS_BY_AXIS: dict[str, tuple[str, ...]] = {
    "journal_scientometrics": ("v_journal_yearly", "v_journal_citation_trend"),
    "collaboration_networks": ("v_coauthor_pairs", "v_institution_collab"),
    "topic_trends": ("v_topic_yearly", "v_field_yearly"),
    "coverage_cross_source": ("v_source_coverage", "v_work_keys"),
}


def create_analysis_views(con) -> None:
    """(Re)create every analysis view on a DuckDB connection."""
    for ddl in ANALYSIS_VIEWS.values():
        con.execute(ddl)
