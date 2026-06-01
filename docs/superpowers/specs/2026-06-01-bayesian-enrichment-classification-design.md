# Bayesian Enrichment Classification — Design Spec

**Date:** 2026-06-01
**Status:** Draft for planning
**Owner:** Platform / Enrichment / Authority
**Type:** Backend intelligence layer, explainable probabilistic scoring, enrichment sentinel observability

---

## 1. Problem Statement

UKIP already has a strong enrichment and authority pipeline, but many decisions are still driven by
fixed heuristics:

- which enrichment provider should run first
- whether a record has enough evidence to enrich
- whether the likely entity type is publication, author, institution, concept, dataset, etc.
- whether a provider result should be considered strong, weak, ambiguous, or NIL
- whether enriched evidence should influence authority review, researcher analytics, or quality scoring

These decisions are currently spread across modules as local rules. That makes them useful but harder to
calibrate, explain, compare, and reuse across the platform.

We want a lightweight probabilistic layer that improves decision quality without introducing deep learning
complexity, heavy dependencies, or opaque behavior.

## 2. Proposal

Introduce a **Bayesian Enrichment Classifier**: an explainable scoring service that combines prior
probabilities with observed evidence from each record and each enrichment result.

Add a companion capability called **UKIP Enrichment Sentinel**: a governed monitoring and calibration
layer that watches Bayesian outputs, enrichment events, provider behavior, authority outcomes, and reviewer
feedback to detect drift, weak evidence, recurring NIL patterns, and calibration opportunities.

The classifier should not replace the current enrichment pipeline. It should produce additional signals:

- `entity_type_probabilities`
- `provider_recommendations`
- `enrichment_confidence`
- `nil_probability`
- `promotion_readiness`
- `evidence_explanation`

The Sentinel should not act as an autonomous pipeline controller in the first delivery. It should produce
diagnostics, alerts, review priorities, and calibration proposals that can be approved by humans or promoted
through later feature flags.

Initial implementation should use a Naive Bayes / Bayesian scoring approach with configurable priors and
likelihood tables. No neural model training is required in the first delivery.

## 3. Goals

- G1. Improve enrichment provider selection using explainable probabilities.
- G2. Estimate likely entity type before and after enrichment.
- G3. Estimate confidence that an enrichment result is correct enough for downstream use.
- G4. Add a reusable probabilistic signal for authority resolution, quality score, researcher analytics,
  mapping suggestions, and dashboards.
- G5. Keep the implementation dependency-light, auditable, tenant-aware, and safe by default.
- G6. Provide a path to later calibration from reviewer feedback without requiring ML infrastructure now.
- G7. Add continuous enrichment observability through UKIP Enrichment Sentinel.
- G8. Detect provider drift, confidence degradation, repeated NIL causes, and calibration candidates.
- G9. Integrate Sentinel outputs with review queues, dashboards, audit logs, and future governance workflows.

## 4. Non-Goals

- Training a deep learning model.
- Adding `torch`, `tensorflow`, `sklearn`, or a model-serving stack.
- Replacing RAG, LLMs, authority scoring, or provider-specific enrichment logic.
- Automatically promoting records to canonical/authority layers solely because of Bayesian confidence.
- Using Bayesian outputs as irreversible decisions in the first phase.
- Allowing Sentinel to automatically disable providers, rewrite priors, or change thresholds without review.
- Building a fully autonomous enrichment agent in the initial implementation.

## 5. Current Architecture Context

| Concern | Current location |
|---|---|
| Enrichment worker/provider cascade | `backend/enrichment_worker.py` |
| Enrichment adapters | `backend/adapters/enrichment/` |
| Scientific import adapters | `backend/importers/scientific/` |
| Authority scoring | `backend/authority/scoring.py` |
| NIL detection | `backend/authority/nil_detection.py` |
| Field profiling / semantic roles | `backend/services/source_profiler.py` |
| Mapping suggestions | `backend/services/mapping_suggestions.py` |
| Researcher by topic analytics | `backend/services/researcher_topic_analytics.py` |
| Quality / derived status | `backend/quality_scorer.py`, `backend/services/derived_status_service.py` |
| Existing optional AI/RAG | `backend/analytics/rag_engine.py`, `backend/analytics/vector_store.py` |
| Telemetry / ops checks | `backend/telemetry.py`, `backend/ops_checks.py` |
| Audit trail | `backend/audit.py` |

