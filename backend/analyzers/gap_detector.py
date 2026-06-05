"""
Knowledge Gap Detector — Phase 10 (Artifact Studio)
Scans a domain and returns a prioritized list of actionable data gaps.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend import models
from backend.analytics.rag_engine import ENRICHED_STATUSES
from backend.schema_registry import SchemaRegistry
from backend.tenant_access import scope_query_to_org

_registry = SchemaRegistry()


@dataclass
class GapItem:
    category: str        # "enrichment" | "authority" | "concepts" | "dimensions"
    severity: str        # "critical" | "warning" | "ok"
    title: str
    description: str
    affected_count: int
    total_count: int
    pct: float           # affected / total * 100
    action: str


class GapAnalyzer:
    """Runs all gap checks and returns results sorted by severity then impact."""

    def analyze(self, domain_id: str, db: Session, org_id: int | None = None) -> List[GapItem]:
        gaps: List[GapItem] = []
        gaps += self._enrichment_gaps(db, org_id)
        gaps += self._authority_gaps(db, org_id)
        gaps += self._concept_density(db, org_id)
        gaps += self._dimension_completeness(domain_id, db, org_id)
        gaps += self._quality_gaps(db, org_id)
        # Sort: critical first, then by pct desc within each severity
        _order = {"critical": 0, "warning": 1, "ok": 2}
        return sorted(gaps, key=lambda g: (_order.get(g.severity, 3), -g.pct))

    # ── 1. Enrichment coverage ────────────────────────────────────────────────

    def _enrichment_gaps(self, db: Session, org_id: int | None = None) -> List[GapItem]:
        total = scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id).count()
        if total == 0:
            return []
        not_done = (
            scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id)
            .filter(models.RawEntity.enrichment_status.notin_(ENRICHED_STATUSES))
            .count()
        )
        pct = not_done / total * 100
        if pct > 40:
            severity = "critical"
        elif pct > 10:
            severity = "warning"
        else:
            severity = "ok"
        return [GapItem(
            category="enrichment",
            severity=severity,
            title="Enrichment Coverage Gap",
            description=f"{not_done} of {total} entities ({pct:.1f}%) have not been enriched with external metadata.",
            affected_count=not_done,
            total_count=total,
            pct=pct,
            action=f"Run enrichment on {not_done} pending entities to improve citation coverage.",
        )]

    # ── 2. Authority resolution backlog ──────────────────────────────────────

    def _authority_gaps(self, db: Session, org_id: int | None = None) -> List[GapItem]:
        total = scope_query_to_org(db.query(models.AuthorityRecord), models.AuthorityRecord, org_id).count()
        if total == 0:
            return []
        pending = (
            scope_query_to_org(db.query(models.AuthorityRecord), models.AuthorityRecord, org_id)
            .filter(models.AuthorityRecord.status == "pending")
            .count()
        )
        if pending == 0:
            return []
        pct = pending / total * 100
        return [GapItem(
            category="authority",
            severity="warning",
            title="Authority Resolution Backlog",
            description=f"{pending} of {total} authority records ({pct:.1f}%) are still pending review.",
            affected_count=pending,
            total_count=total,
            pct=pct,
            action="Review pending authority records in Authority Control to confirm or reject candidates.",
        )]

    # ── 3. Concept density ────────────────────────────────────────────────────

    def _concept_density(self, db: Session, org_id: int | None = None) -> List[GapItem]:
        enriched = (
            scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id)
            .filter(models.RawEntity.enrichment_status.in_(ENRICHED_STATUSES))
            .all()
        )
        if not enriched:
            return []
        sparse = [
            e for e in enriched
            if not e.enrichment_concepts or len(e.enrichment_concepts.split(",")) <= 1
        ]
        pct = len(sparse) / len(enriched) * 100
        if pct <= 15:
            return []
        severity = "critical" if pct > 50 else "warning"
        return [GapItem(
            category="concepts",
            severity=severity,
            title="Low Concept Density",
            description=(
                f"{len(sparse)} enriched entities ({pct:.1f}%) have ≤1 concept tag, "
                "limiting semantic search and topic modeling quality."
            ),
            affected_count=len(sparse),
            total_count=len(enriched),
            pct=pct,
            action="Re-enrich sparse entities or review enrichment source quality to improve concept coverage.",
        )]

    # ── 5. Low-quality entities ───────────────────────────────────────────────

    def _quality_gaps(self, db: Session, org_id: int | None = None) -> List[GapItem]:
        total_with_score = scope_query_to_org(
            db.query(func.count(models.RawEntity.id)), models.RawEntity, org_id
        ).filter(
            models.RawEntity.quality_score != None
        ).scalar() or 0

        if total_with_score > 0:
            low_quality_count = scope_query_to_org(
                db.query(func.count(models.RawEntity.id)), models.RawEntity, org_id
            ).filter(
                models.RawEntity.quality_score < 0.3,
                models.RawEntity.quality_score != None,
            ).scalar() or 0
            low_quality_pct = low_quality_count / total_with_score
            severity = "critical" if low_quality_pct > 0.3 else "warning" if low_quality_pct > 0.1 else "ok"
            return [GapItem(
                category="quality",
                severity=severity,
                title="Low-Quality Entities",
                description=(
                    f"{low_quality_count} of {total_with_score} scored entities "
                    f"({round(low_quality_pct * 100, 1)}%) have a quality score below 0.3."
                ),
                affected_count=low_quality_count,
                total_count=total_with_score,
                pct=round(low_quality_pct * 100, 1),
                action="Run 'Compute Quality Scores' and enrich or add metadata to entities below 0.3.",
            )]
        else:
            return [GapItem(
                category="quality",
                severity="warning",
                title="Low-Quality Entities",
                description="Quality scores have not been computed yet.",
                affected_count=0,
                total_count=0,
                pct=0,
                action="Quality scores have not been computed yet. Run POST /entities/quality/compute.",
            )]

    # ── 4. Dimension completeness ─────────────────────────────────────────────

    def _dimension_completeness(self, domain_id: str, db: Session, org_id: int | None = None) -> List[GapItem]:
        domain = _registry.get_domain(domain_id)
        if not domain:
            return []
        total = scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id).count()
        if total == 0:
            return []

        _EMPTY = {"", "unknown", "n/a", "none", "null", "-", "sin datos"}
        gaps: List[GapItem] = []

        string_fields = [a for a in domain.attributes if a.type == "string" and a.is_core]
        for attr in string_fields:
            col = getattr(models.RawEntity, attr.name, None)
            if col is None:
                continue
            rows = scope_query_to_org(db.query(col), models.RawEntity, org_id).all()
            missing = sum(
                1 for (v,) in rows
                if v is None or str(v).strip().lower() in _EMPTY
            )
            pct = missing / total * 100
            if pct < 20:
                continue
            severity = "critical" if pct > 60 else "warning"
            gaps.append(GapItem(
                category="dimensions",
                severity=severity,
                title=f"Missing Values: {attr.label}",
                description=f"{missing} of {total} entities ({pct:.1f}%) have no value for '{attr.label}'.",
                affected_count=missing,
                total_count=total,
                pct=pct,
                action=f"Populate the '{attr.label}' field to improve OLAP query coverage and filtering accuracy.",
            ))
        return gaps
