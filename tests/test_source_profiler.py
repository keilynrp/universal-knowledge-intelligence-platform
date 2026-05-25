"""Tests for Task 1.4 — Source Profiling Contract."""
from backend.services.source_profiler import (
    InferredType,
    SemanticRole,
    SourceProfiler,
    _infer_type_single,
    _detect_semantic_roles,
    _detect_identifiers,
)


class TestTypeInference:
    def test_doi(self):
        assert _infer_type_single("10.1234/test.2023") == InferredType.IDENTIFIER

    def test_orcid(self):
        assert _infer_type_single("0000-0001-2345-6789") == InferredType.IDENTIFIER

    def test_ror(self):
        assert _infer_type_single("https://ror.org/0abcde12") == InferredType.IDENTIFIER

    def test_url(self):
        assert _infer_type_single("https://example.com") == InferredType.URL

    def test_email(self):
        assert _infer_type_single("user@example.com") == InferredType.EMAIL

    def test_date(self):
        assert _infer_type_single("2023-01-15") == InferredType.DATE

    def test_iso_date(self):
        assert _infer_type_single("2023-01-15T10:30:00Z") == InferredType.DATE

    def test_integer(self):
        assert _infer_type_single("42") == InferredType.INTEGER

    def test_float(self):
        assert _infer_type_single("3.14") == InferredType.FLOAT

    def test_boolean(self):
        assert _infer_type_single("true") == InferredType.BOOLEAN
        assert _infer_type_single("False") == InferredType.BOOLEAN

    def test_json_object(self):
        assert _infer_type_single('{"key": "val"}') == InferredType.JSON_OBJECT

    def test_json_array(self):
        assert _infer_type_single('[1, 2, 3]') == InferredType.JSON_ARRAY

    def test_string(self):
        assert _infer_type_single("Hello World") == InferredType.STRING

    def test_empty(self):
        assert _infer_type_single("") == InferredType.UNKNOWN


class TestSemanticRoles:
    def test_author_field(self):
        roles = _detect_semantic_roles("authors", ["John Doe"])
        assert SemanticRole.PERSON in roles

    def test_institution_field(self):
        roles = _detect_semantic_roles("institution", ["MIT"])
        assert SemanticRole.ORGANIZATION in roles

    def test_country_field(self):
        roles = _detect_semantic_roles("country", ["US"])
        assert SemanticRole.PLACE in roles

    def test_concept_field(self):
        roles = _detect_semantic_roles("keywords", ["machine learning"])
        assert SemanticRole.CONCEPT in roles

    def test_doi_values_detected(self):
        values = ["10.1234/a", "10.5678/b", "10.9999/c"]
        roles = _detect_semantic_roles("some_field", values)
        assert SemanticRole.IDENTIFIER in roles
        assert SemanticRole.PUBLICATION in roles

    def test_orcid_values_detected(self):
        values = ["0000-0001-2345-6789", "0000-0002-3456-7890"]
        roles = _detect_semantic_roles("researcher_id", values)
        assert SemanticRole.IDENTIFIER in roles
        assert SemanticRole.PERSON in roles

    def test_unknown_field(self):
        roles = _detect_semantic_roles("xyzzy", ["abc"])
        assert roles == []


class TestIdentifierDetection:
    def test_doi_by_name(self):
        ids = _detect_identifiers("doi", ["anything"])
        assert "DOI" in ids

    def test_doi_by_values(self):
        ids = _detect_identifiers("ref", ["10.1234/test", "10.5678/other"])
        assert "DOI" in ids

    def test_orcid_by_name(self):
        ids = _detect_identifiers("orcid", ["anything"])
        assert "ORCID" in ids

    def test_no_identifiers(self):
        ids = _detect_identifiers("name", ["John Doe", "Jane Smith"])
        assert ids == []


