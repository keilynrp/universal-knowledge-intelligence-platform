from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any


SOURCE_WEIGHTS: dict[str, float] = {
    "policy": 8.0,
    "news": 5.0,
    "wikipedia": 4.0,
    "repository": 3.0,
    "blog": 2.0,
    "scholarly_web": 2.0,
    "social_web": 1.0,
    "other": 1.0,
}

VALID_SOURCE_TYPES = set(SOURCE_WEIGHTS)
NORMALIZATION_FACTOR = 3.0


def attention_category(score: int) -> str:
    if score <= 0:
        return "none"
    if score <= 24:
        return "low"
    if score <= 49:
        return "moderate"
    if score <= 74:
        return "high"
    return "very_high"


def compute_attention_summary(attributes_json: str | None) -> dict[str, Any]:
    observations = _extract_observations(attributes_json)
    if not observations:
        return _empty_summary()

    now = datetime.now(timezone.utc)
    raw_score = 0.0
    total_mentions = 0
    source_counts: dict[str, int] = {}
    source_weighted: dict[str, float] = {}
    timeline_buckets: dict[str, dict[str, Any]] = {}
    last_seen_values: list[datetime] = []

    for observation in observations:
        source_type = _normalize_source_type(observation.get("source_type"))
        mention_count = _coerce_mentions(observation)
        if mention_count <= 0:
            continue

        last_seen = _parse_datetime(
            observation.get("last_seen_at")
            or observation.get("seen_at")
            or observation.get("date")
        )
        if last_seen is not None:
            last_seen_values.append(last_seen)

        recency = _recency_multiplier(last_seen, now)
        weighted_contribution = math.log1p(mention_count) * SOURCE_WEIGHTS[source_type] * recency
        raw_score += weighted_contribution
        total_mentions += mention_count
        source_counts[source_type] = source_counts.get(source_type, 0) + mention_count
        source_weighted[source_type] = source_weighted.get(source_type, 0.0) + weighted_contribution
        _add_timeline_observation(timeline_buckets, source_type, mention_count, weighted_contribution, last_seen)

    if total_mentions <= 0:
        return _empty_summary()

    score = min(100, round(raw_score * NORMALIZATION_FACTOR))
    last_seen_at = max(last_seen_values).isoformat() if last_seen_values else None
    source_breakdown = _build_source_breakdown(source_counts, source_weighted)
    timeline = _build_timeline(timeline_buckets)
    explanations = _build_explanations(source_breakdown, timeline)
    alerts = _build_alerts(source_breakdown, timeline, total_mentions)

    return {
        "summary": {
            "attention_score": score,
            "category": attention_category(score),
            "total_mentions": total_mentions,
            "active_sources": len(source_counts),
            "last_seen_at": last_seen_at,
        },
        "source_counts": dict(sorted(source_counts.items())),
        "source_breakdown": source_breakdown,
        "timeline": timeline,
        "explanations": explanations,
        "alerts": alerts,
    }


def _empty_summary() -> dict[str, Any]:
    return {
        "summary": {
            "attention_score": 0,
            "category": "none",
            "total_mentions": 0,
            "active_sources": 0,
            "last_seen_at": None,
        },
        "source_counts": {},
        "source_breakdown": [],
        "timeline": [],
        "explanations": [],
        "alerts": [],
    }


def _build_source_breakdown(
    source_counts: dict[str, int],
    source_weighted: dict[str, float],
) -> list[dict[str, Any]]:
    total_weighted = sum(source_weighted.values())
    rows: list[dict[str, Any]] = []
    for source_type, mentions in source_counts.items():
        weighted = source_weighted.get(source_type, 0.0)
        rows.append({
            "source_type": source_type,
            "mentions": mentions,
            "weighted_contribution": round(weighted, 2),
            "share": round(weighted / total_weighted, 4) if total_weighted > 0 else 0.0,
            "weight": SOURCE_WEIGHTS.get(source_type, SOURCE_WEIGHTS["other"]),
        })
    return sorted(
        rows,
        key=lambda item: (
            -float(item["weighted_contribution"]),
            str(item["source_type"]),
        ),
    )


def _add_timeline_observation(
    buckets: dict[str, dict[str, Any]],
    source_type: str,
    mentions: int,
    weighted_contribution: float,
    seen_at: datetime | None,
) -> None:
    if seen_at is None:
        return
    period = seen_at.strftime("%Y-%m")
    bucket = buckets.setdefault(period, {
        "period": period,
        "mentions": 0,
        "weighted_score": 0.0,
        "sources": {},
    })
    bucket["mentions"] += mentions
    bucket["weighted_score"] += weighted_contribution
    sources = bucket["sources"]
    sources[source_type] = sources.get(source_type, 0) + mentions