The Bayesian classifier should sit below these modules as a shared service, not as another isolated
heuristic inside a router.

UKIP Enrichment Sentinel should sit beside the classifier as an observability and calibration service. It
should consume events from enrichment, classification, authority, quality scoring, and reviewer feedback.

## 6. Conceptual Model

```text
raw/imported record
  -> feature extraction
  -> Bayesian prior selection
  -> evidence likelihood scoring
  -> posterior probabilities
  -> recommendation/explanation payload
  -> enrichment + authority + analytics consumers
```

Sentinel side channel:

```text
bayesian outputs + enrichment attempts + provider health + authority outcomes + reviewer feedback
  -> UKIP Enrichment Sentinel
  -> findings + drift alerts + calibration proposals + review priorities
  -> dashboards + audit + governed configuration updates
```

Core equation, expressed operationally:

```text
posterior(class | evidence) proportional to
  prior(class | domain, source, tenant)
  * likelihood(feature_1 | class)
  * likelihood(feature_2 | class)
  * ...
```

For implementation, use log probabilities to avoid underflow:

```text
log_score(class) =
  log_prior(class)
  + sum(log_likelihood(feature=value | class))
```

Then normalize with softmax into probabilities.

## 7. Classification Targets

### 7.1 Entity Type Classification

Estimate:

- `publication`
- `author`
- `institution`
- `concept`
- `dataset`
- `funding`
- `venue`
- `unknown`

Example evidence:

- DOI present
- ORCID present
- ROR/OpenAlex institution ID present
- title-like field present
- author list present
- abstract length
- journal/venue present
- affiliation string present
- year present
- citation count present
- source provider
- file/import format
- domain id

### 7.2 Provider Recommendation

Estimate likely usefulness of each provider for a record:

- OpenAlex
- Crossref
- PubMed
- Semantic Scholar
- ORCID
- ROR/OpenAlex institutions
- Scopus/WoS when configured

Output:

```json
{
  "provider": "openalex",
  "probability_of_useful_match": 0.84,
  "recommended": true,
  "reasons": ["doi_present", "publication_like_record", "scientific_domain"]
}
```

### 7.3 Enrichment Result Confidence

After provider results return, score the probability that a candidate is valid:

- exact identifier match
- title similarity
- year compatibility
- author overlap
- institution/affiliation overlap
- DOI/ORCID/ROR match
- provider prior reliability
- conflicting evidence

Output should complement, not replace, existing authority scoring.

### 7.4 NIL Probability

Estimate whether a record is likely unresolved because:

- insufficient fields
- unsupported entity type
- provider coverage gap
- ambiguous candidates
- conflicting evidence

This should integrate naturally with the explicit NIL layer.

## 8. Proposed Files

New backend package:

- `backend/bayesian/__init__.py`
- `backend/bayesian/features.py`
- `backend/bayesian/priors.py`
- `backend/bayesian/classifier.py`
- `backend/bayesian/explanations.py`
- `backend/bayesian/calibration.py`
- `backend/bayesian/sentinel.py`
- `backend/bayesian/monitoring.py`

New config:

- `backend/domains/default.yaml` extension for Bayesian priors
- optional domain overrides in `backend/domains/science.yaml`, `healthcare.yaml`

New tests:

- `backend/tests/test_bayesian_features.py`
- `backend/tests/test_bayesian_classifier.py`
- `backend/tests/test_bayesian_enrichment_integration.py`
- `backend/tests/test_enrichment_sentinel.py`

Optional later:

- `backend/bayesian/feedback.py`
- `backend/tests/test_bayesian_feedback_calibration.py`

## 9. Data Contracts

### 9.1 Feature Vector

Internal representation:

```python
BayesianFeatureVector = {
    "domain_id": "science",
    "source_type": "scientific_import",
    "file_format": "ris",
    "has_doi": True,
    "has_orcid": False,
    "has_title": True,
    "has_abstract": True,
    "abstract_length_bucket": "long",
    "has_authors": True,
    "has_affiliation": True,
    "has_year": True,
    "has_citation_count": False,
    "identifier_density": "medium",
}
```

The feature extractor must be deterministic and side-effect free.

### 9.2 Classification Result

