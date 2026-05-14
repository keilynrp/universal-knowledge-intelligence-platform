pub mod fuzzy;
pub mod normalize;
pub mod scoring;

use std::collections::HashMap;

use crate::pipelines::{
    ComputePayload, ComputeResult, Pipeline, PipelineCategory, PipelineContext, PipelineError,
    PipelineInput, PipelineOutput, ValidationError,
};
use crate::proto::{
    AuthorityCandidate, AuthorityCandidateGroup, AuthorityResponse,
};

use self::fuzzy::token_sort_ratio;
use self::normalize::normalize_name;

/// Merge threshold: candidates with token-sort-ratio >= 0.92 are considered
/// the same entity from different sources.
const MERGE_THRESHOLD: f64 = 0.92;

pub struct AuthorityPipeline;

#[async_trait::async_trait]
impl Pipeline for AuthorityPipeline {
    fn name(&self) -> &'static str {
        "compute_authority"
    }

    fn category(&self) -> PipelineCategory {
        PipelineCategory::Compute
    }

    fn validate(&self, input: &PipelineInput) -> Result<(), ValidationError> {
        match &input.payload {
            Some(ComputePayload::Authority(req)) if !req.values.is_empty() => Ok(()),
            _ => Err(ValidationError::EmptyInput),
        }
    }

    async fn process(
        &self,
        input: PipelineInput,
        ctx: &PipelineContext,
    ) -> Result<PipelineOutput, PipelineError> {
        let req = match input.payload {
            Some(ComputePayload::Authority(r)) => r,
            _ => {
                return Err(PipelineError::Validation(
                    "missing authority request payload".to_string(),
                ))
            }
        };

        ctx.progress
            .update(0.0, "authority", "Starting authority resolution")
            .await;

        let mut groups = Vec::new();
        let total = req.values.len() as f32;

        for (i, value) in req.values.iter().enumerate() {
            // In a full implementation, we would query external authority sources here.
            // For now, the pipeline processes pre-fetched candidates passed via options,
            // or generates self-referential candidates for scoring demonstration.
            let candidates = resolve_value(
                value,
                &req.entity_type,
                req.context_affiliation.as_deref(),
                req.context_orcid_hint.as_deref(),
                req.context_doi.as_deref(),
            );

            let deduped = deduplicate_candidates(candidates);

            groups.push(AuthorityCandidateGroup {
                original_value: value.clone(),
                candidates: deduped,
            });

            if i % 10 == 0 {
                let progress = (i as f32 + 1.0) / total;
                ctx.progress
                    .update(progress, "authority", &format!("Resolved {}/{}", i + 1, total as usize))
                    .await;
            }
        }

        ctx.progress
            .update(1.0, "done", "Authority resolution complete")
            .await;

        let response = AuthorityResponse { groups };

        let mut counters = HashMap::new();
        counters.insert("values_processed".to_string(), req.values.len() as i32);
        counters.insert(
            "candidates_total".to_string(),
            response
                .groups
                .iter()
                .map(|g| g.candidates.len() as i32)
                .sum(),
        );

        Ok(PipelineOutput {
            counters,
            compute_result: Some(ComputeResult::Authority(response)),
            ..PipelineOutput::default()
        })
    }
}

/// Resolve a single value against authority sources.
/// In a full implementation, this would call external APIs.
/// For now, it generates a scored self-candidate.
fn resolve_value(
    value: &str,
    _entity_type: &str,
    affiliation: Option<&str>,
    orcid_hint: Option<&str>,
    _doi: Option<&str>,
) -> Vec<AuthorityCandidate> {
    // This is a placeholder — the real implementation would query Wikidata, VIAF, ORCID etc.
    // The scoring engine is fully functional and will be used when external resolvers are integrated.
    let result = scoring::compute_score(
        value,
        "openalex",
        &format!("A{:x}", fxhash(value)),
        value,
        None,
        orcid_hint,
        affiliation,
    );

    vec![AuthorityCandidate {
        source: "openalex".to_string(),
        authority_id: format!("A{:x}", fxhash(value)),
        canonical_label: value.to_string(),
        confidence: result.total as f32,
        score_breakdown: result
            .breakdown
            .into_iter()
            .map(|(k, v)| (k, v as f32))
            .collect(),
        resolution_status: result.resolution_status,
        merged_sources: vec![],
        aliases: vec![],
        uri: None,
        description: None,
    }]
}