class TestProfilerCSV:
    def test_basic_csv_profile(self):
        records = [
            {"title": "Paper A", "doi": "10.1234/a", "year": "2023", "country": "US"},
            {"title": "Paper B", "doi": "10.1234/b", "year": "2022", "country": "GB"},
            {"title": "Paper C", "doi": "", "year": "2021", "country": ""},
        ]
        profiler = SourceProfiler()
        profile = profiler.profile_records(records, source_id="test.csv")

        assert profile.source_id == "test.csv"
        assert profile.total_rows == 3
        assert profile.source_format == "csv"
        assert len(profile.field_profiles) == 4

        # Check sparsity
        doi_fp = next(fp for fp in profile.field_profiles if fp.field_name == "doi")
        assert doi_fp.non_null_count == 2
        assert doi_fp.sparsity > 0.3

        # Check semantic candidates
        assert "Publication" in profile.semantic_candidates or "Identifier" in profile.semantic_candidates

        # Check identifiers
        assert "DOI" in profile.candidate_identifiers

    def test_empty_records(self):
        profiler = SourceProfiler()
        profile = profiler.profile_records([], source_id="empty")
        assert profile.total_rows == 0
        assert profile.field_profiles == []

    def test_sparse_scenario(self):
        records = [{"a": "x", "b": ""} for _ in range(10)]
        profiler = SourceProfiler()
        profile = profiler.profile_records(records, source_id="sparse")
        b_fp = next(fp for fp in profile.field_profiles if fp.field_name == "b")
        assert b_fp.sparsity == 1.0  # all empty

    def test_to_dict(self):
        profiler = SourceProfiler()
        profile = profiler.profile_records(
            [{"title": "Test", "doi": "10.1234/t"}],
            source_id="dict_test",
        )
        d = profile.to_dict()
        assert isinstance(d, dict)
        assert d["source_id"] == "dict_test"
        assert isinstance(d["field_profiles"], list)


class TestProfilerOpenAlex:
    def test_openalex_works(self):
        works = [
            {
                "id": "W123",
                "doi": "10.1234/test",
                "title": "Sample Paper",
                "publication_date": "2023-06-15",
                "publication_year": 2023,
                "cited_by_count": 10,
                "type": "journal-article",
                "authorships": [
                    {
                        "author": {"display_name": "Jane Doe", "orcid": "0000-0001-2345-6789"},
                        "institutions": [
                            {"display_name": "MIT", "ror": "https://ror.org/042nb2s44", "country_code": "US"}
                        ],
                    }
                ],
                "concepts": [{"display_name": "Machine Learning"}],
                "primary_location": {
                    "source": {"display_name": "Nature", "issn": ["0028-0836"]},
                },
            }
        ]
        profiler = SourceProfiler()
        profile = profiler.profile_openalex_works(works)
        assert profile.source_format == "openalex"
        assert profile.total_rows == 1
        field_names = {fp.field_name for fp in profile.field_profiles}
        assert "doi" in field_names
        assert "authors" in field_names
        assert "institutions" in field_names
        assert "orcids" in field_names
        assert "rors" in field_names


class TestProfilerCrossref:
    def test_crossref_works(self):
        works = [
            {
                "DOI": "10.1234/cross",
                "title": ["Crossref Paper"],
                "type": "journal-article",
                "publisher": "Springer",
                "container-title": ["Journal of Testing"],
                "ISSN": ["1234-5678"],
                "author": [
                    {
                        "given": "John",
                        "family": "Smith",
                        "ORCID": "https://orcid.org/0000-0002-1234-5678",
                        "affiliation": [{"name": "Stanford University"}],
                    }
                ],
                "issued": {"date-parts": [[2023]]},
                "is-referenced-by-count": 5,
            }
        ]
        profiler = SourceProfiler()
        profile = profiler.profile_crossref_works(works)
        assert profile.source_format == "crossref"
        assert profile.total_rows == 1
        field_names = {fp.field_name for fp in profile.field_profiles}
        assert "doi" in field_names
        assert "authors" in field_names
        assert "affiliations" in field_names
        assert "orcids" in field_names


class TestFieldProfileToDict:
    def test_serialization(self):
        from backend.services.source_profiler import FieldProfile
        fp = FieldProfile(
            field_name="test",
            inferred_type=InferredType.STRING,
            semantic_candidates=[SemanticRole.PERSON],
        )
        d = fp.to_dict()
        assert d["inferred_type"] == "string"
        assert d["semantic_candidates"] == ["Person"]
