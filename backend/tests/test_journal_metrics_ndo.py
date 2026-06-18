from backend.schemas_enrichment import EnrichedRecord, JournalMetrics


def test_enriched_record_carries_journal_metrics():
    rec = EnrichedRecord(
        title="X",
        journal=JournalMetrics(
            issn_l="1111-2222",
            source_id="S99",
            two_yr_mean_citedness=4.1,
            apc_usd=2000,
        ),
    )
    assert rec.journal.issn_l == "1111-2222"
    assert rec.journal.normalized_impact_factor is None


def test_journal_defaults_none_when_absent():
    assert EnrichedRecord(title="Y").journal is None