```json
{
  "model_version": "bayesian-enrichment-classifier-v1",
  "entity_type_probabilities": {
    "publication": 0.91,
    "dataset": 0.04,
    "concept": 0.03,
    "unknown": 0.02
  },
  "provider_recommendations": [
    {
      "provider": "crossref",
      "probability_of_useful_match": 0.88,
      "recommended": true,
      "reasons": ["doi_present", "publication_like_record"]
    }
  ],
  "enrichment_confidence": 0.82,
  "nil_probability": 0.08,
  "promotion_readiness": "review",
  "evidence": [
    "has_doi:+0.42 publication",
    "has_authors:+0.23 publication",
    "abstract_length_bucket=long:+0.11 publication"
  ]
}
```

### 9.3 Persistence

Avoid schema churn at first. Persist the output into `RawEntity.attributes_json` under:

```json
{
  "bayesian_enrichment": {
    "model_version": "bayesian-enrichment-classifier-v1",
    "computed_at": "2026-06-01T00:00:00Z",
    "...": "..."
  }
}
```

Later, if analytics require querying at scale, promote selected fields into columns or a dedicated
`BayesianClassificationResult` table.

### 9.4 Sentinel Finding

Sentinel findings should be structured, explainable, and reviewable.

```json
{
  "id": "sentinel-find-20260601-0001",
  "model_version": "ukip-enrichment-sentinel-v1",
  "severity": "medium",
  "scope": {
    "tenant_id": "tenant_123",
    "domain_id": "science",
    "provider": "openalex"
  },
  "signal_type": "provider_drift",
  "title": "OpenAlex useful-match probability is declining for DOI-rich records",
  "explanation": "Provider success fell below the expected Bayesian recommendation band for the last 500 records.",
  "evidence": {
    "expected_success_rate": 0.82,
    "observed_success_rate": 0.61,
    "window_size": 500,
    "nil_increase": 0.14
  },
  "recommended_actions": [
    "review provider credentials and rate limits",
    "inspect recent NIL reasons",
    "evaluate temporary provider reordering"
  ],
  "status": "open",
  "created_at": "2026-06-01T00:00:00Z"
}
```

### 9.5 Calibration Proposal

Calibration proposals should be separate from findings because they imply a possible behavior change.

```json
{
  "id": "calibration-proposal-20260601-0001",
  "target": "bayesian_enrichment.provider_priors.openalex.science",
  "current_value": 0.84,
  "proposed_value": 0.76,
  "reason": "Observed useful-match rate has been consistently lower than expected for the configured domain.",
  "expected_impact": "Reduce over-prioritization of OpenAlex for ambiguous publication-like records.",
  "confidence": 0.71,
  "requires_approval": true,
  "status": "proposed"
}
```

## 10. Integration Points

### 10.1 Enrichment Worker

Add a pre-enrichment decision point:

1. Extract features from `RawEntity`.
2. Compute Bayesian entity type probabilities and provider recommendations.
3. Use recommendations to order or skip provider attempts when safe.
4. Preserve current fallback cascade if classifier confidence is low.

Initial safe rule:

- If classifier confidence is low, use the existing cascade unchanged.
- If a provider is strongly recommended, try it earlier.
- Do not completely skip a configured provider in Phase 1 unless explicitly enabled by flag.

Feature flag:

- `UKIP_ENABLE_BAYESIAN_ENRICHMENT=1`

### 10.2 Authority Resolution

Use Bayesian confidence as an optional prior:

- entity type hint
- NIL probability
- candidate confidence support
- source reliability prior

Do not let it override exact identifiers.

### 10.3 Mapping Suggestions

Feed field-profile evidence into Bayesian features:

- semantic role candidates
- identifier density
- source format
- sample value patterns

Use output to improve automatic field mapping confidence.

### 10.4 Researcher Analytics

Use Bayesian result quality to explain lower confidence:

- weak enrichment confidence
- ambiguous entity type
- NIL probability high
- insufficient identifiers

This can strengthen `/analytics/researchers` without adding ML-heavy behavior.

### 10.5 Quality Score / Derived Status

Add Bayesian evidence to quality score inputs:

- high enrichment confidence increases readiness
- high NIL probability lowers readiness
- ambiguous entity type marks review state

### 10.6 UKIP Enrichment Sentinel

Sentinel should observe the enrichment lifecycle and generate governed recommendations.

