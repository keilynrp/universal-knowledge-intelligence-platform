"""Unit tests for the OpenAlex lake transform + DuckDB store."""
from backend.openalex_lake.config import LakeScope, default_scope
from backend.openalex_lake.store import LakeStore, RowBuffer, dedup_by_pk
from backend.openalex_lake.transform import transform_work

SAMPLE_WORK = {
    "id": "https://openalex.org/W2755950973",
    "doi": "https://doi.org/10.1234/ABC.def",
    "title": "The Astropy Project",
    "publication_year": 2018,
    "publication_date": "2018-09-01",
    "type": "article",
    "cited_by_count": 42,
    "updated_date": "2025-06-01",
    "primary_location": {
        "source": {
            "id": "https://openalex.org/S137773608",
            "issn_l": "0028-0836",
            "display_name": "Nature",
            "host_organization_name": "Springer Nature",
            "is_in_doaj": False,
            "type": "journal",
        }
    },
    "open_access": {"is_oa": True, "oa_status": "green"},
    "primary_topic": {
        "id": "https://openalex.org/T10001",
        "display_name": "Astronomy",
        "field": {"id": "https://openalex.org/fields/31", "display_name": "Physics and Astronomy"},
        "subfield": {"display_name": "Astronomy and Astrophysics"},
        "domain": {"display_name": "Physical Sciences"},
    },
    "topics": [
        {
            "id": "https://openalex.org/T10001",
            "display_name": "Astronomy",
            "score": 0.99,
            "field": {"id": "https://openalex.org/fields/31", "display_name": "Physics and Astronomy"},
            "subfield": {"display_name": "Astronomy and Astrophysics"},
            "domain": {"display_name": "Physical Sciences"},
        },
        {
            "id": "https://openalex.org/T11000",
            "display_name": "Software",
            "score": 0.42,
            "field": {"id": "https://openalex.org/fields/17", "display_name": "Computer Science"},
        },
    ],
    "counts_by_year": [
        {"year": 2020, "cited_by_count": 10},
        {"year": 2019, "cited_by_count": 8},
    ],
    "authorships": [
        {
            "author_position": "first",
            "author": {
                "id": "https://openalex.org/A5000",
                "orcid": "https://orcid.org/0000-0001-0002-0003",
                "display_name": "A. Astronomer",
            },
            "institutions": [
                {
                    "id": "https://openalex.org/I200",
                    "ror": "https://ror.org/05gq02987",
                    "display_name": "Caltech",
                    "country_code": "US",
                    "type": "education",
                }
            ],
        }
    ],
    "referenced_works": [
        "https://openalex.org/W111",
        "https://openalex.org/W222",
    ],
}


def test_transform_core_fact_fields():
    rows = transform_work(SAMPLE_WORK)
    work = rows["fact_works"][0]
    assert work["work_id"] == "W2755950973"
    assert work["doi"] == "10.1234/abc.def"  # bare + lowercased
    assert work["publication_year"] == 2018
    assert work["source_issn_l"] == "0028-0836"
    assert work["source_id"] == "S137773608"
    assert work["field_id"] == 31 and work["field"] == "Physics and Astronomy"
    assert work["domain"] == "Physical Sciences"
    assert work["is_oa"] is True
    assert work["referenced_count"] == 2


def test_transform_counts_authorship_topics():
    rows = transform_work(SAMPLE_WORK)
    assert {r["year"] for r in rows["fact_work_counts_by_year"]} == {2019, 2020}

    auth = rows["fact_authorship"][0]
    assert auth["author_id"] == "A5000"
    assert auth["orcid"] == "0000-0001-0002-0003"  # URL prefix stripped
    assert auth["institution_ror"] == "05gq02987"
    assert auth["country_code"] == "US"

    topics = {t["topic_id"]: t for t in rows["fact_work_topic"]}
    assert topics["T10001"]["is_primary"] is True
    assert topics["T11000"]["is_primary"] is False


