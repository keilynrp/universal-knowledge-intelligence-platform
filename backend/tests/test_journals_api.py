from backend.schemas import JournalMetricResponse, EntityAttributesDict


def test_journal_metric_response_shape():
    r = JournalMetricResponse(
        issn_l="0028-0836", display_name="Nat", source_id="S77",
        two_yr_mean_citedness=17.4, h_index=1200, normalized_impact_factor=1.5,
        nif_field="Genetics", apc_usd=11690, apc_currency="USD", apc_source="openalex",
        is_in_doaj=False, if_metric_kind="openalex_2yr_mean_citedness", nif_updated_at=None,
    )
    assert r.apc_usd == 11690 and r.nif_field == "Genetics"


def test_issn_l_documented_in_attributes_contract():
    assert "issn_l" in EntityAttributesDict.__annotations__
