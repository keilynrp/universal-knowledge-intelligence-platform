"""Tests for OpenAlex import adapter fixes."""
import json

import pytest

from backend.importers.scientific.openalex_adapter import (
    OpenAlexJSONImportAdapter,
    _extract_concepts,
    _reconstruct_abstract,
    _strip_raw_record,
    _parse_works,
    _peek_first_work,
)


def _make_work(**overrides):
    """Minimal OpenAlex work fixture."""
    base = {
        "id": "https://openalex.org/W1234567890",
        "doi": "https://doi.org/10.1234/test.2024",
        "display_name": "Test Publication Title",
        "publication_year": 2024,
        "type": "journal-article",
        "cited_by_count": 42,
        "authorships": [
            {
                "author": {"display_name": "Alice Smith", "id": "https://openalex.org/A1", "orcid": "https://orcid.org/0000-0001-0000-0001"},
                "institutions": [{"display_name": "MIT", "country_code": "US", "id": "https://openalex.org/I1"}],
            }
        ],
        "primary_location": {
            "source": {"display_name": "Nature", "host_organization_name": "Springer Nature"},
        },
        "concepts": [
            {"display_name": "Machine Learning", "score": 0.9},
            {"display_name": "Noise", "score": 0.1},
        ],
    }
    base.update(overrides)
    return base


# ── Abstract reconstruction ──────────────────────────────────────────────────


class TestReconstructAbstract:
    def test_plain_abstract_passthrough(self):
        work = {"abstract": "A plain abstract."}
        assert _reconstruct_abstract(work) == "A plain abstract."

    def test_inverted_index_reconstruction(self):
        work = {
            "abstract_inverted_index": {
                "Deep": [0],
                "learning": [1],
                "is": [2],
                "powerful": [3],
            }
        }
        assert _reconstruct_abstract(work) == "Deep learning is powerful"

    def test_inverted_index_with_repeated_words(self):
        work = {
            "abstract_inverted_index": {
                "the": [0, 3],
                "cat": [1],
                "chased": [2],
                "mouse": [4],
            }
        }
        assert _reconstruct_abstract(work) == "the cat chased the mouse"

    def test_no_abstract_at_all(self):
        assert _reconstruct_abstract({}) is None

    def test_empty_inverted_index(self):
        work = {"abstract_inverted_index": {}}
        assert _reconstruct_abstract(work) is None

    def test_plain_abstract_preferred_over_index(self):
        work = {
            "abstract": "Preferred text",
            "abstract_inverted_index": {"Other": [0]},
        }
        assert _reconstruct_abstract(work) == "Preferred text"

    def test_invalid_index_values_skipped(self):
        work = {
            "abstract_inverted_index": {
                "valid": [0],
                "skipped": "not-a-list",
            }
        }
        result = _reconstruct_abstract(work)
        assert result == "valid"


# ── Concept extraction ────────────────────────────────────────────────────────


class TestExtractConcepts:
    def test_concepts_field_with_score_filter(self):
        work = {
            "concepts": [
                {"display_name": "AI", "score": 0.9},
                {"display_name": "Noise", "score": 0.1},
            ]
        }
        result = _extract_concepts(work)
        assert "AI" in result
        assert "Noise" not in result

    def test_topics_field_included(self):
        work = {
            "concepts": [],
            "topics": [{"display_name": "Genomics", "score": 0.8}],
        }
        result = _extract_concepts(work)
        assert "Genomics" in result

    def test_keywords_field_no_score_filter(self):
        work = {
            "concepts": [],
            "keywords": [{"display_name": "CRISPR"}],
        }
        result = _extract_concepts(work)
        assert "CRISPR" in result

    def test_keywords_as_plain_strings(self):
        work = {"keywords": ["alpha", "beta"]}
        result = _extract_concepts(work)
        assert result == ["alpha", "beta"]

    def test_deduplication_across_fields(self):
        work = {
            "concepts": [{"display_name": "AI", "score": 0.9}],
            "topics": [{"display_name": "ai", "score": 0.8}],
            "keywords": [{"display_name": "AI"}],
        }
        result = _extract_concepts(work)
        assert len(result) == 1
        assert result[0] == "AI"

    def test_empty_fields(self):
        assert _extract_concepts({}) == []

    def test_threshold_boundary(self):
        work = {
            "concepts": [
                {"display_name": "Exact", "score": 0.4},
                {"display_name": "Below", "score": 0.39},
            ]
        }
        result = _extract_concepts(work)
        assert "Exact" in result
        assert "Below" not in result


# ── Raw record stripping ─────────────────────────────────────────────────────


class TestStripRawRecord:
    def test_heavy_fields_removed(self):
        work = {
            "id": "https://openalex.org/W1",
            "title": "Test",
            "abstract_inverted_index": {"big": [0]},
            "referenced_works": ["W2", "W3"],
            "related_works": ["W4"],
            "ngrams_url": "https://...",
            "counts_by_year": [{"year": 2024}],
        }
        stripped = _strip_raw_record(work)
        assert "id" in stripped
        assert "title" in stripped
        assert "abstract_inverted_index" not in stripped
        assert "referenced_works" not in stripped
        assert "related_works" not in stripped
        assert "ngrams_url" not in stripped
        assert "counts_by_year" not in stripped

    def test_does_not_mutate_original(self):
        work = {"id": "W1", "abstract_inverted_index": {"x": [0]}}
        _strip_raw_record(work)
        assert "abstract_inverted_index" in work