def _build_timeline(buckets: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    if not buckets:
        return []

    rows: list[dict[str, Any]] = []
    previous_score = 0.0
    previous_scores: list[float] = []

    for period in sorted(buckets):
        bucket = buckets[period]
        weighted_score = float(bucket["weighted_score"])
        score_delta = round(weighted_score - previous_score, 2)
        baseline = sum(previous_scores) / len(previous_scores) if previous_scores else 0.0
        spike = bool(
            previous_scores
            and weighted_score >= max(5.0, baseline * 1.75)
            and score_delta > 0
            and int(bucket["mentions"]) >= 2
        )
        top_source_type = _top_source_type(bucket["sources"])
        rows.append({
            "period": period,
            "mentions": int(bucket["mentions"]),
            "score_delta": score_delta,
            "weighted_score": round(weighted_score, 2),
            "top_source_type": top_source_type,
            "spike": spike,
            "spike_reason": "attention above rolling baseline" if spike else None,
        })
        previous_score = weighted_score
        previous_scores.append(weighted_score)

    return rows


def _top_source_type(sources: dict[str, int]) -> str | None:
    if not sources:
        return None
    return sorted(sources.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _build_explanations(
    source_breakdown: list[dict[str, Any]],
    timeline: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    explanations: list[dict[str, Any]] = []

    if source_breakdown:
        top_source = source_breakdown[0]
        source_type = str(top_source["source_type"])
        share = round(float(top_source["share"]) * 100)
        mentions = int(top_source["mentions"])
        explanations.append({
            "type": "top_source",
            "label": f"{_source_display_name(source_type)} drives the attention score",
            "evidence": f"{_source_display_name(source_type)} contributes {share}% of weighted attention from {mentions} mentions.",
            "priority": 80,
        })

        policy = next((row for row in source_breakdown if row["source_type"] == "policy"), None)
        if policy is not None:
            policy_share = round(float(policy["share"]) * 100)
            explanations.append({
                "type": "policy_mention",
                "label": "Policy attention detected",
                "evidence": f"Policy mentions contribute {policy_share}% of weighted attention.",
                "priority": 95,
            })

    spike_bucket = next((bucket for bucket in reversed(timeline) if bucket.get("spike")), None)
    if spike_bucket is not None:
        explanations.append({
            "type": "attention_spike",
            "label": f"Attention spiked in {spike_bucket['period']}",
            "evidence": (
                f"{spike_bucket['mentions']} mentions appeared in {spike_bucket['period']}, "
                f"led by {_source_display_name(spike_bucket.get('top_source_type'))}."
            ),
            "priority": 90,
        })

    if len(source_breakdown) >= 3:
        explanations.append({
            "type": "cross_source_momentum",
            "label": "Attention is distributed across multiple sources",
            "evidence": f"{len(source_breakdown)} source types are contributing to the current attention signal.",
            "priority": 70,
        })

    return sorted(explanations, key=lambda item: -int(item["priority"]))[:5]


def _source_display_name(source_type: Any) -> str:
    labels = {
        "policy": "Policy",
        "news": "News",
        "wikipedia": "Wikipedia",
        "repository": "Repository",
        "blog": "Blogs",
        "scholarly_web": "Scholarly web",
        "social_web": "Social/web",
        "other": "Other sources",
    }
    return labels.get(str(source_type), "External attention")


def _build_alerts(
    source_breakdown: list[dict[str, Any]],
    timeline: list[dict[str, Any]],
    total_mentions: int,
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    latest_period = timeline[-1]["period"] if timeline else None

    if total_mentions > 0 and len(timeline) == 1:
        alerts.append({
            "type": "new_attention",
            "severity": "low",
            "confidence": "medium",
            "label": "New external attention detected",
            "evidence": f"{total_mentions} external mentions are available for this entity.",
            "period": latest_period,
            "priority": 40,
        })

    spike_bucket = next((bucket for bucket in reversed(timeline) if bucket.get("spike")), None)
    if spike_bucket is not None:
        alerts.append({
            "type": "attention_spike",
            "severity": "medium",
            "confidence": "high" if int(spike_bucket["mentions"]) >= 5 else "medium",
            "label": f"Attention spike in {spike_bucket['period']}",
            "evidence": f"{spike_bucket['mentions']} mentions exceeded the rolling baseline.",
            "period": spike_bucket["period"],
            "priority": 80,
        })

    policy = next((row for row in source_breakdown if row["source_type"] == "policy"), None)
    if policy is not None:
        share = float(policy["share"])
        alerts.append({
            "type": "policy_mention",
            "severity": "high" if share >= 0.25 else "medium",
            "confidence": "high",
            "label": "Policy attention detected",
            "evidence": f"Policy sources account for {round(share * 100)}% of weighted attention.",
            "period": latest_period,
            "priority": 90,
        })

    if len(source_breakdown) >= 3:
        alerts.append({
            "type": "cross_source_momentum",
            "severity": "medium",
            "confidence": "medium",
            "label": "Cross-source momentum detected",
            "evidence": f"{len(source_breakdown)} source types are contributing to this attention signal.",
            "period": latest_period,
            "priority": 70,
        })

    return sorted(
        alerts,
        key=lambda item: (
            -int(item["priority"]),
            str(item.get("type")),
        ),
    )[:5]


def _extract_observations(attributes_json: str | None) -> list[dict[str, Any]]:
    if not attributes_json:
        return []
    try:
        attrs = json.loads(attributes_json)
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(attrs, dict):
        return []

    raw = (
        attrs.get("external_attention_observations")
        or attrs.get("external_attention")
        or attrs.get("attention_observations")
    )
    if isinstance(raw, dict):
        raw = raw.get("observations") or raw.get("mentions") or []
    if not isinstance(raw, list):
        return []

    return [item for item in raw if isinstance(item, dict)]


def _normalize_source_type(raw: Any) -> str:
    if not isinstance(raw, str):
        return "other"
    source_type = raw.strip().lower().replace("-", "_")
    return source_type if source_type in VALID_SOURCE_TYPES else "other"


def _coerce_mentions(observation: dict[str, Any]) -> int:
    value = (
        observation.get("mention_count")
        or observation.get("mentions")
        or observation.get("count")
        or 1
    )
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 1


def _parse_datetime(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    value = raw.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _recency_multiplier(last_seen: datetime | None, now: datetime) -> float:
    if last_seen is None:
        return 0.75
    age_days = max(0, (now - last_seen).days)
    if age_days <= 30:
        return 1.2
    if age_days <= 180:
        return 1.0
    if age_days <= 730:
        return 0.75
    return 0.5
