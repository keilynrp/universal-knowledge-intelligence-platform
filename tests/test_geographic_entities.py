"""Tests for Task 1.2 — Geographic Entity Model."""
from backend.services.geographic_entities import (
    GeoEntityType,
    GeographicEntity,
    validate_country_code,
    normalize_geonames_id,
    normalize_wikidata_qid,
    normalize_osm_id,
    build_ancestor_chain,
    normalize_geo_name,
    matches_alias,
    create_geographic_entity_from_dict,
)


class TestValidateCountryCode:
    def test_valid_codes(self):
        assert validate_country_code("US") == "US"
        assert validate_country_code("gb") == "GB"
        assert validate_country_code("  de  ") == "DE"

    def test_invalid_codes(self):
        assert validate_country_code("XX") is None
        assert validate_country_code("ZZZ") is None
        assert validate_country_code("") is None
        assert validate_country_code(None) is None

    def test_territories(self):
        assert validate_country_code("HK") == "HK"
        assert validate_country_code("PR") == "PR"


class TestNormalizeGeonamesId:
    def test_integer(self):
        assert normalize_geonames_id(3865483) == 3865483

    def test_string(self):
        assert normalize_geonames_id("3865483") == 3865483

    def test_url(self):
        assert normalize_geonames_id("https://www.geonames.org/3865483") == 3865483

    def test_invalid(self):
        assert normalize_geonames_id("abc") is None
        assert normalize_geonames_id(None) is None
        assert normalize_geonames_id(0) is None
        assert normalize_geonames_id(-1) is None


class TestNormalizeWikidataQid:
    def test_bare_qid(self):
        assert normalize_wikidata_qid("Q30") == "Q30"
        assert normalize_wikidata_qid("q30") == "Q30"

    def test_url(self):
        assert normalize_wikidata_qid("https://www.wikidata.org/wiki/Q30") == "Q30"
        assert normalize_wikidata_qid("http://www.wikidata.org/entity/Q30") == "Q30"

    def test_bare_numeric(self):
        assert normalize_wikidata_qid("30") == "Q30"

    def test_invalid(self):
        assert normalize_wikidata_qid(None) is None
        assert normalize_wikidata_qid("") is None
        assert normalize_wikidata_qid("abc") is None


class TestNormalizeOsmId:
    def test_integer(self):
        assert normalize_osm_id(12345) == 12345

    def test_string(self):
        assert normalize_osm_id("12345") == 12345

    def test_invalid(self):
        assert normalize_osm_id(None) is None
        assert normalize_osm_id(0) is None


class TestGeographicEntity:
    def test_to_dict(self):
        entity = GeographicEntity(
            id=1,
            type=GeoEntityType.COUNTRY,
            name="Argentina",
            country_code="AR",
        )
        d = entity.to_dict()
        assert d["type"] == "country"
        assert d["name"] == "Argentina"
        assert d["country_code"] == "AR"

    def test_default_values(self):
        entity = GeographicEntity()
        assert entity.type == GeoEntityType.UNKNOWN
        assert entity.name == ""
        assert entity.parent_id is None
        assert entity.aliases == []


class TestBuildAncestorChain:
    def test_simple_chain(self):
        country = GeographicEntity(id=1, type=GeoEntityType.COUNTRY, name="Argentina")
        region = GeographicEntity(id=2, type=GeoEntityType.REGION, name="Buenos Aires", parent_id=1)
        city = GeographicEntity(id=3, type=GeoEntityType.CITY, name="La Plata", parent_id=2)
        lookup = {1: country, 2: region, 3: city}
        chain = build_ancestor_chain(city, lookup)
        assert len(chain) == 3
        assert chain[0].name == "La Plata"
        assert chain[1].name == "Buenos Aires"
        assert chain[2].name == "Argentina"

    def test_no_parent(self):
        entity = GeographicEntity(id=1, name="Standalone")
        chain = build_ancestor_chain(entity, {1: entity})
        assert len(chain) == 1

    def test_cycle_protection(self):
        a = GeographicEntity(id=1, name="A", parent_id=2)
        b = GeographicEntity(id=2, name="B", parent_id=1)
        chain = build_ancestor_chain(a, {1: a, 2: b})
        assert len(chain) == 2  # stops at cycle


class TestNormalizeGeoName:
    def test_diacritics(self):
        assert normalize_geo_name("São Paulo") == "sao paulo"

    def test_case_folding(self):
        assert normalize_geo_name("BUENOS AIRES") == "buenos aires"


class TestMatchesAlias:
    def test_exact_name(self):
        entity = GeographicEntity(name="United States")
        assert matches_alias(entity, "united states")

    def test_alias_match(self):
        entity = GeographicEntity(name="United States", aliases=["USA", "US", "America"])
        assert matches_alias(entity, "America")

    def test_no_match(self):
        entity = GeographicEntity(name="United States")
        assert not matches_alias(entity, "Canada")

    def test_empty_query(self):
        entity = GeographicEntity(name="Test")
        assert not matches_alias(entity, "")


class TestCreateFromDict:
    def test_full_dict(self):
        raw = {
            "id": 42,
            "type": "country",
            "name": "Germany",
            "country_code": "DE",
            "wikidata_id": "Q183",
            "geonames_id": 2921044,
            "coordinates": [51.0, 9.0],
            "aliases": ["Deutschland", "Allemagne"],
            "provenance": "geonames",
        }
        entity = create_geographic_entity_from_dict(raw)
        assert entity.id == 42
        assert entity.type == GeoEntityType.COUNTRY
        assert entity.country_code == "DE"
        assert entity.wikidata_id == "Q183"
        assert entity.geonames_id == 2921044
        assert entity.coordinates == (51.0, 9.0)
        assert "Deutschland" in entity.aliases

    def test_partial_dict(self):
        raw = {"name": "Unknown Place"}
        entity = create_geographic_entity_from_dict(raw)
        assert entity.type == GeoEntityType.UNKNOWN
        assert entity.name == "Unknown Place"
        assert entity.country_code is None

    def test_invalid_iso(self):
        raw = {"name": "Nowhere", "country_code": "ZZZ"}
        entity = create_geographic_entity_from_dict(raw)
        assert entity.country_code is None

    def test_json_string_aliases(self):
        raw = {"name": "Test", "aliases": '["Alias1", "Alias2"]'}
        entity = create_geographic_entity_from_dict(raw)
        assert entity.aliases == ["Alias1", "Alias2"]

    def test_invalid_type_defaults_to_unknown(self):
        raw = {"name": "Test", "type": "not_a_type"}
        entity = create_geographic_entity_from_dict(raw)
        assert entity.type == GeoEntityType.UNKNOWN
