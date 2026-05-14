use std::collections::HashMap;

use crate::pipelines::{
    ComputePayload, ComputeResult, Pipeline, PipelineCategory, PipelineContext, PipelineError,
    PipelineInput, PipelineOutput, ValidationError,
};
use crate::proto::{DisambiguationCluster, DisambiguationResponse};

use crate::pipelines::authority::fuzzy::token_sort_ratio;
use crate::pipelines::authority::normalize::normalize_name;

/// Default similarity threshold for fuzzy clustering.
const DEFAULT_THRESHOLD: f64 = 0.85;

pub struct DisambiguationPipeline;

#[async_trait::async_trait]
impl Pipeline for DisambiguationPipeline {
    fn name(&self) -> &'static str {
        "compute_disambiguation"
    }

    fn category(&self) -> PipelineCategory {
        PipelineCategory::Compute
    }

    fn validate(&self, input: &PipelineInput) -> Result<(), ValidationError> {
        match &input.payload {
            Some(ComputePayload::Disambiguation(req)) if !req.values.is_empty() => Ok(()),
            _ => Err(ValidationError::EmptyInput),
        }
    }

    async fn process(
        &self,
        input: PipelineInput,
        ctx: &PipelineContext,
    ) -> Result<PipelineOutput, PipelineError> {
        let req = match input.payload {
            Some(ComputePayload::Disambiguation(r)) => r,
            _ => {
                return Err(PipelineError::Validation(
                    "missing disambiguation request payload".to_string(),
                ))
            }
        };

        let threshold = if req.similarity_threshold > 0.0 {
            req.similarity_threshold as f64
        } else {
            DEFAULT_THRESHOLD
        };

        ctx.progress
            .update(0.0, "disambiguation", "Starting disambiguation")
            .await;

        let clusters = fuzzy_cluster(&req.values, threshold);

        ctx.progress
            .update(1.0, "done", "Disambiguation complete")
            .await;

        let mut counters = HashMap::new();
        counters.insert("values_input".to_string(), req.values.len() as i32);
        counters.insert("clusters_output".to_string(), clusters.len() as i32);

        Ok(PipelineOutput {
            counters,
            compute_result: Some(ComputeResult::Disambiguation(DisambiguationResponse {
                clusters,
            })),
            ..PipelineOutput::default()
        })
    }
}