# ── JSONL support ─────────────────────────────────────────────────────────────


class TestJSONLSupport:
    def test_can_parse_jsonl(self):
        adapter = OpenAlexJSONImportAdapter()
        lines = [
            json.dumps(_make_work(id="https://openalex.org/W1")),
            json.dumps(_make_work(id="https://openalex.org/W2")),
        ]
        content = "\n".join(lines)
        assert adapter.can_parse("export.jsonl", content) is True

    def test_parse_jsonl_multiple_works(self):
        adapter = OpenAlexJSONImportAdapter()
        lines = [
            json.dumps(_make_work(display_name="Paper A")),
            "",
            json.dumps(_make_work(display_name="Paper B")),
        ]
        content = "\n".join(lines)
        result = adapter.parse("export.jsonl", content)
        assert result.total_rows == 2
        assert result.records[0].title == "Paper A"
        assert result.records[1].title == "Paper B"

    def test_jsonl_skips_invalid_lines(self):
        content = json.dumps(_make_work()) + "\nNOT JSON\n" + json.dumps(_make_work())
        works = _parse_works("test.jsonl", content)
        assert len(works) == 2

    def test_peek_first_work_jsonl(self):
        content = json.dumps(_make_work(display_name="First")) + "\n" + json.dumps(_make_work(display_name="Second"))
        first = _peek_first_work("test.jsonl", content)
        assert first["display_name"] == "First"

    def test_peek_empty_jsonl(self):
        assert _peek_first_work("test.jsonl", "\n\n") is None

    def test_can_parse_rejects_non_openalex_jsonl(self):
        adapter = OpenAlexJSONImportAdapter()
        content = json.dumps({"id": "not-openalex", "name": "test"})
        assert adapter.can_parse("data.jsonl", content) is False


# ── Full adapter integration ─────────────────────────────────────────────────


class TestOpenAlexAdapter:
    def test_can_parse_json_with_results_wrapper(self):
        adapter = OpenAlexJSONImportAdapter()
        content = json.dumps({"results": [_make_work()]})
        assert adapter.can_parse("works.json", content) is True

    def test_can_parse_json_single_work(self):
        adapter = OpenAlexJSONImportAdapter()
        content = json.dumps(_make_work())
        assert adapter.can_parse("work.json", content) is True

    def test_can_parse_json_array(self):
        adapter = OpenAlexJSONImportAdapter()
        content = json.dumps([_make_work()])
        assert adapter.can_parse("works.json", content) is True

    def test_rejects_non_json(self):
        adapter = OpenAlexJSONImportAdapter()
        assert adapter.can_parse("data.csv", "a,b,c") is False

    def test_rejects_non_openalex_json(self):
        adapter = OpenAlexJSONImportAdapter()
        content = json.dumps({"id": "scopus:123", "title": "test"})
        assert adapter.can_parse("data.json", content) is False

    def test_parse_extracts_all_fields(self):
        adapter = OpenAlexJSONImportAdapter()
        work = _make_work(
            abstract_inverted_index={"Hello": [0], "world": [1]},
        )
        content = json.dumps({"results": [work]})
        result = adapter.parse("works.json", content)

        assert result.total_rows == 1
        pub = result.records[0]
        assert pub.title == "Test Publication Title"
        assert pub.doi == "10.1234/test.2024"
        assert pub.year == 2024
        assert pub.citation_count == 42
        assert pub.abstract == "Hello world"
        assert pub.source_title == "Nature"
        assert pub.publisher == "Springer Nature"
        assert len(pub.authors) == 1
        assert pub.authors[0].name == "Alice Smith"
        assert len(pub.affiliations) == 1
        assert pub.affiliations[0].name == "MIT"
        assert "Machine Learning" in pub.concepts
        assert "Noise" not in pub.concepts

    def test_raw_record_stripped_of_heavy_fields(self):
        adapter = OpenAlexJSONImportAdapter()
        work = _make_work(
            abstract_inverted_index={"x": [0]},
            referenced_works=["W1", "W2"],
            related_works=["W3"],
        )
        content = json.dumps([work])
        result = adapter.parse("works.json", content)
        raw = result.records[0].raw_record
        assert "abstract_inverted_index" not in raw
        assert "referenced_works" not in raw
        assert "id" in raw

    def test_to_entity_kwargs_includes_abstract(self):
        adapter = OpenAlexJSONImportAdapter()
        work = _make_work(
            abstract_inverted_index={"Reconstructed": [0], "abstract": [1]},
        )
        content = json.dumps([work])
        result = adapter.parse("works.json", content)
        entity_data = result.records[0].to_entity_kwargs()
        attrs = json.loads(entity_data.get("attributes_json", "{}"))
        assert entity_data.get("enrichment_concepts") is not None
        assert "abstract" in attrs or "abstract" in entity_data
