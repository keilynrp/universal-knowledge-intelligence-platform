from backend import schemas
from backend.models import JournalMetric, RawEntity
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


def test_journal_metric_signal_facet_and_filter(db_session):
    db_session.add_all(
        [
            RawEntity(primary_label="ready", enrichment_issn_l="1111-1111"),
            RawEntity(primary_label="raw", enrichment_issn_l="2222-2222"),
            JournalMetric(
                issn_l="1111-1111",
                normalized_impact_factor=1.2,
                nif_bayes=1.1,
            ),
            JournalMetric(
                issn_l="2222-2222",
                normalized_impact_factor=1.0,
                nif_bayes=None,
            ),
        ]
    )
    db_session.commit()

    facets = EntityService.get_facets(db_session, "journal_metric_signal")
    assert facets["journal_metric_signal"] == [
        {"value": "nif_bayes_ready", "count": 1}
    ]

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
        ft_work_type=None,
        ft_journal_metric_signal="nif_bayes_ready",
    )
    assert total == 1
    assert [row.primary_label for row in rows] == ["ready"]


def test_attach_journal_metrics_surfaces_signal_per_record(db_session):
    db_session.add_all(
        [
            RawEntity(primary_label="ready", enrichment_issn_l="1111-1111"),
            RawEntity(primary_label="raw", enrichment_issn_l="2222-2222"),
            RawEntity(primary_label="orphan", enrichment_issn_l=None),
            JournalMetric(
                issn_l="1111-1111",
                display_name="Nature",
                normalized_impact_factor=2.703,
                nif_bayes=3.247,
                nif_ci_low=3.23,
                nif_ci_high=3.26,
            ),
            JournalMetric(
                issn_l="2222-2222",
                display_name="Some Journal",
                normalized_impact_factor=1.0,
                nif_bayes=None,
            ),
        ]
    )
    db_session.commit()

    entities = (
        db_session.query(RawEntity).order_by(RawEntity.primary_label.asc()).all()
    )
    EntityService.attach_journal_metrics(db_session, entities, org_id=None)
    by_label = {
        e.primary_label: schemas.Entity.model_validate(e).model_dump()
        for e in entities
    }

    ready = by_label["ready"]
    assert ready["journal_nif_bayes_ready"] is True
    assert ready["enrichment_issn_l"] == "1111-1111"
    assert ready["journal_display_name"] == "Nature"
    assert ready["journal_nif"] == 2.703
    assert ready["journal_nif_bayes"] == 3.247
    assert ready["journal_nif_ci_low"] == 3.23
    assert ready["journal_nif_ci_high"] == 3.26

    # NIF present but no Bayes → not "ready"
    assert by_label["raw"]["journal_nif_bayes_ready"] is False
    assert by_label["raw"]["journal_nif"] == 1.0
    assert by_label["raw"]["journal_nif_bayes"] is None

    # No linked journal at all
    assert by_label["orphan"]["journal_nif_bayes_ready"] is False
    assert by_label["orphan"]["journal_display_name"] is None