Inputs:

- Bayesian classification results.
- Enrichment provider attempts, responses, errors, latency, and rate-limit events.
- Provider recommendation versus actual provider outcome.
- NIL decisions and NIL reasons.
- Authority match outcomes.
- Quality score and derived status changes.
- Reviewer confirmations, corrections, and rejections.

Outputs:

- `sentinel_findings` for drift, weak evidence, ambiguous records, repeated failure modes, and provider issues.
- `calibration_proposals` for priors, likelihoods, thresholds, and provider reliability adjustments.
- `review_priorities` for records that need human attention before promotion.
- `provider_health_summary` for operational dashboards.

Initial safe behavior:

- Read-only by default.
- No automatic provider disabling.
- No automatic prior or threshold changes.
- No automatic authority promotion.
- All proposed calibration changes require explicit approval.

Feature flag:

- `UKIP_ENABLE_ENRICHMENT_SENTINEL=1`

Possible persistence strategy:

- Phase 1: persist compact findings in audit/log/event storage and selected `attributes_json` metadata.
- Later: introduce queryable tables such as `enrichment_sentinel_findings` and
  `enrichment_calibration_proposals` if dashboards or historical analysis require it.

## 11. Priors and Likelihood Configuration

Initial config should be YAML, not code-only.

Example:

```yaml
bayesian_enrichment:
  model_version: bayesian-enrichment-classifier-v1
  priors:
    entity_type:
      publication: 0.45
      author: 0.15
      institution: 0.15
      concept: 0.10
      dataset: 0.05
      funding: 0.03
      venue: 0.03
      unknown: 0.04
  likelihoods:
    has_doi:
      publication: 0.92
      dataset: 0.25
      unknown: 0.05
    has_orcid:
      author: 0.95
      publication: 0.10
      unknown: 0.03
    has_ror:
      institution: 0.90
      unknown: 0.03
```

Rules:

- All probabilities must be clamped to `[0.001, 0.999]`.
- Missing likelihoods use a neutral value (`0.5`) or a configured smoothing parameter.
- Domain-specific configs override default priors but inherit unspecified likelihoods.

## 12. Explainability Requirements

Every classification must include:

- top class
- probability
- top positive evidence
- top negative/conflicting evidence where available
- model version
- config source

This is essential because the classifier will be used in governance-sensitive flows.

Every Sentinel finding must include:

- observed signal
- expected baseline
- evidence window
- severity
- affected scope
- recommended action
- whether the action is informational, review-only, or calibration-related

## 13. Safety and Governance

- Default off behind `UKIP_ENABLE_BAYESIAN_ENRICHMENT`.
- Phase 1 is advisory only.
- Never auto-promote canonical or authority records solely from Bayesian confidence.
- Persist model version with every result.
- Add audit log when classification affects provider order or review routing.
- Tenant overrides must not leak across orgs.
- Sentinel is advisory in the first release.
- Sentinel calibration proposals require human approval before changing runtime behavior.
- Sentinel findings should be auditable and dismissible with a reason.
- Critical provider-health findings may trigger notifications, but not automatic provider shutdown in Phase 1.

## 14. Rollout Plan

### Phase 0 — Spec and Baseline

- Document design.
- Identify existing feature sources.
- Define default YAML priors.
- Define quality metrics and fixtures.

### Phase 1 — Advisory Classifier

- Implement feature extraction.
- Implement Bayesian scorer.
- Add tests for deterministic output.
- Add endpoint or service method for dry-run classification.
- Persist advisory result only when explicitly invoked.

### Phase 1.5 — Advisory Sentinel

- Implement Sentinel finding generation from stored or in-process enrichment events.
- Add provider health and confidence drift checks.
- Generate review-only findings and calibration proposals.
- Persist findings in audit/event storage or a minimal internal store.
- Add tests for drift detection, repeated NIL patterns, and proposal generation.

### Phase 2 — Enrichment Integration

- Add feature flag.
- Use provider recommendation to reorder provider cascade.
- Persist classification result during enrichment.
- Add audit evidence to enrichment result.
- Feed enrichment outcomes into Sentinel monitoring.

### Phase 3 — Cross-Module Integration

- Feed outputs into authority NIL/readiness.
- Add quality score input.
- Surface evidence in review UIs.
- Add researcher analytics caveats.
- Surface Sentinel findings in dashboards and review workflows.
- Add provider health summaries to operational views.