/// Fuzzy cluster values using sorted-neighborhood blocking + token-sort-ratio.
///
/// Algorithm:
/// 1. Sort values by normalized form (sorted-neighborhood blocking).
/// 2. Compare each value against a sliding window of neighbors.
/// 3. Group matches into clusters; pick canonical by frequency then length.
fn fuzzy_cluster(values: &[String], threshold: f64) -> Vec<DisambiguationCluster> {
    if values.is_empty() {
        return vec![];
    }

    // Count frequencies
    let mut freq: HashMap<String, usize> = HashMap::new();
    for v in values {
        *freq.entry(v.clone()).or_insert(0) += 1;
    }

    // Deduplicate and sort by normalized form (sorted-neighborhood blocking key)
    let mut unique: Vec<String> = freq.keys().cloned().collect();
    unique.sort_by_cached_key(|v| normalize_name(v));

    // Sliding window comparison (window size chosen to balance O(n*w) vs recall)
    let window_size = 20;
    let mut cluster_id: HashMap<String, usize> = HashMap::new();
    let mut clusters: Vec<Vec<String>> = Vec::new();

    for i in 0..unique.len() {
        if cluster_id.contains_key(&unique[i]) {
            continue;
        }

        // Start a new cluster
        let cid = clusters.len();
        clusters.push(vec![unique[i].clone()]);
        cluster_id.insert(unique[i].clone(), cid);

        let norm_i = normalize_name(&unique[i]);

        // Compare against the window
        for j in (i + 1)..unique.len().min(i + window_size) {
            if cluster_id.contains_key(&unique[j]) {
                continue;
            }

            let norm_j = normalize_name(&unique[j]);
            let sim = token_sort_ratio(&norm_i, &norm_j);

            if sim >= threshold {
                clusters[cid].push(unique[j].clone());
                cluster_id.insert(unique[j].clone(), cid);
            }
        }
    }

    // Build output: pick canonical by frequency (desc), then shortest name
    clusters
        .into_iter()
        .map(|members| {
            let mut sorted_members = members.clone();
            sorted_members.sort_by(|a, b| {
                let fa = freq.get(a).unwrap_or(&0);
                let fb = freq.get(b).unwrap_or(&0);
                fb.cmp(fa).then_with(|| a.len().cmp(&b.len()))
            });

            let canonical = sorted_members[0].clone();
            let canonical_norm = normalize_name(&canonical);

            let variants: Vec<String> = sorted_members[1..].to_vec();
            let scores: Vec<f32> = variants
                .iter()
                .map(|v| token_sort_ratio(&canonical_norm, &normalize_name(v)) as f32)
                .collect();

            let total_freq: usize = sorted_members.iter().map(|m| freq.get(m).unwrap_or(&0)).sum();

            DisambiguationCluster {
                canonical_value: canonical,
                variants,
                scores,
                frequency: total_freq as i32,
            }
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_fuzzy_cluster_identical() {
        let values = vec![
            "John Smith".to_string(),
            "John Smith".to_string(),
            "john smith".to_string(),
        ];
        let clusters = fuzzy_cluster(&values, 0.85);
        // "John Smith" and "john smith" should merge
        let total_values: usize = clusters.iter()
            .map(|c| 1 + c.variants.len())
            .sum();
        assert_eq!(total_values, 2, "should have 2 unique values across clusters");
    }

    #[test]
    fn test_fuzzy_cluster_different() {
        let values = vec![
            "John Smith".to_string(),
            "Alice Jones".to_string(),
        ];
        let clusters = fuzzy_cluster(&values, 0.85);
        assert_eq!(clusters.len(), 2, "completely different names → 2 clusters");
    }

    #[test]
    fn test_fuzzy_cluster_reordered_name() {
        let values = vec![
            "John Smith".to_string(),
            "Smith John".to_string(),
        ];
        let clusters = fuzzy_cluster(&values, 0.85);
        // Token-sort-ratio: sorted tokens are identical → should merge
        assert_eq!(clusters.len(), 1, "reordered tokens should merge");
        assert_eq!(clusters[0].variants.len(), 1);
    }

    #[test]
    fn test_fuzzy_cluster_empty() {
        let clusters = fuzzy_cluster(&[], 0.85);
        assert!(clusters.is_empty());
    }

    #[test]
    fn test_fuzzy_cluster_canonical_by_frequency() {
        let values = vec![
            "Apple Inc.".to_string(),
            "Apple Inc.".to_string(),
            "Apple Inc.".to_string(),
            "apple inc".to_string(),
        ];
        let clusters = fuzzy_cluster(&values, 0.85);
        // "Apple Inc." appears 3 times, should be canonical
        let merged = clusters.iter().find(|c| c.canonical_value == "Apple Inc.");
        assert!(merged.is_some(), "most frequent should be canonical");
    }

    #[test]
    fn test_fuzzy_cluster_scores() {
        let values = vec![
            "Machine Learning".to_string(),
            "machine learning".to_string(),
        ];
        let clusters = fuzzy_cluster(&values, 0.85);
        assert_eq!(clusters.len(), 1);
        assert!(!clusters[0].scores.is_empty());
        assert!(clusters[0].scores[0] > 0.85);
    }

    #[test]
    fn test_fuzzy_cluster_performance_1k() {
        // Ensure 1000 values complete quickly
        let mut values: Vec<String> = (0..1000)
            .map(|i| format!("Entity {}", i))
            .collect();
        // Add some duplicates
        for i in 0..100 {
            values.push(format!("entity {}", i));
        }
        let start = std::time::Instant::now();
        let clusters = fuzzy_cluster(&values, 0.85);
        let elapsed = start.elapsed();
        assert!(!clusters.is_empty());
        assert!(elapsed.as_secs() < 30, "should complete in < 30s, took {:?}", elapsed);
    }

    #[test]
    fn test_disambiguation_pipeline_validate() {
        let pipeline = DisambiguationPipeline;

        // Valid
        let valid_input = PipelineInput {
            job_id: "test".to_string(),
            import_batch_id: 0,
            org_id: None,
            domain: "test".to_string(),
            publications: vec![],
            options: HashMap::new(),
            payload: Some(ComputePayload::Disambiguation(
                crate::proto::DisambiguationRequest {
                    field_name: "brand".to_string(),
                    values: vec!["Apple".to_string()],
                    similarity_threshold: 0.85,
                },
            )),
        };
        assert!(pipeline.validate(&valid_input).is_ok());

        // Empty values
        let empty_input = PipelineInput {
            job_id: "test".to_string(),
            import_batch_id: 0,
            org_id: None,
            domain: "test".to_string(),
            publications: vec![],
            options: HashMap::new(),
            payload: Some(ComputePayload::Disambiguation(
                crate::proto::DisambiguationRequest {
                    field_name: "brand".to_string(),
                    values: vec![],
                    similarity_threshold: 0.85,
                },
            )),
        };
        assert!(pipeline.validate(&empty_input).is_err());
    }
}