/// Simple hash for generating deterministic IDs.
fn fxhash(s: &str) -> u64 {
    s.bytes().fold(0u64, |h, b| {
        h.wrapping_mul(0x100000001b3).wrapping_add(b as u64)
    })
}

/// Cross-source candidate deduplication.
/// Merges candidates whose normalized labels have token-sort-ratio >= MERGE_THRESHOLD.
fn deduplicate_candidates(mut candidates: Vec<AuthorityCandidate>) -> Vec<AuthorityCandidate> {
    if candidates.len() <= 1 {
        return candidates;
    }

    // Sort by confidence descending so the best candidate is kept as primary.
    candidates.sort_by(|a, b| b.confidence.partial_cmp(&a.confidence).unwrap_or(std::cmp::Ordering::Equal));

    let mut merged: Vec<AuthorityCandidate> = Vec::new();

    for candidate in candidates {
        let norm_label = normalize_name(&candidate.canonical_label);
        let mut found_merge = false;

        for existing in &mut merged {
            let existing_norm = normalize_name(&existing.canonical_label);
            let similarity = token_sort_ratio(&norm_label, &existing_norm);

            if similarity >= MERGE_THRESHOLD {
                // Merge: keep highest confidence, track merged sources
                if !existing.merged_sources.contains(&candidate.source) {
                    existing.merged_sources.push(candidate.source.clone());
                }
                // Merge aliases
                if !existing.aliases.contains(&candidate.canonical_label)
                    && candidate.canonical_label != existing.canonical_label
                {
                    existing.aliases.push(candidate.canonical_label.clone());
                }
                found_merge = true;
                break;
            }
        }

        if !found_merge {
            merged.push(candidate);
        }
    }

    merged
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_deduplicate_identical() {
        let candidates = vec![
            AuthorityCandidate {
                source: "orcid".to_string(),
                authority_id: "0000-0001".to_string(),
                canonical_label: "John Smith".to_string(),
                confidence: 0.95,
                score_breakdown: HashMap::new(),
                resolution_status: "exact_match".to_string(),
                merged_sources: vec![],
                aliases: vec![],
                uri: None,
                description: None,
            },
            AuthorityCandidate {
                source: "openalex".to_string(),
                authority_id: "A123".to_string(),
                canonical_label: "John Smith".to_string(),
                confidence: 0.80,
                score_breakdown: HashMap::new(),
                resolution_status: "probable_match".to_string(),
                merged_sources: vec![],
                aliases: vec![],
                uri: None,
                description: None,
            },
        ];

        let result = deduplicate_candidates(candidates);
        assert_eq!(result.len(), 1, "should merge identical names");
        assert_eq!(result[0].confidence, 0.95, "should keep highest confidence");
        assert!(result[0].merged_sources.contains(&"openalex".to_string()));
    }

    #[test]
    fn test_deduplicate_different() {
        let candidates = vec![
            AuthorityCandidate {
                source: "orcid".to_string(),
                authority_id: "0000-0001".to_string(),
                canonical_label: "John Smith".to_string(),
                confidence: 0.90,
                score_breakdown: HashMap::new(),
                resolution_status: "exact_match".to_string(),
                merged_sources: vec![],
                aliases: vec![],
                uri: None,
                description: None,
            },
            AuthorityCandidate {
                source: "openalex".to_string(),
                authority_id: "A456".to_string(),
                canonical_label: "Alice Jones".to_string(),
                confidence: 0.85,
                score_breakdown: HashMap::new(),
                resolution_status: "exact_match".to_string(),
                merged_sources: vec![],
                aliases: vec![],
                uri: None,
                description: None,
            },
        ];

        let result = deduplicate_candidates(candidates);
        assert_eq!(result.len(), 2, "should not merge different names");
    }

    #[test]
    fn test_deduplicate_near_match() {
        let candidates = vec![
            AuthorityCandidate {
                source: "viaf".to_string(),
                authority_id: "V1".to_string(),
                canonical_label: "Smith, John".to_string(),
                confidence: 0.70,
                score_breakdown: HashMap::new(),
                resolution_status: "probable_match".to_string(),
                merged_sources: vec![],
                aliases: vec![],
                uri: None,
                description: None,
            },
            AuthorityCandidate {
                source: "orcid".to_string(),
                authority_id: "0000-0001".to_string(),
                canonical_label: "John Smith".to_string(),
                confidence: 0.90,
                score_breakdown: HashMap::new(),
                resolution_status: "exact_match".to_string(),
                merged_sources: vec![],
                aliases: vec![],
                uri: None,
                description: None,
            },
        ];

        let result = deduplicate_candidates(candidates);
        // "smith john" vs "john smith" → token_sort_ratio should be ~1.0 → merge
        assert_eq!(result.len(), 1, "should merge reordered names");
        assert_eq!(result[0].confidence, 0.90);
    }

    #[test]
    fn test_fxhash_deterministic() {
        assert_eq!(fxhash("hello"), fxhash("hello"));
        assert_ne!(fxhash("hello"), fxhash("world"));
    }

    #[test]
    fn test_deduplicate_single_candidate() {
        let candidates = vec![AuthorityCandidate {
            source: "orcid".to_string(),
            authority_id: "0000-0001".to_string(),
            canonical_label: "John Smith".to_string(),
            confidence: 0.90,
            score_breakdown: HashMap::new(),
            resolution_status: "exact_match".to_string(),
            merged_sources: vec![],
            aliases: vec![],
            uri: None,
            description: None,
        }];
        let result = deduplicate_candidates(candidates);
        assert_eq!(result.len(), 1);
        assert!(result[0].merged_sources.is_empty());
    }

    #[test]
    fn test_deduplicate_empty() {
        let result = deduplicate_candidates(vec![]);
        assert!(result.is_empty());
    }

    #[test]
    fn test_deduplicate_three_sources_merge() {
        let candidates = vec![
            AuthorityCandidate {
                source: "orcid".to_string(),
                authority_id: "0000-0001".to_string(),
                canonical_label: "John Smith".to_string(),
                confidence: 0.95,
                score_breakdown: HashMap::new(),
                resolution_status: "exact_match".to_string(),
                merged_sources: vec![],
                aliases: vec![],
                uri: None,
                description: None,
            },
            AuthorityCandidate {
                source: "viaf".to_string(),
                authority_id: "V1".to_string(),
                canonical_label: "Smith, John".to_string(),
                confidence: 0.70,
                score_breakdown: HashMap::new(),
                resolution_status: "probable_match".to_string(),
                merged_sources: vec![],
                aliases: vec![],
                uri: None,
                description: None,
            },
            AuthorityCandidate {
                source: "openalex".to_string(),
                authority_id: "A1".to_string(),
                canonical_label: "John Smith".to_string(),
                confidence: 0.80,
                score_breakdown: HashMap::new(),
                resolution_status: "probable_match".to_string(),
                merged_sources: vec![],
                aliases: vec![],
                uri: None,
                description: None,
            },
        ];

        let result = deduplicate_candidates(candidates);
        assert_eq!(result.len(), 1, "all three should merge");
        assert_eq!(result[0].confidence, 0.95, "highest confidence kept");
        assert_eq!(result[0].merged_sources.len(), 2);
        assert!(result[0].merged_sources.contains(&"viaf".to_string()));
        assert!(result[0].merged_sources.contains(&"openalex".to_string()));
    }

    #[test]
    fn test_deduplicate_preserves_aliases() {
        let candidates = vec![
            AuthorityCandidate {
                source: "orcid".to_string(),
                authority_id: "0000-0001".to_string(),
                canonical_label: "John Smith".to_string(),
                confidence: 0.95,
                score_breakdown: HashMap::new(),
                resolution_status: "exact_match".to_string(),
                merged_sources: vec![],
                aliases: vec![],
                uri: None,
                description: None,
            },
            AuthorityCandidate {
                source: "viaf".to_string(),
                authority_id: "V1".to_string(),
                canonical_label: "Smith, John".to_string(),
                confidence: 0.60,
                score_breakdown: HashMap::new(),
                resolution_status: "probable_match".to_string(),
                merged_sources: vec![],
                aliases: vec![],
                uri: None,
                description: None,
            },
        ];

        let result = deduplicate_candidates(candidates);
        assert_eq!(result.len(), 1);
        assert!(result[0].aliases.contains(&"Smith, John".to_string()));
    }

    #[test]
    fn test_resolve_value_returns_scored_candidate() {
        let candidates = resolve_value("John Smith", "person", None, None, None);
        assert_eq!(candidates.len(), 1);
        assert_eq!(candidates[0].source, "openalex");
        assert!(!candidates[0].canonical_label.is_empty());
        assert!(candidates[0].confidence > 0.0);
        assert!(!candidates[0].resolution_status.is_empty());
    }

    #[test]
    fn test_resolve_value_with_orcid_hint() {
        let candidates = resolve_value(
            "John Smith",
            "person",
            None,
            Some("0000-0001-2345-6789"),
            None,
        );
        assert_eq!(candidates.len(), 1);
        // With orcid hint but source is openalex (not orcid), no special boost
        assert!(candidates[0].confidence > 0.0);
    }

    fn make_input(payload: Option<ComputePayload>) -> PipelineInput {
        PipelineInput {
            job_id: "test-job".to_string(),
            import_batch_id: 0,
            org_id: None,
            domain: "test".to_string(),
            publications: vec![],
            options: HashMap::new(),
            payload,
        }
    }

    #[test]
    fn test_authority_pipeline_validate_ok() {
        let pipeline = AuthorityPipeline;
        let req = crate::proto::AuthorityRequest {
            field_name: "author".to_string(),
            values: vec!["John Smith".to_string()],
            entity_type: "person".to_string(),
            context_affiliation: None,
            context_orcid_hint: None,
            context_doi: None,
            context_year: None,
        };
        let input = make_input(Some(ComputePayload::Authority(req)));
        assert!(pipeline.validate(&input).is_ok());
    }

    #[test]
    fn test_authority_pipeline_validate_empty_values() {
        let pipeline = AuthorityPipeline;
        let req = crate::proto::AuthorityRequest {
            field_name: "author".to_string(),
            values: vec![],
            entity_type: "person".to_string(),
            context_affiliation: None,
            context_orcid_hint: None,
            context_doi: None,
            context_year: None,
        };
        let input = make_input(Some(ComputePayload::Authority(req)));
        assert!(pipeline.validate(&input).is_err());
    }

    #[test]
    fn test_authority_pipeline_validate_no_payload() {
        let pipeline = AuthorityPipeline;
        let input = make_input(None);
        assert!(pipeline.validate(&input).is_err());
    }

    #[test]
    fn test_authority_pipeline_category() {
        let pipeline = AuthorityPipeline;
        assert_eq!(pipeline.category(), PipelineCategory::Compute);
    }

    #[test]
    fn test_authority_pipeline_name() {
        let pipeline = AuthorityPipeline;
        assert_eq!(pipeline.name(), "compute_authority");
    }
}
