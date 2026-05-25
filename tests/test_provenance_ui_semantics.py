"""Tests for provenance_ui_semantics.py — Task 5.5."""
import pytest

from backend.services.provenance_ui_semantics import (
    AI_ASSISTED,
    AI_GENERATED,
    CONFIDENCE_LEVELS,
    NULL_STATE,
    PROV_BADGES,
    get_ai_disclosure,
    get_confidence_level,
    get_prov_badge,
)


class TestProvBadges:
    def test_four_layers(self):
        assert len(PROV_BADGES) == 4
        assert set(PROV_BADGES.keys()) == {"source", "enrichment", "canonical", "authority"}

    def test_source_badge(self):
        badge = get_prov_badge("source")
        assert badge is not None
        assert badge.label == "Source"
        assert badge.color_token == "--ukip-muted"

    def test_enrichment_badge(self):
        badge = get_prov_badge("enrichment")
        assert badge.color_token == "--ukip-cyan"

    def test_canonical_badge(self):
        badge = get_prov_badge("canonical")
        assert badge.color_token == "--ukip-emerald"

    def test_authority_badge(self):
        badge = get_prov_badge("authority")
        assert badge.color_token == "--ukip-violet"

    def test_unknown_layer(self):
        assert get_prov_badge("bogus") is None

    def test_to_dict(self):
        badge = get_prov_badge("source")
        d = badge.to_dict()
        assert d["layer"] == "source"
        assert d["icon"] == "upload"


class TestConfidenceLevels:
    def test_high(self):
        config = get_confidence_level(0.9)
        assert config.level == "high"
        assert config.color_token == "--ukip-emerald"

    def test_medium(self):
        config = get_confidence_level(0.6)
        assert config.level == "medium"

    def test_low(self):
        config = get_confidence_level(0.3)
        assert config.level == "low"
        assert config.color_token == "--ukip-danger"

    def test_unknown(self):
        config = get_confidence_level(0.1)
        assert config.level == "unknown"

    def test_review_required(self):
        config = get_confidence_level(0.9, requires_review=True)
        assert config.level == "review_required"
        assert config.color_token == "--ukip-warning"

    def test_to_dict(self):
        config = get_confidence_level(0.85)
        d = config.to_dict()
        assert d["level"] == "high"
        assert d["min_threshold"] == 0.8


class TestNullState:
    def test_de_emphasized(self):
        assert NULL_STATE.style == "de_emphasized"
        assert NULL_STATE.opacity == 0.5
        assert NULL_STATE.show_reason is True


class TestAIDisclosure:
    def test_assisted(self):
        config = get_ai_disclosure(is_generated=False)
        assert config.badge_label == "AI-assisted"
        assert config.color_token == "--ukip-cyan"

    def test_generated(self):
        config = get_ai_disclosure(is_generated=True)
        assert config.badge_label == "AI-generated"
        assert config.icon == "bot"

    def test_to_dict(self):
        d = AI_ASSISTED.to_dict()
        assert d["badge_label"] == "AI-assisted"
        assert d["tooltip"] != ""
