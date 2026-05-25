"""Tests for feature_flags.py — Task 5.1."""
import os
import pytest

from backend.services.feature_flags import (
    commerce_adapters_enabled,
    get_all_flags,
    is_commerce_store_type,
    is_enabled,
    visible_store_types,
)


class TestIsEnabled:
    def test_default_commerce_true(self):
        # Remove env var if set
        os.environ.pop("ENABLE_COMMERCE_ADAPTERS", None)
        assert is_enabled("ENABLE_COMMERCE_ADAPTERS") is True

    def test_env_override_false(self, monkeypatch):
        monkeypatch.setenv("ENABLE_COMMERCE_ADAPTERS", "false")
        assert is_enabled("ENABLE_COMMERCE_ADAPTERS") is False

    def test_env_override_true(self, monkeypatch):
        monkeypatch.setenv("ENABLE_COMMERCE_ADAPTERS", "1")
        assert is_enabled("ENABLE_COMMERCE_ADAPTERS") is True

    def test_env_yes(self, monkeypatch):
        monkeypatch.setenv("ENABLE_COMMERCE_ADAPTERS", "yes")
        assert is_enabled("ENABLE_COMMERCE_ADAPTERS") is True

    def test_unknown_flag_default_false(self):
        assert is_enabled("UNKNOWN_FLAG_XYZ") is False

    def test_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("ENABLE_LINKED_DATA_EXPORT", "TRUE")
        assert is_enabled("ENABLE_LINKED_DATA_EXPORT") is True


class TestGetAllFlags:
    def test_returns_all_known(self):
        flags = get_all_flags()
        assert "ENABLE_COMMERCE_ADAPTERS" in flags
        assert "ENABLE_LINKED_DATA_EXPORT" in flags
        assert "ENABLE_STAKEHOLDER_DEMO" in flags


class TestCommerceHelpers:
    def test_commerce_enabled_default(self):
        os.environ.pop("ENABLE_COMMERCE_ADAPTERS", None)
        assert commerce_adapters_enabled() is True

    def test_commerce_disabled(self, monkeypatch):
        monkeypatch.setenv("ENABLE_COMMERCE_ADAPTERS", "false")
        assert commerce_adapters_enabled() is False

    def test_visible_stores_when_enabled(self):
        os.environ.pop("ENABLE_COMMERCE_ADAPTERS", None)
        stores = visible_store_types()
        assert "shopify" in stores
        assert "woocommerce" in stores
        assert "bsale" in stores

    def test_visible_stores_when_disabled(self, monkeypatch):
        monkeypatch.setenv("ENABLE_COMMERCE_ADAPTERS", "0")
        stores = visible_store_types()
        assert len(stores) == 0

    def test_is_commerce_store_type(self):
        assert is_commerce_store_type("shopify") is True
        assert is_commerce_store_type("Shopify") is True
        assert is_commerce_store_type("scientific") is False
