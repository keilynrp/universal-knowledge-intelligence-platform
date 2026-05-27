import json

from backend import models


def _record(title: str, authors: list[dict], *, concepts: str = "open science", citations: int = 0):
    return models.RawEntity(
        primary_label=title,
        secondary_label=", ".join(author["author_name"] for author in authors),
        domain="topic_test",
        attributes_json=json.dumps({
            "abstract": f"This paper studies {concepts} and collaborative knowledge systems.",
            "author_affiliations": authors,
            "keywords": [concepts, "collaboration"],
        }),
        normalized_json=json.dumps({}),
        enrichment_status="completed",
        enrichment_source="openalex",
        enrichment_concepts=concepts,
        enrichment_citation_count=citations,
    )


def test_researchers_by_topic_ranks_authors_from_ingested_records(client, auth_headers, db_session):
    db_session.add_all([
        _record(
            "Open science governance",
            [
                {"author_name": "Ada Rivera", "author_orcid": "0000-0001"},
                {"author_name": "Ben Soto", "author_orcid": "0000-0002"},
            ],
            citations=25,
        ),
        _record(
            "Open science repositories",
            [
                {"author_name": "Ada Rivera", "author_orcid": "0000-0001"},
                {"author_name": "Clara Vega", "author_orcid": "0000-0003"},
            ],
            citations=10,
        ),
        _record(
            "Unrelated chemistry note",
            [{"author_name": "Dina Paz", "author_orcid": "0000-0004"}],
            concepts="chemistry",
            citations=100,
        ),
    ])
    db_session.commit()

    response = client.get(
        "/analytics/researchers-by-topic",
        params={"domain_id": "topic_test", "topic": "open science"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["topic"] == "open science"
    assert payload["records_analyzed"] == 2
    assert payload["researchers"][0]["name"] == "Ada Rivera"
    assert payload["researchers"][0]["records_count"] == 2
    assert payload["researchers"][0]["topic_score"] == 100


def test_topic_researcher_graph_links_topic_and_coauthors(client, auth_headers, db_session):
    db_session.add_all([
        _record(
            "Open science governance",
            [
                {"author_name": "Ada Rivera", "author_orcid": "0000-0001"},
                {"author_name": "Ben Soto", "author_orcid": "0000-0002"},
            ],
            citations=25,
        ),
        _record(
            "Open science repositories",
            [
                {"author_name": "Ada Rivera", "author_orcid": "0000-0001"},
                {"author_name": "Ben Soto", "author_orcid": "0000-0002"},
            ],
            citations=10,
        ),
    ])
    db_session.commit()

    response = client.get(
        "/analytics/topic-researcher-graph",
        params={"domain_id": "topic_test", "topic": "open science", "min_weight": 2},
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert any(node["type"] == "topic" for node in payload["nodes"])
    assert any(edge["type"] == "works_on_topic" for edge in payload["edges"])
    assert any(edge["type"] == "coauthor_with" and edge["weight"] == 2 for edge in payload["edges"])


def test_researcher_topic_tools_are_registered_for_rag_assistant(db_session):
    import backend.tool_registry as tool_registry

    tool_registry._registry = None
    registry = tool_registry.get_registry()
    names = {tool["name"] for tool in registry.list_tools()}

    assert "find_researchers_by_topic" in names
    assert "get_topic_researcher_graph" in names
