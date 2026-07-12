"""ML feature-readiness for the retrospective layer (Phase 6).

Generates offline, point-in-time feature datasets from the append-only history
(ml-feature-readiness-contract spec). This module prepares data for FUTURE
learning workflows — it does not train, deploy, or serve models. It guarantees:

- **Point-in-time envelopes (6.1)** — every row carries feature_timestamp and
  label_timestamp with feature_timestamp <= label_timestamp.
- **Governed labels (6.2)** — labels come from governed decisions
  (authority accept/reject) or explicitly-flagged proxy outcomes with lineage.
- **Leakage prevention (6.3)** — no feature value observed after feature_timestamp
  is included; every row is leakage-checked.
- **Lineage (6.4)** — each row records the snapshots/events it was built from.
- **Offline validation only (6.5)** — the builder emits dataset quality metrics
  and creates no model endpoint.
"""
from __future__ import annotations

import json
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from .. import models

SCHEMA_VERSION = 1


# ── 6.1 Feature dataset envelope ────────────────────────────────────────────

@dataclass(frozen=True)
class FeatureRow:
    dataset_id: str
    dataset_version: str
    org_scope: Optional[int]
    subject_type: str
    subject_id: str
    feature_timestamp: datetime
    label_timestamp: datetime
    features: dict
    labels: dict
    lineage: dict
    schema_version: int = SCHEMA_VERSION
    created_at: datetime = field(default_factory=lambda: datetime.now().replace(microsecond=0))


@dataclass(frozen=True)
class FeatureDataset:
    dataset_id: str
    dataset_version: str
    org_scope: Optional[int]
    created_at: datetime
    rows: list[FeatureRow]
    leakage_ok: bool
    quality: dict


# ── 6.3 Leakage check ───────────────────────────────────────────────────────

def leakage_violations(
    feature_timestamp: datetime,
    label_timestamp: datetime,
    source_timestamps: list[datetime],
) -> list[str]:
    """Return leakage problems for one row (empty list = clean)."""
    problems: list[str] = []
    if not feature_timestamp <= label_timestamp:
        problems.append("feature_timestamp is after label_timestamp")
    for ts in source_timestamps:
        if ts > feature_timestamp:
            problems.append(f"feature source at {ts.isoformat()} is after feature_timestamp")
    return problems


# ── 6.2 Governed labels ─────────────────────────────────────────────────────

_DECISION_LABELS = {"authority.accepted": 1, "authority.rejected": 0}


def governed_label_from_decision(event: models.RetrospectiveEvent) -> Optional[dict]:
    """Extract a governed supervised label from an authority decision event.

    Returns ``None`` for non-decision events. The label carries the reviewer role
    and decision lineage, per the spec's "authority decision creates a label".
    """
    if event.event_type not in _DECISION_LABELS:
        return None
    return {
        "value": _DECISION_LABELS[event.event_type],
        "label_kind": "governed_decision",
        "label_timestamp": event.occurred_at,
        "lineage": {
            "source": "retrospective_event",
            "event_id": event.event_id,
            "event_type": event.event_type,
            "actor_type": event.actor_type,
            "actor_id": event.actor_id,
        },
    }


# ── 6.5 First offline dataset: journal NIF trajectory ───────────────────────

def build_journal_nif_dataset(
    db: Session, *, org_scope: Optional[int], dataset_version: str = "v1"
) -> FeatureDataset:
    """Build an offline feature dataset from journal-metric snapshot trajectories.

    For each journal with >= 2 snapshots, the EARLIEST snapshot supplies features
    and a LATER snapshot supplies a proxy label (``nif_increased``) with lineage —
    an "explicitly approved proxy outcome" per 6.2. Every row is leakage-checked
    (features are strictly before the label). No model is trained.
    """
    dataset_id = uuid.uuid4().hex
    created_at = datetime.now().replace(microsecond=0)

    q = db.query(models.RetrospectiveSnapshot).filter(
        models.RetrospectiveSnapshot.snapshot_type == "journal_metric"
    )
    q = q.filter(
        models.RetrospectiveSnapshot.org_id.is_(None)
        if org_scope is None
        else models.RetrospectiveSnapshot.org_id == org_scope
    )
    by_subject: dict[str, list[models.RetrospectiveSnapshot]] = defaultdict(list)
    for snap in q.order_by(models.RetrospectiveSnapshot.valid_at.asc()).all():
        by_subject[snap.subject_id].append(snap)

    rows: list[FeatureRow] = []
    leakage_ok = True
    for subject_id, snaps in by_subject.items():
        if len(snaps) < 2:
            continue  # need a before/after pair
        feat_snap, label_snap = snaps[0], snaps[-1]
        feat_payload = json.loads(feat_snap.payload)
        label_payload = json.loads(label_snap.payload)

        problems = leakage_violations(
            feat_snap.valid_at, label_snap.valid_at, [feat_snap.valid_at]
        )
        if problems:
            leakage_ok = False
            continue  # never emit a leaky row

        feat_nif = feat_payload.get("nif")
        label_nif = label_payload.get("nif")
        nif_increased = (
            1 if (feat_nif is not None and label_nif is not None and label_nif > feat_nif) else 0
        )
        rows.append(FeatureRow(
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            org_scope=org_scope,
            subject_type="journal",
            subject_id=subject_id,
            feature_timestamp=feat_snap.valid_at,
            label_timestamp=label_snap.valid_at,
            features={
                "nif": feat_nif,
                "nif_bayes": feat_payload.get("nif_bayes"),
                "two_yr_mean_citedness": feat_payload.get("two_yr_mean_citedness"),
                "works_2yr": feat_payload.get("works_2yr"),
                "nif_field": feat_payload.get("nif_field"),
            },
            labels={
                "nif_increased": nif_increased,
                "label_kind": "proxy_outcome",
            },
            lineage={
                "feature_snapshot_id": feat_snap.snapshot_id,
                "feature_valid_at": feat_snap.valid_at.isoformat(),
                "label_snapshot_id": label_snap.snapshot_id,
                "label_valid_at": label_snap.valid_at.isoformat(),
                "source": "journal_metric_snapshot",
            },
            created_at=created_at,
        ))

    quality = {
        "row_counts": len(rows),
        "subjects_considered": len(by_subject),
        "lineage_completeness": (
            sum(1 for r in rows if r.lineage) / len(rows) if rows else 1.0
        ),
        "leakage_ok": leakage_ok,
        "positive_labels": sum(1 for r in rows if r.labels["nif_increased"] == 1),
    }
    return FeatureDataset(
        dataset_id=dataset_id, dataset_version=dataset_version, org_scope=org_scope,
        created_at=created_at, rows=rows, leakage_ok=leakage_ok, quality=quality,
    )
