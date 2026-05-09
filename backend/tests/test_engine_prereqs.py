"""Tests for engine prerequisite DB constraints."""
import pytest
from sqlalchemy import inspect


class TestEnginePrereqMigration:
    def test_updated_at_column_exists(self, db_session):
        from backend.models import UniversalEntity
        assert hasattr(UniversalEntity, 'updated_at')

    def test_updated_at_column_nullable(self, db_session):
        from backend.models import UniversalEntity
        col = UniversalEntity.__table__.columns['updated_at']
        assert col.nullable is True

    def test_updated_at_column_type(self, db_session):
        from backend.models import UniversalEntity
        from sqlalchemy import DateTime
        col = UniversalEntity.__table__.columns['updated_at']
        assert isinstance(col.type, DateTime)

    def test_unique_constraint_columns_exist(self, db_session):
        from backend.models import UniversalEntity, EntityRelationship
        mapper = inspect(UniversalEntity)
        col_names = [c.key for c in mapper.column_attrs]
        assert 'org_id' in col_names
        assert 'domain' in col_names
        assert 'entity_type' in col_names
        assert 'canonical_id' in col_names

    def test_relationship_constraint_columns_exist(self, db_session):
        from backend.models import EntityRelationship
        mapper = inspect(EntityRelationship)
        col_names = [c.key for c in mapper.column_attrs]
        assert 'org_id' in col_names
        assert 'source_id' in col_names
        assert 'target_id' in col_names
        assert 'relation_type' in col_names

    def test_raw_entity_alias_has_updated_at(self, db_session):
        from backend.models import RawEntity
        assert hasattr(RawEntity, 'updated_at')
