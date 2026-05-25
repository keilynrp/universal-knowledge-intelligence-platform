"""Audience Presets — Task 4.5.

Defines stakeholder audience presets and adjusts readout framing
(labels, CTAs, emphasis) by audience. Calculations remain unchanged.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class AudiencePreset:
    """Defines how a readout is framed for a specific audience."""
    preset_id: str
    label: str
    label_es: str
    description: str
    description_es: str
    emphasis: list[str] = field(default_factory=list)
    cta_label: str = ""
    cta_label_es: str = ""


AUDIENCE_PRESETS: dict[str, AudiencePreset] = {
    "leadership": AudiencePreset(
        preset_id="leadership",
        label="Executive Leadership",
        label_es="Liderazgo Ejecutivo",
        description="High-level strategic signals and investment readiness",
        description_es="Señales estratégicas de alto nivel y preparación para inversión",
        emphasis=["confidence_level", "emerging_signals", "recommendations"],
        cta_label="Export Executive Brief",
        cta_label_es="Exportar Resumen Ejecutivo",
    ),
    "research_office": AudiencePreset(
        preset_id="research_office",
        label="Research Office",
        label_es="Oficina de Investigación",
        description="Corpus quality, enrichment coverage, and authority status",
        description_es="Calidad del corpus, cobertura de enriquecimiento y estado de autoridad",
        emphasis=["enrichment_coverage", "authority_coverage", "quality_score", "missing_data"],
        cta_label="Export Data Quality Report",
        cta_label_es="Exportar Informe de Calidad de Datos",
    ),
    "investigator": AudiencePreset(
        preset_id="investigator",
        label="Principal Investigator",
        label_es="Investigador Principal",
        description="Evidence-backed signals and concept landscape",
        description_es="Señales respaldadas por evidencia y panorama de conceptos",
        emphasis=["known_signals", "emerging_signals", "corpus_size"],
        cta_label="Export Research Landscape",
        cta_label_es="Exportar Panorama de Investigación",
    ),
    "innovation_transfer": AudiencePreset(
        preset_id="innovation_transfer",
        label="Innovation & Transfer",
        label_es="Innovación y Transferencia",
        description="Emerging trends and collaboration potential",
        description_es="Tendencias emergentes y potencial de colaboración",
        emphasis=["emerging_signals", "known_signals", "recommendations"],
        cta_label="Export Innovation Brief",
        cta_label_es="Exportar Resumen de Innovación",
    ),
    "evaluator": AudiencePreset(
        preset_id="evaluator",
        label="External Evaluator",
        label_es="Evaluador Externo",
        description="Transparent methodology and evidence traceability",
        description_es="Metodología transparente y trazabilidad de evidencia",
        emphasis=["confidence_level", "quality_score", "missing_data", "enrichment_coverage"],
        cta_label="Export Evaluation Report",
        cta_label_es="Exportar Informe de Evaluación",
    ),
}

DEFAULT_AUDIENCE = "leadership"


def get_preset(audience: str) -> AudiencePreset:
    """Get audience preset, defaulting to leadership."""
    return AUDIENCE_PRESETS.get(audience, AUDIENCE_PRESETS[DEFAULT_AUDIENCE])


def list_presets() -> list[dict[str, Any]]:
    """List all available audience presets."""
    return [asdict(p) for p in AUDIENCE_PRESETS.values()]


def apply_framing(
    readout_dict: dict[str, Any],
    audience: str,
) -> dict[str, Any]:
    """Apply audience framing to a readout dict.

    Adds audience metadata and emphasis markers.
    Calculations (values) remain unchanged.
    """
    preset = get_preset(audience)
    readout_dict["audience"] = audience
    readout_dict["audience_label"] = preset.label
    readout_dict["audience_description"] = preset.description
    readout_dict["cta_label"] = preset.cta_label
    readout_dict["emphasized_fields"] = preset.emphasis
    return readout_dict
