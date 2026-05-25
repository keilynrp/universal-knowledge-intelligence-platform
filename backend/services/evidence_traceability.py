"""Evidence Traceability — Task 4.6.

Provides evidence references for recommendations and exposes them
for display in expandable panels and PDF/HTML appendix.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


class EvidenceType:
    BENCHMARK = "benchmark"
    CONCEPT = "concept"
    ENTITY = "entity"
    QUALITY = "quality"
    ENRICHMENT = "enrichment"


@dataclass
class EvidenceItem:
    """A traceable evidence item backing a recommendation."""
    ref_type: str  # benchmark | concept | entity | quality | enrichment
    label: str = ""
    entity_id: int | None = None
    field_name: str = ""
    value: str = ""
    confidence: float = 0.0
    source: str = ""  # where the evidence originated
    link: str = ""  # internal link path

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvidencePanel:
    """A panel grouping evidence for a specific recommendation."""
    recommendation_id: str = ""
    recommendation_text: str = ""
    items: list[EvidenceItem] = field(default_factory=list)
    fallback_copy: str = ""  # shown when evidence unavailable

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["items"] = [i.to_dict() for i in self.items]
        d["has_evidence"] = len(self.items) > 0
        return d


class EvidenceTraceabilityService:
    """Builds traceable evidence panels for recommendations."""

    def build_panels(
        self,
        recommendations: list[dict[str, Any]],
        entities: list[dict[str, Any]] | None = None,
        concepts: list[dict[str, Any]] | None = None,
        quality_metrics: dict[str, Any] | None = None,
    ) -> list[EvidencePanel]:
        """Build evidence panels for a list of recommendations."""
        panels: list[EvidencePanel] = []

        for i, rec in enumerate(recommendations):
            panel = self._build_panel(
                rec_id=f"rec_{i}",
                rec=rec,
                entities=entities or [],
                concepts=concepts or [],
                quality_metrics=quality_metrics or {},
            )
            panels.append(panel)

        return panels

    def build_appendix(
        self,
        panels: list[EvidencePanel],
    ) -> dict[str, Any]:
        """Build an evidence appendix for PDF/HTML export."""
        sections: list[dict[str, Any]] = []

        for panel in panels:
            if not panel.items:
                continue
            sections.append({
                "title": panel.recommendation_text or panel.recommendation_id,
                "evidence_count": len(panel.items),
                "items": [
                    {
                        "type": item.ref_type,
                        "label": item.label,
                        "value": item.value,
                        "source": item.source,
                    }
                    for item in panel.items
                ],
            })

        return {
            "title": "Evidence Appendix",
            "total_references": sum(len(p.items) for p in panels),
            "sections": sections,
        }

    def _build_panel(
        self,
        rec_id: str,
        rec: dict[str, Any],
        entities: list[dict[str, Any]],
        concepts: list[dict[str, Any]],
        quality_metrics: dict[str, Any],
    ) -> EvidencePanel:
        """Build a single evidence panel from a recommendation."""
        items: list[EvidenceItem] = []

        # Extract evidence_refs from recommendation
        evidence_refs = rec.get("evidence_refs", [])
        for ref in evidence_refs:
            if isinstance(ref, dict):
                items.append(EvidenceItem(
                    ref_type=ref.get("ref_type", "entity"),
                    label=ref.get("label", ""),
                    value=ref.get("value", ""),
                    confidence=ref.get("confidence", 0.0),
                    source=ref.get("source", ""),
                    link=ref.get("link", ""),
                ))

        # Add concept evidence if action mentions concepts
        action = rec.get("action", "").lower()
        if "concept" in action and concepts:
            for c in concepts[:3]:
                if isinstance(c, dict):
                    items.append(EvidenceItem(
                        ref_type=EvidenceType.CONCEPT,
                        label=c.get("concept") or c.get("name", ""),
                        value=str(c.get("count", "")),
                        source="concept_extraction",
                    ))

        # Add quality evidence if action mentions quality
        if "quality" in action and quality_metrics:
            score = quality_metrics.get("overall_score") or quality_metrics.get("avg_quality_score")
            if score is not None:
                items.append(EvidenceItem(
                    ref_type=EvidenceType.QUALITY,
                    label="Overall quality score",
                    value=str(score),
                    source="quality_engine",
                ))

        # Add enrichment evidence if action mentions enrichment
        if "enrich" in action and quality_metrics:
            coverage = quality_metrics.get("enrichment_coverage")
            if coverage is not None:
                items.append(EvidenceItem(
                    ref_type=EvidenceType.ENRICHMENT,
                    label="Enrichment coverage",
                    value=f"{coverage:.0%}" if isinstance(coverage, float) else str(coverage),
                    source="enrichment_pipeline",
                ))

        fallback = ""
        if not items:
            fallback = "Evidence details are not yet available for this recommendation."

        return EvidencePanel(
            recommendation_id=rec_id,
            recommendation_text=rec.get("action", ""),
            items=items,
            fallback_copy=fallback,
        )
