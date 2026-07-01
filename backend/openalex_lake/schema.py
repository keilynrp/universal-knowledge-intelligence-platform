"""DuckDB star schema for the OpenAlex lake.

One DDL, identical for the API-subset and the full-snapshot paths. Fact tables
are keyed by short OpenAlex ids (e.g. "W2755950973"); dimensions by their
natural canonical id (ISSN-L, ROR, ORCID) where available so cross-source joins
against the app's Postgres/SQLite are direct.

`_meta` carries the incremental-refresh watermark per source, enabling automated
periodic updates (pull only works updated since the last successful run).
"""

# Order matters only for readability; DuckDB has no FK enforcement here.
DDL_STATEMENTS: tuple[str, ...] = (
    # ---- fact tables ------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS fact_works (
        work_id           VARCHAR PRIMARY KEY,
        doi               VARCHAR,
        title             VARCHAR,
        publication_year  INTEGER,
        publication_date  DATE,
        type              VARCHAR,
        source_issn_l     VARCHAR,
        source_id         VARCHAR,
        cited_by_count    INTEGER,
        is_oa             BOOLEAN,
        oa_status         VARCHAR,
        primary_topic_id  VARCHAR,
        field_id          INTEGER,
        field             VARCHAR,
        domain            VARCHAR,
        referenced_count  INTEGER,
        updated_date      VARCHAR
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fact_work_counts_by_year (
        work_id        VARCHAR,
        year           INTEGER,
        cited_by_count INTEGER,
        PRIMARY KEY (work_id, year)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fact_authorship (
        work_id          VARCHAR,
        author_position  VARCHAR,
        author_id        VARCHAR,
        orcid            VARCHAR,
        institution_ror  VARCHAR,
        institution_id   VARCHAR,
        country_code     VARCHAR,
        PRIMARY KEY (work_id, author_id, institution_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fact_work_topic (
        work_id   VARCHAR,
        topic_id  VARCHAR,
        score     DOUBLE,
        is_primary BOOLEAN,
        PRIMARY KEY (work_id, topic_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fact_citation (
        work_id            VARCHAR,
        referenced_work_id VARCHAR,
        PRIMARY KEY (work_id, referenced_work_id)
    )
    """,
    # ---- dimensions (full from snapshot, or derived from works) -----------
    """
    CREATE TABLE IF NOT EXISTS dim_source (
        source_id     VARCHAR PRIMARY KEY,
        issn_l        VARCHAR,
        display_name  VARCHAR,
        host_org      VARCHAR,
        is_in_doaj    BOOLEAN,
        type          VARCHAR,
        country_code  VARCHAR
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS dim_institution (
        institution_id VARCHAR PRIMARY KEY,
        ror            VARCHAR,
        display_name   VARCHAR,
        country_code   VARCHAR,
        type           VARCHAR
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS dim_author (
        author_id     VARCHAR PRIMARY KEY,
        orcid         VARCHAR,
        display_name  VARCHAR
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS dim_topic (
        topic_id      VARCHAR PRIMARY KEY,
        display_name  VARCHAR,
        subfield      VARCHAR,
        field_id      INTEGER,
        field         VARCHAR,
        domain        VARCHAR
    )
    """,
    # ---- ops --------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS _meta (
        key   VARCHAR PRIMARY KEY,
        value VARCHAR
    )
    """,
)

# Tables that transform_work populates, in insert order. Used by the store to
# dedup/upsert generically.
FACT_TABLES = (
    "fact_works",
    "fact_work_counts_by_year",
    "fact_authorship",
    "fact_work_topic",
    "fact_citation",
)
DERIVED_DIM_TABLES = ("dim_author", "dim_institution", "dim_topic", "dim_source")

# Primary-key columns per table, for idempotent upserts.
PRIMARY_KEYS: dict[str, tuple[str, ...]] = {
    "fact_works": ("work_id",),
    "fact_work_counts_by_year": ("work_id", "year"),
    "fact_authorship": ("work_id", "author_id", "institution_id"),
    "fact_work_topic": ("work_id", "topic_id"),
    "fact_citation": ("work_id", "referenced_work_id"),
    "dim_source": ("source_id",),
    "dim_institution": ("institution_id",),
    "dim_author": ("author_id",),
    "dim_topic": ("topic_id",),
}
