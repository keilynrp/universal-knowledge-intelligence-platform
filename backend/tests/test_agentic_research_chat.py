import json

from backend import models
from backend.services.agentic_research_chat import AgenticChatRequest, AgenticResearchChatService


def _seed_entity(db_session):
    entity = models.RawEntity(
        domain="science",
        entity_type="publication",
        primary_label="Linked Data - The Story So Far",
        canonical_id="10.4018/jswis.2009081901",
        validation_status="validated",
        enrichment_status="completed",
        enrichment_source="wos",
        enrichment_citation_count=4551,
        enrichment_concepts="linked data; semantic web; knowledge graph",
        quality_score=0.91,
        source="wos",
    )
    db_session.add(entity)
    db_session.commit()
    return entity


def test_agentic_chat_service_returns_trace_without_active_llm(db_session):
    user = db_session.query(models.User).filter(models.User.role == "super_admin").first()
    _seed_entity(db_session)

    result = AgenticResearchChatService.ask(
        db=db_session,
        payload=AgenticChatRequest(
            question="Que patrones ocultos debo revisar antes del brief?",
            mode="auto",
            domain_id="science",
            persist_trace=True,
        ),
        current_user=user,
        org_id=None,
    )

    assert result["mode_used"] == "hybrid"
    assert result["trace"]["rag_used"] is True
    assert result["trace"]["nlq_used"] is True
    assert "scope_summary" in result["trace"]["context_blocks"]
    assert result["trace_id"] is not None

    saved = db_session.get(models.AnalysisContext, result["trace_id"])
    snapshot = json.loads(saved.context_snapshot)
    assert saved.label.startswith("agentic-chat:")
    assert snapshot["kind"] == "agentic_chat_trace"
    assert snapshot["scope"]["domain_id"] == "science"


def test_agentic_chat_endpoint_is_authenticated(client):
    response = client.post(
        "/agentic-chat/query",
        json={"question": "Que brechas tiene este portafolio?", "domain_id": "science"},
    )
    assert response.status_code == 401


def test_agentic_chat_endpoint_returns_scope_and_followups(client, auth_headers, db_session):
    _seed_entity(db_session)

    response = client.post(
        "/agentic-chat/query",
        headers=auth_headers,
        json={
            "question": "Que brechas tiene este portafolio?",
            "domain_id": "science",
            "mode": "auto",
            "persist_trace": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["scope"]["domain_id"] == "science"
    assert payload["trace_id"] is None
    assert payload["follow_up_questions"]