def test_transform_derived_dims():
    rows = transform_work(SAMPLE_WORK)
    assert rows["dim_author"][0]["orcid"] == "0000-0001-0002-0003"
    assert rows["dim_institution"][0]["ror"] == "05gq02987"
    assert rows["dim_source"][0]["issn_l"] == "0028-0836"
    field_ids = {t["field_id"] for t in rows["dim_topic"]}
    assert field_ids == {31, 17}


def test_citations_are_opt_in():
    assert transform_work(SAMPLE_WORK)["fact_citation"] == []
    with_refs = transform_work(SAMPLE_WORK, include_citations=True)["fact_citation"]
    assert {r["referenced_work_id"] for r in with_refs} == {"W111", "W222"}


def test_transform_tolerates_sparse_work():
    rows = transform_work({"id": "https://openalex.org/W9"})
    assert rows["fact_works"][0]["work_id"] == "W9"
    assert rows["fact_authorship"] == [] and rows["dim_source"] == []


def test_transform_skips_work_without_id():
    rows = transform_work({"title": "orphan"})
    assert all(v == [] for v in rows.values())


def test_store_roundtrip_and_idempotency():
    with LakeStore(":memory:") as store:
        rows = transform_work(SAMPLE_WORK, include_citations=True)
        store.ingest_work_rows(rows)
        assert store.count("fact_works") == 1
        assert store.count("fact_work_counts_by_year") == 2
        assert store.count("fact_citation") == 2
        assert store.count("dim_topic") == 2

        # Re-ingesting the same work must not duplicate rows.
        store.ingest_work_rows(rows)
        assert store.count("fact_works") == 1
        assert store.count("fact_work_counts_by_year") == 2
        assert store.count("dim_topic") == 2

        # Cross-source key is queryable.
        issn = store.con.execute(
            "SELECT source_issn_l FROM fact_works WHERE work_id = 'W2755950973'"
        ).fetchone()[0]
        assert issn == "0028-0836"


def test_store_watermark():
    with LakeStore(":memory:") as store:
        assert store.get_watermark("works") is None
        store.set_watermark("works", "2025-06-30")
        assert store.get_watermark("works") == "2025-06-30"
        store.set_watermark("works", "2025-07-01")
        assert store.get_watermark("works") == "2025-07-01"


def _work_with_author(work_id, author_id):
    return {
        "id": f"https://openalex.org/{work_id}",
        "authorships": [{
            "author": {"id": f"https://openalex.org/{author_id}", "display_name": author_id},
            "institutions": [{"id": "https://openalex.org/I1"}],
        }],
    }


def test_row_buffer_auto_flushes_at_threshold_and_dedups_dims():
    with LakeStore(":memory:") as store:
        buf = RowBuffer(store, flush_every=2)
        # Two works sharing author A1 -> auto-flush after the 2nd.
        buf.add_work_rows(transform_work(_work_with_author("W1", "A1")))
        buf.add_work_rows(transform_work(_work_with_author("W2", "A1")))
        assert store.count("fact_works") == 2       # flushed
        assert store.count("dim_author") == 1       # A1 deduped within the window
        # A third work stays buffered until flush().
        buf.add_work_rows(transform_work(_work_with_author("W3", "A2")))
        assert store.count("fact_works") == 2
        buf.flush()
        assert store.count("fact_works") == 3
        assert store.count("dim_author") == 2


def test_dedup_by_pk_keeps_last_write():
    rows = [{"author_id": "A1", "display_name": "old"}, {"author_id": "A1", "display_name": "new"}]
    assert dedup_by_pk("dim_author", rows) == [{"author_id": "A1", "display_name": "new"}]


def test_default_scope_is_bounded_after_issns():
    scope = default_scope()
    assert scope.year_from == 2010 and scope.year_to == 2025
    assert scope.include_citations is False
    assert not scope.is_bounded()  # no issns yet
    scope2 = scope.with_issns(["0028-0836", "0028-0836", "", "1476-4687"])
    assert scope2.issn_l == ("0028-0836", "1476-4687")  # dedup + drop empty
    assert scope2.is_bounded()
    assert isinstance(scope2, LakeScope)