### Phase 4 — Calibration From Feedback

- Aggregate reviewer outcomes.
- Update priors or source reliability adjustments.
- Keep caps on learned adjustments.
- Add regression tests against known fixture outcomes.
- Convert approved Sentinel calibration proposals into versioned config changes.
- Track before/after calibration impact.

## 15. Evaluation Metrics

Initial offline metrics:

- entity type accuracy on fixture records
- provider recommendation precision
- provider recommendation recall
- reduction in unnecessary provider calls
- enrichment success rate
- NIL false positive / false negative rate
- explanation completeness
- Sentinel drift detection precision
- calibration proposal acceptance rate

Operational metrics:

- provider attempts per enriched record
- average enrichment latency
- successful enrichment ratio
- review queue ambiguity rate
- downstream authority confirmation rate
- provider drift alert count by severity
- time from Sentinel finding to review/closure
- calibration impact on enrichment success and unnecessary provider calls

## 16. Test Plan

### Unit Tests

- feature extractor handles missing / malformed JSON
- DOI/ORCID/ROR/year/author evidence detection
- priors normalize correctly
- likelihood smoothing prevents zero-probability collapse
- posterior probabilities sum to 1
- explanations include top evidence

### Integration Tests

- classifier produces advisory output for raw entity
- enrichment worker reorders providers only when flag is enabled
- low confidence falls back to existing cascade
- classification result persists in `attributes_json`
- tenant-scoped config override applies only to that org/domain
- Sentinel emits advisory findings when provider outcomes deviate from Bayesian expectations
- Sentinel does not mutate runtime config without approval

### Regression Tests

- fixture set with known entity types
- fixture set with known provider recommendations
- exact DOI record still recommends publication providers
- ORCID-only person-like record does not route primarily to Crossref
- sparse record produces high `unknown` / review readiness
- repeated provider failures produce a Sentinel provider-health finding
- accepted calibration proposal changes are versioned and reversible

## 17. Acceptance Criteria

- [ ] Bayesian classifier exists as a reusable backend service.
- [ ] Feature extraction is deterministic and tested.
- [ ] Default priors/likelihoods are configurable.
- [ ] Advisory classification result includes probabilities and explanation.
- [ ] Enrichment integration is gated by feature flag.
- [ ] Existing enrichment behavior remains unchanged when the flag is off.
- [ ] No heavy ML/DL dependency is introduced.
- [ ] Classification result can be consumed by authority, quality, and analytics modules.
- [ ] Tests cover baseline classification, fallback, persistence, and provider recommendation.
- [ ] Documentation clearly states advisory-only behavior in the first release.
- [ ] UKIP Enrichment Sentinel can generate advisory findings from enrichment outcomes.
- [ ] Sentinel calibration proposals are structured, explainable, and approval-gated.
- [ ] Sentinel cannot disable providers or change priors automatically in the first release.

## 18. Open Questions

- Should priors be global/domain-level only, or should tenants eventually tune them?
- Which provider success/failure events should be stored for calibration?
- Should Bayesian outputs live only in `attributes_json`, or should we introduce a queryable table earlier?
- What minimum labeled fixture set is acceptable before using provider reordering in production?
- Should review feedback calibrate class priors, provider priors, or both?
- Should Sentinel findings live in the audit/event stream first, or in dedicated tables from day one?
- What severity thresholds should trigger notifications versus passive dashboard findings?
- Who can approve calibration proposals: platform admins only, domain admins, or both?

## 19. Recommended First Implementation Slice

Start with a minimal, safe slice:

1. `features.py` extracts evidence from `RawEntity`.
2. `classifier.py` computes entity type probabilities.
3. `priors.py` loads default/domain YAML priors.
4. `explanations.py` generates top evidence.
5. Tests validate deterministic behavior.

Then integrate with enrichment provider ordering only after we have baseline fixtures and metrics.

Sentinel first slice:

1. `sentinel.py` evaluates recent enrichment outcomes against Bayesian expectations.
2. `monitoring.py` computes provider health, NIL-pattern, and confidence-drift signals.
3. Findings are generated as advisory objects only.
4. Calibration proposals are emitted but not applied.
5. Tests confirm Sentinel remains read-only unless a later approved workflow is added.
