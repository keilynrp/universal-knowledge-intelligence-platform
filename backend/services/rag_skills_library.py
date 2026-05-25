"""Initial RAG Skills Library — Task 4.8.

Implements 3 initial skills: evidence-grading, citation-grounding,
stakeholder-briefing. All are advisory governance level.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class EvidenceGrade:
    """Grade for a single piece of evidence."""
    evidence_id: str = ""
    relevance: float = 0.0  # 0-1
    quality: float = 0.0  # 0-1
    recency: float = 0.0  # 0-1
    overall: float = 0.0
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CitationGrounding:
    """A grounded citation mapping a claim to evidence."""
    claim: str = ""
    evidence_ref: str = ""
    entity_id: int | None = None
    field_name: str = ""
    confidence: float = 0.0
    snippet: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StakeholderBriefing:
    """An audience-aware narrative briefing."""
    audience: str = "leadership"
    narrative: str = ""
    key_findings: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    confidence: float = 0.0
    caveats: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EvidenceGradingSkill:
    """Grade retrieved evidence for quality and relevance (advisory).

    Skill ID: evidence_grading
    Governance: advisory
    """

    SKILL_ID = "evidence_grading"
    GOVERNANCE_LEVEL = "advisory"

    def execute(
        self,
        query: str,
        evidence_items: list[dict[str, Any]],
    ) -> list[EvidenceGrade]:
        """Grade each evidence item for relevance and quality."""
        grades: list[EvidenceGrade] = []

        for item in evidence_items:
            grade = self._grade_single(query, item)
            grades.append(grade)

        # Sort by overall descending
        grades.sort(key=lambda g: g.overall, reverse=True)
        return grades

    def _grade_single(self, query: str, item: dict[str, Any]) -> EvidenceGrade:
        """Grade a single evidence item using heuristics."""
        text = str(item.get("text", "") or item.get("content", ""))
        source = str(item.get("source", ""))

        # Relevance: keyword overlap
        query_tokens = set(query.lower().split())
        text_tokens = set(text.lower().split())
        overlap = len(query_tokens & text_tokens)
        relevance = min(overlap / max(len(query_tokens), 1), 1.0)

        # Quality: length and structure
        quality = 0.5
        if len(text) > 200:
            quality += 0.2
        if len(text) > 500:
            quality += 0.1
        if item.get("enrichment_doi") or item.get("doi"):
            quality += 0.2
        quality = min(quality, 1.0)

        # Recency: presence of year
        recency = 0.5
        if item.get("year"):
            try:
                year = int(item["year"])
                if year >= 2024:
                    recency = 0.9
                elif year >= 2020:
                    recency = 0.7
                elif year >= 2015:
                    recency = 0.5
                else:
                    recency = 0.3
            except (ValueError, TypeError):
                pass

        overall = round(0.5 * relevance + 0.3 * quality + 0.2 * recency, 3)

        return EvidenceGrade(
            evidence_id=str(item.get("id", "")),
            relevance=round(relevance, 3),
            quality=round(quality, 3),
            recency=round(recency, 3),
            overall=overall,
            rationale=self._build_rationale(relevance, quality, recency),
        )

    def _build_rationale(self, relevance: float, quality: float, recency: float) -> str:
        parts: list[str] = []
        if relevance >= 0.7:
            parts.append("highly relevant")
        elif relevance >= 0.4:
            parts.append("moderately relevant")
        else:
            parts.append("low relevance")
        if quality >= 0.7:
            parts.append("high quality")
        if recency >= 0.7:
            parts.append("recent")
        return "; ".join(parts).capitalize()


class CitationGroundingSkill:
    """Map claims to specific evidence references (advisory).

    Skill ID: citation_grounding
    Governance: advisory
    """

    SKILL_ID = "citation_grounding"
    GOVERNANCE_LEVEL = "advisory"

    def execute(
        self,
        claims: list[str],
        evidence_items: list[dict[str, Any]],
    ) -> list[CitationGrounding]:
        """Ground claims to evidence items using keyword matching."""
        groundings: list[CitationGrounding] = []

        for claim in claims:
            best = self._find_best_evidence(claim, evidence_items)
            if best:
                groundings.append(best)
            else:
                groundings.append(CitationGrounding(
                    claim=claim,
                    confidence=0.0,
                    snippet="No supporting evidence found",
                ))

        return groundings

    def _find_best_evidence(
        self, claim: str, evidence_items: list[dict[str, Any]],
    ) -> CitationGrounding | None:
        """Find the best evidence item supporting a claim."""
        claim_tokens = set(claim.lower().split())
        best_score = 0.0
        best_item: dict[str, Any] | None = None

        for item in evidence_items:
            text = str(item.get("text", "") or item.get("content", "") or item.get("primary_label", ""))
            item_tokens = set(text.lower().split())
            overlap = len(claim_tokens & item_tokens)
            score = overlap / max(len(claim_tokens), 1)

            if score > best_score:
                best_score = score
                best_item = item

        if best_item and best_score >= 0.3:
            text = str(best_item.get("text", "") or best_item.get("content", "") or "")
            snippet = text[:200] if text else ""
            return CitationGrounding(
                claim=claim,
                evidence_ref=str(best_item.get("id", "")),
                entity_id=best_item.get("entity_id") or best_item.get("id"),
                field_name=best_item.get("field_name", ""),
                confidence=round(min(best_score, 1.0), 3),
                snippet=snippet,
            )
        return None


class StakeholderBriefingSkill:
    """Generate audience-aware decision narrative (advisory).

    Skill ID: stakeholder_briefing
    Governance: advisory
    """

    SKILL_ID = "stakeholder_briefing"
    GOVERNANCE_LEVEL = "advisory"

    def execute(
        self,
        readout: dict[str, Any],
        audience: str = "leadership",
        evidence_items: list[dict[str, Any]] | None = None,
    ) -> StakeholderBriefing:
        """Generate a narrative briefing from a decision readout."""
        findings = self._extract_findings(readout)
        narrative = self._build_narrative(readout, audience, findings)
        caveats = self._identify_caveats(readout)

        evidence_refs: list[str] = []
        if evidence_items:
            evidence_refs = [
                str(e.get("id", "")) for e in evidence_items[:10]
                if isinstance(e, dict)
            ]

        confidence = self._assess_confidence(readout)

        return StakeholderBriefing(
            audience=audience,
            narrative=narrative,
            key_findings=findings,
            evidence_refs=evidence_refs,
            confidence=confidence,
            caveats=caveats,
        )

    def _extract_findings(self, readout: dict[str, Any]) -> list[str]:
        findings: list[str] = []
        corpus = readout.get("corpus_size", 0)
        if corpus > 0:
            findings.append(f"Corpus contains {corpus} entities")

        enr = readout.get("enrichment_coverage", 0)
        if enr > 0:
            findings.append(f"Enrichment coverage: {enr:.0%}")

        signals = readout.get("known_signals", [])
        if signals:
            findings.append(f"Top signals: {', '.join(signals[:3])}")

        emerging = readout.get("emerging_signals", [])
        if emerging:
            findings.append(f"Emerging: {', '.join(emerging[:2])}")

        return findings

    def _build_narrative(
        self, readout: dict[str, Any], audience: str, findings: list[str],
    ) -> str:
        """Build a simple template-based narrative."""
        confidence = readout.get("confidence_level", "low")
        corpus = readout.get("corpus_size", 0)

        if corpus == 0:
            return "No data available for analysis. Import entities to begin."

        opening = {
            "leadership": f"Based on analysis of {corpus} entities, ",
            "research_office": f"Data quality assessment of {corpus} entities indicates ",
            "investigator": f"The research landscape across {corpus} entities shows ",
            "innovation_transfer": f"Innovation signals from {corpus} entities reveal ",
            "evaluator": f"Methodological review of {corpus} entities demonstrates ",
        }.get(audience, f"Analysis of {corpus} entities shows ")

        body = "; ".join(findings[:3]) if findings else "insufficient data for conclusions"
        confidence_note = f" (confidence: {confidence})"

        return opening + body + confidence_note + "."

    def _identify_caveats(self, readout: dict[str, Any]) -> list[str]:
        caveats: list[str] = []
        missing = readout.get("missing_data", [])
        if missing:
            caveats.extend(missing[:3])
        if readout.get("enrichment_coverage", 0) < 0.5:
            caveats.append("Less than 50% enrichment coverage may limit signal strength")
        if readout.get("confidence_level") == "low":
            caveats.append("Overall confidence is low — findings are preliminary")
        return caveats

    def _assess_confidence(self, readout: dict[str, Any]) -> float:
        """Map confidence level to numeric score."""
        level = readout.get("confidence_level", "low")
        return {"high": 0.85, "medium": 0.6, "low": 0.3}.get(level, 0.3)
