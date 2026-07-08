import json

from backend import models
from backend.auth import create_access_token, hash_password


def test_catalog_portal_create_and_results_global_scope(client, auth_headers, db_session):
    db_session.add_all(
        [
            models.RawEntity(
                primary_label="Portal Record A",
                secondary_label="Alpha Author",
                canonical_id="10.1000/a",
                entity_type="publication",
                domain="science",
                validation_status="valid",
                enrichment_status="completed",
                enrichment_citation_count=32,
                quality_score=0.86,
                source="scientific_import",
                attributes_json=json.dumps({"journal": "Nature", "year": 2024}),
            ),
            models.RawEntity(
                primary_label="Portal Record B",
                secondary_label="Beta Author",
                canonical_id="10.1000/b",
                entity_type="publication",
                domain="science",
                validation_status="pending",
                enrichment_status="none",
                enrichment_citation_count=0,
                quality_score=0.41,
                source="demo",
                attributes_json=json.dumps({"journal": "Cell", "year": 2023}),
            ),
            models.RawEntity(
                primary_label="Out of Scope",
                entity_type="software",
                domain="default",
                validation_status="valid",
                enrichment_status="none",
                source="user",
            ),
        ]
    )
    db_session.commit()

    create_resp = client.post(
        "/catalogs",
        json={
            "title": "Science Catalog",
            "slug": "science-catalog",
            "description": "Portal for science entities",
            "domain_id": "science",
            "visibility": "private",
            "source_label": "Latest science import",
            "source_context": {"format": "wos_plaintext", "rows": 2},
            "ft_entity_type": "publication",
            "featured_facets": ["entity_type", "enrichment_status", "source"],
            "default_sort": "primary_label",
            "default_order": "asc",
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    portal = create_resp.json()
    assert portal["slug"] == "science-catalog"
    assert portal["domain_id"] == "science"
    assert portal["source_label"] == "Latest science import"
    assert portal["source_context"]["format"] == "wos_plaintext"
    assert portal["featured_facets"] == ["entity_type", "enrichment_status", "source", "journal_metric_signal"]

    summary_resp = client.get("/catalogs/science-catalog", headers=auth_headers)
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["summary"]["total_records"] == 2
    assert summary["summary"]["enriched_records"] == 1

    results_resp = client.get("/catalogs/science-catalog/results", headers=auth_headers)
    assert results_resp.status_code == 200, results_resp.text
    results = results_resp.json()
    assert results["total"] == 2
    assert [item["primary_label"] for item in results["items"]] == ["Portal Record A", "Portal Record B"]
    assert "enrichment_status" in results["facets"]

    record_id = results["items"][0]["id"]
    detail_resp = client.get(f"/catalogs/science-catalog/records/{record_id}", headers=auth_headers)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["primary_label"] == "Portal Record A"


def test_catalog_results_include_journal_metric_signal_facet(client, auth_headers, db_session):
    db_session.add_all(
        [
            models.RawEntity(
                primary_label="Ready Journal Work",
                entity_type="publication",
                domain="science",
                source="scientific_import",
                enrichment_issn_l="1234-5678",
            ),
            models.RawEntity(
                primary_label="Raw Journal Work",
                entity_type="publication",
                domain="science",
                source="scientific_import",
                enrichment_issn_l="8765-4321",
            ),
            models.JournalMetric(
                issn_l="1234-5678",
                normalized_impact_factor=1.2,
                nif_bayes=1.1,
            ),
            models.JournalMetric(
                issn_l="8765-4321",
                normalized_impact_factor=1.0,
                nif_bayes=None,
            ),
        ]
    )
    db_session.commit()

    create_resp = client.post(
        "/catalogs",
        json={
            "title": "Journal Signal Catalog",
            "slug": "journal-signal-catalog",
            "domain_id": "science",
            "visibility": "private",
            "featured_facets": ["entity_type", "journal_metric_signal"],
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 201, create_resp.text

    results_resp = client.get("/catalogs/journal-signal-catalog/results", headers=auth_headers)
    assert results_resp.status_code == 200, results_resp.text
    results = results_resp.json()
    assert results["facets"]["journal_metric_signal"] == [
        {"value": "nif_bayes_ready", "count": 1}
    ]

    filtered_resp = client.get(
        "/catalogs/journal-signal-catalog/results?ft_journal_metric_signal=nif_bayes_ready",
        headers=auth_headers,
    )
    assert filtered_resp.status_code == 200, filtered_resp.text
    filtered = filtered_resp.json()
    assert filtered["total"] == 1
    assert [item["primary_label"] for item in filtered["items"]] == ["Ready Journal Work"]


def test_catalog_portal_can_scope_to_exact_import_batch(client, auth_headers, db_session):
    batch_a = models.ImportBatch(
        domain_id="science",
        source_type="science_upload",
        file_name="a.ris",
        file_format="ris",
        source_label="Batch A",
        total_rows=1,
        entity_type_hint="publication",
    )
    batch_b = models.ImportBatch(
        domain_id="science",
        source_type="science_upload",
        file_name="b.ris",
        file_format="ris",
        source_label="Batch B",
        total_rows=1,
        entity_type_hint="publication",
    )
    db_session.add_all([batch_a, batch_b])
    db_session.flush()
    db_session.add_all(
        [
            models.RawEntity(
                primary_label="Batch Scoped Record",
                entity_type="publication",
                domain="science",
                source="science_upload",
                import_batch_id=batch_a.id,
                quality_score=0.91,
            ),
            models.RawEntity(
                primary_label="Same Domain Other Batch",
                entity_type="publication",
                domain="science",
                source="science_upload",
                import_batch_id=batch_b.id,
                quality_score=0.88,
            ),
        ]
    )
    db_session.commit()

    create_resp = client.post(
        "/catalogs",
        json={
            "title": "Exact Batch Portal",
            "slug": "exact-batch-portal",
            "domain_id": "science",
            "visibility": "private",
            "source_batch_id": batch_a.id,
            "featured_facets": ["entity_type", "source"],
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    portal = create_resp.json()
    assert portal["source_batch_id"] == batch_a.id

    results_resp = client.get("/catalogs/exact-batch-portal/results", headers=auth_headers)
    assert results_resp.status_code == 200, results_resp.text
    results = results_resp.json()
    assert results["total"] == 1
    assert [item["primary_label"] for item in results["items"]] == ["Batch Scoped Record"]

    candidates_resp = client.get("/catalogs/import-candidates", headers=auth_headers)
    assert candidates_resp.status_code == 200
    candidates = candidates_resp.json()
    assert any(candidate["kind"] == "batch" and candidate["batch_id"] == batch_a.id for candidate in candidates)


def test_catalog_portal_is_scoped_to_active_organization(client, db_session):
    admin = models.User(
        username="catalog_admin",
        password_hash=hash_password("catalog-pass-123"),
        role="admin",
        is_active=True,
    )
    outsider = models.User(
        username="catalog_outsider",
        password_hash=hash_password("catalog-pass-456"),
        role="admin",
        is_active=True,
    )
    db_session.add_all([admin, outsider])
    db_session.flush()

    org_a = models.Organization(name="Org A", slug="org-a-catalog", owner_id=admin.id, is_active=True)
    org_b = models.Organization(name="Org B", slug="org-b-catalog", owner_id=outsider.id, is_active=True)
    db_session.add_all([org_a, org_b])
    db_session.flush()

    db_session.add_all(
        [
            models.OrganizationMember(org_id=org_a.id, user_id=admin.id, role="admin"),
            models.OrganizationMember(org_id=org_b.id, user_id=outsider.id, role="admin"),
        ]
    )
    admin.org_id = org_a.id
    outsider.org_id = org_b.id
    db_session.flush()

    db_session.add_all(
        [
            models.RawEntity(primary_label="Org A Record", entity_type="publication", domain="science", org_id=org_a.id),
            models.RawEntity(primary_label="Org B Record", entity_type="publication", domain="science", org_id=org_b.id),
        ]
    )
    db_session.commit()

    admin_headers = {"Authorization": f"Bearer {create_access_token(subject=admin.username, role='admin')}"}
    outsider_headers = {"Authorization": f"Bearer {create_access_token(subject=outsider.username, role='admin')}"}

    create_resp = client.post(
        "/catalogs",
        json={
            "title": "Org A Portal",
            "slug": "org-a-portal",
            "domain_id": "science",
            "visibility": "private",
            "ft_entity_type": "publication",
        },
        headers=admin_headers,
    )
    assert create_resp.status_code == 201, create_resp.text

    owner_results = client.get("/catalogs/org-a-portal/results", headers=admin_headers)
    assert owner_results.status_code == 200
    assert owner_results.json()["total"] == 1
    assert owner_results.json()["items"][0]["primary_label"] == "Org A Record"

    outsider_results = client.get("/catalogs/org-a-portal/results", headers=outsider_headers)
    assert outsider_results.status_code == 404


def test_catalog_portal_update_persists_editable_fields(client, auth_headers, db_session):
    db_session.add(
        models.RawEntity(
            primary_label="Editable Record",
            entity_type="publication",
            domain="science",
            quality_score=0.75,
            source="scientific_import",
        )
    )
    db_session.commit()

    create_resp = client.post(
        "/catalogs",
        json={
            "title": "Editable Catalog",
            "slug": "editable-catalog",
            "domain_id": "science",
            "visibility": "private",
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 201, create_resp.text

    update_resp = client.put(
        "/catalogs/editable-catalog",
        json={
            "title": "Edited Catalog",
            "description": "Updated portal description",
            "visibility": "org",
            "source_label": "Manual pilot collection",
            "search": "Editable",
            "min_quality": 0.7,
        },
        headers=auth_headers,
    )
    assert update_resp.status_code == 200, update_resp.text
    updated = update_resp.json()
    assert updated["title"] == "Edited Catalog"
    assert updated["description"] == "Updated portal description"
    assert updated["visibility"] == "org"
    assert updated["source_label"] == "Manual pilot collection"
    assert updated["search"] == "Editable"
    assert updated["min_quality"] == 0.7


def test_public_catalog_portal_is_readable_without_auth(client, auth_headers, db_session):
    db_session.add(
        models.RawEntity(
            primary_label="Public Record",
            secondary_label="Open Author",
            canonical_id="10.1000/public",
            entity_type="publication",
            domain="science",
            validation_status="valid",
            enrichment_status="completed",
            enrichment_citation_count=14,
            quality_score=0.88,
            source="scientific_import",
            attributes_json=json.dumps({"journal": "Open Science", "year": 2025}),
        )
    )
    db_session.commit()

    create_resp = client.post(
        "/catalogs",
        json={
            "title": "Public Science Catalog",
            "slug": "public-science-catalog",
            "domain_id": "science",
            "visibility": "public",
            "ft_entity_type": "publication",
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 201, create_resp.text

    summary_resp = client.get("/catalogs/public-science-catalog")
    assert summary_resp.status_code == 200, summary_resp.text
    assert summary_resp.json()["visibility"] == "public"

    results_resp = client.get("/catalogs/public-science-catalog/results")
    assert results_resp.status_code == 200, results_resp.text
    results = results_resp.json()
    assert results["total"] == 1
    assert results["items"][0]["primary_label"] == "Public Record"

    record_id = results["items"][0]["id"]
    detail_resp = client.get(f"/catalogs/public-science-catalog/records/{record_id}")
    assert detail_resp.status_code == 200, detail_resp.text
    assert detail_resp.json()["canonical_id"] == "10.1000/public"


def test_catalog_portal_delete_removes_only_portal(client, auth_headers, db_session):
    record = models.RawEntity(
        primary_label="Persistent Imported Record",
        entity_type="publication",
        domain="science",
        source="scientific_import",
    )
    db_session.add(record)
    db_session.commit()

    create_resp = client.post(
        "/catalogs",
        json={
            "title": "Disposable Catalog",
            "slug": "disposable-catalog",
            "domain_id": "science",
            "visibility": "private",
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 201, create_resp.text

    delete_resp = client.delete("/catalogs/disposable-catalog", headers=auth_headers)
    assert delete_resp.status_code == 204, delete_resp.text

    portal = db_session.query(models.CatalogPortal).filter(models.CatalogPortal.slug == "disposable-catalog").first()
    assert portal is None

    persisted_record = db_session.query(models.RawEntity).filter(models.RawEntity.id == record.id).first()
    assert persisted_record is not None
    assert persisted_record.primary_label == "Persistent Imported Record"


def test_catalog_import_candidates_are_grouped_from_existing_records(client, auth_headers, db_session):
    db_session.add_all(
        [
            models.RawEntity(
                primary_label="Grouped Record A",
                entity_type="publication",
                domain="science",
                source="scientific_import",
                quality_score=0.8,
            ),
            models.RawEntity(
                primary_label="Grouped Record B",
                entity_type="publication",
                domain="science",
                source="scientific_import",
                quality_score=0.6,
            ),
            models.RawEntity(
                primary_label="Grouped Record C",
                entity_type="dataset",
                domain="science",
                source="user",
                quality_score=0.4,
            ),
        ]
    )
    db_session.commit()

    resp = client.get("/catalogs/import-candidates", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert len(payload) >= 2

    top = payload[0]
    assert top["domain_id"] == "science"
    assert top["source"] == "scientific_import"
    assert top["entity_type"] == "publication"
    assert top["total_records"] == 2
    assert top["ft_source"] == "scientific_import"
    assert top["ft_entity_type"] == "publication"


def test_catalog_results_min_quality_computes_missing_scores(client, auth_headers, db_session):
    high = models.RawEntity(
        primary_label="Portal High Missing Score",
        secondary_label="Research Office",
        canonical_id="AUTH:portal-high",
        entity_type="organization",
        domain="science",
        enrichment_status="completed",
        enrichment_doi="10.1000/portal-high",
        quality_score=None,
    )
    low = models.RawEntity(
        primary_label="Portal Low Missing Score",
        entity_type="organization",
        domain="science",
        enrichment_status="none",
        quality_score=None,
    )
    db_session.add_all([high, low])
    db_session.flush()
    db_session.add(
        models.AuthorityRecord(
            field_name="primary_label",
            original_value="Portal High Missing Score",
            authority_source="ror",
            authority_id="https://ror.org/portal-high",
            canonical_label="Portal High Missing Score",
            confidence=1.0,
            status="confirmed",
        )
    )
    db_session.commit()

    create_resp = client.post(
        "/catalogs",
        json={
            "title": "Quality Filter Catalog",
            "slug": "quality-filter-catalog",
            "domain_id": "science",
            "visibility": "private",
            "default_sort": "primary_label",
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 201, create_resp.text

    results_resp = client.get("/catalogs/quality-filter-catalog/results?min_quality=0.7", headers=auth_headers)
    assert results_resp.status_code == 200, results_resp.text
    labels = {record["primary_label"] for record in results_resp.json()["items"]}
    assert "Portal High Missing Score" in labels
    assert "Portal Low Missing Score" not in labels
    high_result = next(record for record in results_resp.json()["items"] if record["primary_label"] == "Portal High Missing Score")
    assert high_result["quality_score"] >= 0.7


def test_catalog_results_max_quality_returns_only_low_scored(client, auth_headers, db_session):
    """max_quality expresses the 'Menor a 30%' bucket as quality_score < 0.3."""
    high = models.RawEntity(
        primary_label="Portal High Score",
        entity_type="organization",
        domain="science",
        enrichment_status="completed",
        quality_score=0.9,
    )
    low = models.RawEntity(
        primary_label="Portal Low Score",
        entity_type="organization",
        domain="science",
        enrichment_status="none",
        quality_score=0.1,
    )
    boundary = models.RawEntity(
        primary_label="Portal Boundary Score",
        entity_type="organization",
        domain="science",
        enrichment_status="none",
        quality_score=0.3,
    )
    db_session.add_all([high, low, boundary])
    db_session.commit()

    create_resp = client.post(
        "/catalogs",
        json={
            "title": "Max Quality Catalog",
            "slug": "max-quality-catalog",
            "domain_id": "science",
            "visibility": "private",
            "default_sort": "primary_label",
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 201, create_resp.text

    results_resp = client.get(
        "/catalogs/max-quality-catalog/results?max_quality=0.3", headers=auth_headers
    )
    assert results_resp.status_code == 200, results_resp.text
    labels = {record["primary_label"] for record in results_resp.json()["items"]}
    assert "Portal Low Score" in labels
    # 0.3 itself belongs to the "30%+" bucket, not "under 30%".
    assert "Portal Boundary Score" not in labels
    assert "Portal High Score" not in labels
