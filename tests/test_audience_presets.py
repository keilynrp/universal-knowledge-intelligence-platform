"""Tests for audience_presets.py — Task 4.5."""
import pytest

from backend.services.audience_presets import (
    AUDIENCE_PRESETS,
    DEFAULT_AUDIENCE,
    AudiencePreset,
    apply_framing,
    get_preset,
    list_presets,
)


class TestPresets:
    def test_five_presets_defined(self):
        assert len(AUDIENCE_PRESETS) == 5

    def test_all_preset_ids(self):
        expected = {"leadership", "research_office", "investigator", "innovation_transfer", "evaluator"}
        assert set(AUDIENCE_PRESETS.keys()) == expected

    def test_default_is_leadership(self):
        assert DEFAULT_AUDIENCE == "leadership"

    def test_preset_has_translations(self):
        for preset in AUDIENCE_PRESETS.values():
            assert preset.label != ""
            assert preset.label_es != ""
            assert preset.description != ""
            assert preset.description_es != ""
            assert preset.cta_label != ""
            assert preset.cta_label_es != ""

    def test_preset_has_emphasis(self):
        for preset in AUDIENCE_PRESETS.values():
            assert len(preset.emphasis) > 0


class TestGetPreset:
    def test_known_preset(self):
        p = get_preset("investigator")
        assert p.preset_id == "investigator"

    def test_unknown_defaults_to_leadership(self):
        p = get_preset("unknown_audience")
        assert p.preset_id == "leadership"


class TestListPresets:
    def test_returns_list_of_dicts(self):
        result = list_presets()
        assert len(result) == 5
        assert all(isinstance(r, dict) for r in result)
        assert result[0]["preset_id"] in AUDIENCE_PRESETS


class TestApplyFraming:
    def test_adds_audience_metadata(self):
        readout = {"corpus_size": 100, "confidence_level": "high"}
        framed = apply_framing(readout, "leadership")
        assert framed["audience"] == "leadership"
        assert framed["audience_label"] == "Executive Leadership"
        assert framed["cta_label"] == "Export Executive Brief"
        assert "confidence_level" in framed["emphasized_fields"]

    def test_investigator_framing(self):
        readout = {"corpus_size": 100}
        framed = apply_framing(readout, "investigator")
        assert framed["audience_label"] == "Principal Investigator"
        assert "known_signals" in framed["emphasized_fields"]

    def test_unknown_audience_gets_leadership(self):
        readout = {"corpus_size": 50}
        framed = apply_framing(readout, "xyz_bad")
        assert framed["audience_label"] == "Executive Leadership"

    def test_values_unchanged(self):
        readout = {"corpus_size": 100, "quality_score": 0.8}
        framed = apply_framing(readout, "evaluator")
        assert framed["corpus_size"] == 100
        assert framed["quality_score"] == 0.8
