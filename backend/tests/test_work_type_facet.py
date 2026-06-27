from backend.models import RawEntity
from backend.services.entity_service import EntityService


def _seed(db, wt, n=1):
    for _ in range(n):
        db.add(RawEntity(primary_label="x", enrichment_work_type=wt))


def test_facets_fold_into_codes_with_nulls(db_session):
    _seed(db_session, "book", 2)
    _seed(db_session, "monograph", 1)
    _seed(db_session, "article", 1)
    _seed(db_session, "standard", 1)
    _seed(db_session, None, 2)
    db_session.commit()
    facets = EntityService.get_facets(db_session, "work_type")
    buckets = {d["value"]: d["count"] for d in facets["work_type"]}
    assert buckets["book"] == 3 and buckets["article"] == 1
    assert buckets["other"] == 1 and buckets["unclassified"] == 2


def test_list_filter_by_work_type_code(db_session):
    _seed(db_session, "book")
    _seed(db_session, "monograph")
    _seed(db_session, "article")
    _seed(db_session, None)
    db_session.commit()
    total, rows = EntityService.get_list(
        db_session,
        skip=0,
        limit=100,
        search=None,
        sort_by="id",
        order="asc",
        min_quality=None,
        ft_entity_type=None,
        ft_domain=None,
        ft_validation_status=None,
        ft_enrichment_status=None,
        ft_source=None,
        concept=None,
        ft_work_type="book",
    )
    assert total == 2

    total_u, rows_u = EntityService.get_list(
        db_session,
        skip=0,
        limit=100,
        search=None,
        sort_by="id",
        order="asc",
        min_quality=None,
        ft_entity_type=None,
        ft_domain=None,
        ft_validation_status=None,
        ft_enrichment_status=None,
        ft_source=None,
        concept=None,
        ft_work_type="unclassified",
    )
    assert total_u == 1
