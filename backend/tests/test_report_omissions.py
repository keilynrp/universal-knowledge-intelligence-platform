"""Omission reporting (unify-report-format-coverage, phase 4).

A section a binary format cannot render must be reported, not silently dropped:
the export still succeeds and names the omitted sections in a response header,
and GET /reports/sections advertises per-format availability so the caller can
see it before exporting. agentic_trace is the motivating case — long free text
that Excel and PPTX declare unsupported.
"""


def test_excel_export_reports_omitted_agentic_trace(client, auth_headers):
    payload = {"domain_id": "default", "sections": ["entity_stats", "agentic_trace"]}
    resp = client.post("/exports/excel", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    omitted = resp.headers.get("X-UKIP-Report-Omitted-Sections", "")
    assert "agentic_trace" in omitted
    assert "entity_stats" not in omitted        # entity_stats is supported


def test_excel_export_no_header_when_all_supported(client, auth_headers):
    payload = {"domain_id": "default", "sections": ["entity_stats", "enrichment_coverage"]}
    resp = client.post("/exports/excel", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    assert "X-UKIP-Report-Omitted-Sections" not in resp.headers


def test_pptx_export_reports_omitted_agentic_trace(client, auth_headers):
    payload = {"domain_id": "default", "sections": ["entity_stats", "agentic_trace"]}
    resp = client.post("/exports/pptx", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    assert "agentic_trace" in resp.headers.get("X-UKIP-Report-Omitted-Sections", "")


def test_reports_sections_lists_per_format_availability(client, auth_headers):
    resp = client.get("/reports/sections", headers=auth_headers)
    assert resp.status_code == 200
    by_id = {row["id"]: row for row in resp.json()}

    # every row carries a per-format availability map over the four formats
    assert set(by_id["entity_stats"]["formats"]) == {"html", "pdf", "excel", "pptx"}
    assert by_id["entity_stats"]["formats"]["excel"] is True

    # agentic_trace is HTML/PDF only — declared unsupported for the binary formats
    at = by_id["agentic_trace"]["formats"]
    assert at["html"] is True and at["pdf"] is True
    assert at["excel"] is False and at["pptx"] is False
