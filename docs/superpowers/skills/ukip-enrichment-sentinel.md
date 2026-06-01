# UKIP Enrichment Sentinel Skill

**Status:** Draft / installed locally
**Local skill path:** `C:/Users/Jose Paul/.codex/skills/ukip-enrichment-sentinel`
**Purpose:** Provide a specialized AI Assistant workflow for enrichment observability, Bayesian calibration, provider health, NIL patterns, authority readiness, quality scoring, and researcher analytics signals.

## Activation Intent

Use this skill when working on UKIP tasks involving:

- enrichment pipeline analysis or implementation
- Bayesian enrichment classification
- provider ordering or provider health
- NIL detection and unresolved records
- authority scoring and readiness
- quality/derived status
- researcher analytics confidence caveats
- calibration proposals and governance

## Operating Model

The skill treats **UKIP Enrichment Sentinel** as an advisory layer first:

- observe enrichment outcomes
- detect weak evidence, provider drift, repeated NIL causes, and confidence degradation
- propose calibration changes
- prioritize review
- preserve human approval for behavior-changing actions

It should not automatically disable providers, update priors, rewrite thresholds, or promote records without explicit implementation work, feature flags, tests, and approval flow.

## Repo Context

Primary UKIP modules:

- `backend/enrichment_worker.py`
- `backend/adapters/enrichment/`
- `backend/authority/scoring.py`
- `backend/authority/nil_detection.py`
- `backend/services/source_profiler.py`
- `backend/services/mapping_suggestions.py`
- `backend/quality_scorer.py`
- `backend/services/derived_status_service.py`
- `backend/services/researcher_topic_analytics.py`
- `backend/analytics/rag_engine.py`
- `backend/analytics/vector_store.py`

Related spec:

- `docs/superpowers/specs/2026-06-01-bayesian-enrichment-classification-design.md`

## Expected Output Shape

For reviews:

```text
Finding:
Evidence:
Impact:
Recommended action:
Governance:
Validation:
```

For calibration proposals:

```text
Calibration proposal:
Target:
Current behavior:
Proposed behavior:
Reason:
Expected impact:
Approval requirement:
Rollback:
```

## Installation State

The local Codex skill has been initialized at:

```text
C:/Users/Jose Paul/.codex/skills/ukip-enrichment-sentinel
```

The local skill contains:

- `SKILL.md`
- `agents/openai.yaml`
- `references/sentinel-checklist.md`

This document is the repo-versioned source of intent for the skill. The local skill can evolve from here as we test it against real UKIP tasks.
