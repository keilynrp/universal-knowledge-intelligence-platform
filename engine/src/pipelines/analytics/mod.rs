pub mod clustering;
pub mod correlation;
pub mod pmi;
pub mod topics;

use std::collections::HashMap;

use crate::pipelines::{
    ComputePayload, ComputeResult, Pipeline, PipelineCategory, PipelineContext, PipelineError,
    PipelineInput, PipelineOutput, ValidationError,
};
use crate::proto::{
    AnalyticsResponse, CooccurrencePair, CorrelationPair, TopicCluster, TopicEntry,
};

use self::clustering::topic_clusters;
use self::correlation::{top_correlations, CorrelationEntry};
use self::pmi::cooccurrence_pmi;
use self::topics::{parse_concepts, top_topics};

const VALID_MODES: &[&str] = &["topics", "cooccurrence", "clusters", "correlation"];

pub struct AnalyticsPipeline;

#[async_trait::async_trait]
impl Pipeline for AnalyticsPipeline {
    fn name(&self) -> &'static str {
        "compute_analytics"
    }

    fn category(&self) -> PipelineCategory {
        PipelineCategory::Compute
    }

    fn validate(&self, input: &PipelineInput) -> Result<(), ValidationError> {
        match &input.payload {
            Some(ComputePayload::Analytics(req)) => {
                if !VALID_MODES.contains(&req.mode.as_str()) {
                    return Err(ValidationError::InvalidField(format!(
                        "invalid mode '{}', expected one of: {:?}",
                        req.mode, VALID_MODES
                    )));
                }
                Ok(())
            }
            _ => Err(ValidationError::EmptyInput),
        }
    }

    async fn process(
        &self,
        input: PipelineInput,
        ctx: &PipelineContext,
    ) -> Result<PipelineOutput, PipelineError> {
        let req = match input.payload {
            Some(ComputePayload::Analytics(r)) => r,
            _ => {
                return Err(PipelineError::Validation(
                    "missing analytics request payload".to_string(),
                ))
            }
        };

        let limit = if req.limit > 0 { req.limit as usize } else { 30 };

        ctx.progress
            .update(0.0, "analytics", &format!("Starting analytics: {}", req.mode))
            .await;

        // Load concept data from DB
        let concept_lists = load_concepts(&ctx.pool, &req.domain_id).await?;

        ctx.progress
            .update(0.3, "analytics", &format!("Loaded {} records", concept_lists.len()))
            .await;

        let mut response = AnalyticsResponse {
            topics: vec![],
            cooccurrences: vec![],
            clusters: vec![],
            correlations: vec![],
        };

        match req.mode.as_str() {
            "topics" => {
                let top = top_topics(&concept_lists, limit);
                let total = concept_lists.len() as f32;
                response.topics = top
                    .into_iter()
                    .map(|(concept, count)| TopicEntry {
                        concept,
                        count: count as i32,
                        frequency: if total > 0.0 { count as f32 / total } else { 0.0 },
                    })
                    .collect();
            }
            "cooccurrence" => {
                let pairs = cooccurrence_pmi(&concept_lists, limit);
                response.cooccurrences = pairs
                    .into_iter()
                    .map(|e| CooccurrencePair {
                        concept_a: e.concept_a,
                        concept_b: e.concept_b,
                        co_count: e.co_count as i32,
                        pmi: e.pmi as f32,
                    })
                    .collect();
            }
            "clusters" => {
                let n_clusters = if limit > 0 { limit.min(20) } else { 6 };
                let cls = topic_clusters(&concept_lists, n_clusters);
                response.clusters = cls
                    .into_iter()
                    .map(|c| TopicCluster {
                        seed_concept: c.seed,
                        members: c.members.iter().map(|(m, _)| m.clone()).collect(),
                        total_count: c.members.iter().map(|(_, cnt)| *cnt as i32).sum(),
                    })
                    .collect();
            }
            "correlation" => {
                let field_data = load_field_data(&ctx.pool, &req.domain_id, &req.field_filters)
                    .await?;
                let corrs = top_correlations(&field_data, limit);
                response.correlations = corrs
                    .into_iter()
                    .map(|e: CorrelationEntry| CorrelationPair {
                        field_a: e.field_a,
                        field_b: e.field_b,
                        cramers_v: e.cramers_v as f32,
                        strength: e.strength,
                    })
                    .collect();
            }
            _ => unreachable!("validated above"),
        }

        ctx.progress
            .update(1.0, "done", "Analytics complete")
            .await;

        let mut counters = HashMap::new();
        counters.insert("records_analyzed".to_string(), concept_lists.len() as i32);

        Ok(PipelineOutput {
            counters,
            compute_result: Some(ComputeResult::Analytics(response)),
            ..PipelineOutput::default()
        })
    }
}

/// Load enrichment_concepts from the DB for a given domain.
async fn load_concepts(
    pool: &sqlx::PgPool,
    domain_id: &str,
) -> Result<Vec<Vec<String>>, PipelineError> {
    let rows: Vec<(Option<String>,)> = if domain_id == "all" {
        sqlx::query_as(
            "SELECT enrichment_concepts FROM raw_entities \
             WHERE enrichment_concepts IS NOT NULL AND enrichment_concepts != ''"
        )
        .fetch_all(pool)
        .await
        .map_err(PipelineError::Database)?
    } else {
        sqlx::query_as(
            "SELECT enrichment_concepts FROM raw_entities \
             WHERE domain = $1 AND enrichment_concepts IS NOT NULL AND enrichment_concepts != ''"
        )
        .bind(domain_id)
        .fetch_all(pool)
        .await
        .map_err(PipelineError::Database)?
    };

    Ok(rows
        .into_iter()
        .filter_map(|(concepts,)| concepts.map(|c| parse_concepts(&c)))
        .collect())
}

/// Load categorical field data for correlation analysis.
async fn load_field_data(
    pool: &sqlx::PgPool,
    domain_id: &str,
    field_filters: &[String],
) -> Result<HashMap<String, Vec<String>>, PipelineError> {
    // For correlation, we need actual column data. Since raw_entities has a fixed schema,
    // we query the key categorical columns.
    let candidate_fields = if field_filters.is_empty() {
        vec![
            "brand_capitalized", "enrichment_source", "domain",
            "enrichment_status", "validation_status",
        ]
    } else {
        field_filters.iter().map(|s| s.as_str()).collect()
    };

    let mut result: HashMap<String, Vec<String>> = HashMap::new();

    for field in &candidate_fields {
        if correlation::should_skip_field(field) {
            continue;
        }

        let safe_field = field.replace(|c: char| !c.is_alphanumeric() && c != '_', "");
        if safe_field.is_empty() || safe_field != *field {
            continue; // skip if the field name was sanitized (unsafe chars)
        }

        let query = format!(
            "SELECT \"{}\" FROM raw_entities WHERE domain = $1 AND \"{}\" IS NOT NULL",
            safe_field, safe_field
        );

        let rows: Vec<(String,)> = sqlx::query_as(&query)
            .bind(domain_id)
            .fetch_all(pool)
            .await
            .map_err(PipelineError::Database)?;

        let values: Vec<String> = rows.into_iter().map(|(v,)| v).collect();
        if !values.is_empty() {
            result.insert(field.to_string(), values);
        }
    }

    Ok(result)
}
