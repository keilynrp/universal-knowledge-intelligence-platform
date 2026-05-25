"""Decision Readout Builder — Task 4.3.

Derives a structured decision readout from dashboard summary data.
Shared interface between dashboard and report builder.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class EvidenceRef:
    """A reference to supporting evidence."""
    ref_type: str  # benchmark | concept | entity | quality | enrichment
    label: str = ""
    value: str = ""
    confidence: float = 0.0
    link: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Recommendation:
    """A recommended action derived from evidence."""
    action: str
    rationale: str
    priority: str = "medium"  # high | medium | low
    evidence_refs: list[EvidenceRef] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["evidence_refs"] = [e.to_dict() for e in self.evidence_refs]
        return d


@dataclass
class DecisionReadout:
    """Structured decision readout for stakeholder consumption."""
    corpus_size: int = 0
    enrichment_coverage: float = 0.0
    authority_coverage: float = 0.0
    quality_score: float = 0.0
    known_signals: list[str] = field(default_factory=list)
    emerging_signals: list[str] = field(default_factory=list)
    confidence_level: str = "low"  # high | medium | low
    missing_data: list[str] = field(default_factory=list)
    recommendations: list[Recommendation] = field(default_factory=list)
    audience: str = "leadership"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["recommendations"] = [r.to_dict() for r in self.recommendations]
        return d


class DecisionReadoutBuilder:
    """Builds a DecisionReadout from dashboard summary data."""

    def build(
        self,
        dashboard: dict[str, Any],
        audience: str = "leadership",
    ) -> DecisionReadout:
        """Build readout from /dashboard/summary response data.

        Handles empty corpus, partial enrichment, missing benchmark,
        and missing concepts gracefully.
        """
        readout = DecisionReadout(audience=audience)

        # Corpus size
        kpis = dashboard.get("kpis", {})
        readout.corpus_size = kpis.get("total_entities", 0)

        if readout.corpus_size == 0:
            readout.confidence_level = "low"
            readout.missing_data.append("No entities in corpus")
            readout.recommendations.append(Recommendation(
                action="Import data",
                rationale="Corpus is empty — no analysis possible",
                priority="high",
            ))
            return readout

        # Enrichment coverage
        enriched = kpis.get("enriched_entities", 0)
        readout.enrichment_coverage = (
            round(enriched / readout.corpus_size, 3) if readout.corpus_size else 0.0
        )
        if readout.enrichment_coverage < 0.5:
            readout.missing_data.append("Enrichment coverage below 50%")

        # Quality score
        readout.quality_score = kpis.get("avg_quality_score", 0.0)

        # Authority coverage
        authority_resolved = kpis.get("authority_resolved", 0)
        readout.authority_coverage = (
            round(authority_resolved / readout.corpus_size, 3)
            if readout.corpus_size else 0.0
        )

        # Known signals from top concepts
        top_concepts = dashboard.get("top_concepts", [])
        if top_concepts:
            readout.known_signals = [
                c.get("concept") or c.get("name", "")
                for c in top_concepts[:5]
                if isinstance(c, dict)
            ]
        else:
            readout.missing_data.append("No concept data available")

        # Emerging signals from timeline
        timeline = dashboard.get("timeline", [])
        if len(timeline) >= 2:
            recent = timeline[-1] if isinstance(timeline[-1], dict) else {}
            prior = timeline[-2] if isinstance(timeline[-2], dict) else {}
            recent_count = recent.get("count", 0)
            prior_count = prior.get("count", 0)
            if recent_count > prior_count * 1.2:
                readout.emerging_signals.append("Accelerating publication rate")
            if recent_count < prior_count * 0.8:
                readout.emerging_signals.append("Declining publication rate")

        # Top entities as signals
        top_entities = dashboard.get("top_entities", [])
        if top_entities:
            for ent in top_entities[:3]:
                if isinstance(ent, dict):
                    label = ent.get("label") or ent.get("primary_label", "")
                    if label:
                        readout.known_signals.append(f"Key entity: {label}")

        # Confidence level
        readout.confidence_level = self._compute_confidence(readout)

        # Generate recommendations
        readout.recommendations = self._generate_recommendations(readout, dashboard)

        return readout

    def _compute_confidence(self, readout: DecisionReadout) -> str:
        """Compute overall confidence from coverage metrics."""
        if readout.corpus_size == 0:
            return "low"
        score = 0.0
        if readout.enrichment_coverage >= 0.8:
            score += 0.4
        elif readout.enrichment_coverage >= 0.5:
            score += 0.2
        if readout.authority_coverage >= 0.5:
            score += 0.3
        elif readout.authority_coverage >= 0.2:
            score += 0.15
        if readout.quality_score >= 0.7:
            score += 0.2
        elif readout.quality_score >= 0.4:
            score += 0.1
        if readout.known_signals:
            score += 0.1

        if score >= 0.7:
            return "high"
        if score >= 0.4:
            return "medium"
        return "low"

    def _generate_recommendations(
        self, readout: DecisionReadout, dashboard: dict[str, Any],
    ) -> list[Recommendation]:
        """Generate recommendations from readout state."""
        recs: list[Recommendation] = []

        if readout.enrichment_coverage < 0.5:
            recs.append(Recommendation(
                action="Run enrichment pipeline",
                rationale=f"Only {readout.enrichment_coverage:.0%} of entities enriched",
                priority="high",
                evidence_refs=[EvidenceRef(
                    ref_type="enrichment",
                    label="Enrichment coverage",
                    value=f"{readout.enrichment_coverage:.0%}",
                )],
            ))

        if readout.authority_coverage < 0.3:
            recs.append(Recommendation(
                action="Initiate authority resolution",
                rationale=f"Only {readout.authority_coverage:.0%} authority coverage",
                priority="high" if readout.authority_coverage < 0.1 else "medium",
                evidence_refs=[EvidenceRef(
                    ref_type="quality",
                    label="Authority coverage",
                    value=f"{readout.authority_coverage:.0%}",
                )],
            ))

        if readout.quality_score < 0.5 and readout.quality_score > 0:
            recs.append(Recommendation(
                action="Review data quality issues",
                rationale=f"Average quality score is {readout.quality_score:.2f}",
                priority="medium",
                evidence_refs=[EvidenceRef(
                    ref_type="quality",
                    label="Quality score",
                    value=f"{readout.quality_score:.2f}",
                )],
            ))

        if not readout.known_signals:
            recs.append(Recommendation(
                action="Enrich entities to extract concepts",
                rationale="No concept signals detected — enrichment needed",
                priority="medium",
            ))

        return recs
