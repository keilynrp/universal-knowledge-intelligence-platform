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

/// Whitelist of raw_entities columns allowed in correlation field_filter queries.
/// Any user-supplied column name not in this list is rejected before SQL construction.
const ALLOWED_COLUMNS: &[&str] = &[
    "primary_label",
    "secondary_label",
    "entity_type",
    "entity_name",
    "brand_capitalized",
    "enrichment_concepts",
    "enrichment_source",
    "enrichment_status",
    "enrichment_doi",
    "enrichment_citation_count",
    "domain",
    "validation_status",
    "sku",
    "gtin",
    "barcode",
    "title",
    "doi",
    "nct_id",
    "source",
    "branches",
    "creation_date",
    "normalized_json",
    "status",
];

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
            other => {
                return Err(PipelineError::Validation(format!(
                    "unknown analytics mode: {}",
                    other
                )))
            }
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
            "secondary_label", "entity_type", "enrichment_source", "domain",
            "enrichment_status", "validation_status",
        ]
    } else {
        // Validate all user-supplied field names against the whitelist
        for f in field_filters {
            if !ALLOWED_COLUMNS.contains(&f.as_str()) {
                return Err(PipelineError::Validation(format!(
                    "unknown column '{}' in field_filters; allowed: {:?}",
                    f, ALLOWED_COLUMNS
                )));
            }
        }
        field_filters.iter().map(|s| s.as_str()).collect()
    };

    let mut result: HashMap<String, Vec<String>> = HashMap::new();

    for field in &candidate_fields {
        if correlation::should_skip_field(field) {
            continue;
        }

        // Double-check against whitelist (covers both default and user-supplied paths)
        if !ALLOWED_COLUMNS.contains(field) {
            continue;
        }

        let query = format!(
            "SELECT \"{}\" FROM raw_entities WHERE domain = $1 AND \"{}\" IS NOT NULL",
            field, field
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_allowed_columns_whitelist_rejects_unknown() {
        assert!(ALLOWED_COLUMNS.contains(&"brand_capitalized"));
        assert!(ALLOWED_COLUMNS.contains(&"domain"));
        assert!(!ALLOWED_COLUMNS.contains(&"'; DROP TABLE raw_entities; --"));
        assert!(!ALLOWED_COLUMNS.contains(&"nonexistent_column"));
    }

    #[test]
    fn test_default_candidate_fields_are_allowed() {
        let defaults = ["secondary_label", "entity_type", "enrichment_source", "domain",
                        "enrichment_status", "validation_status"];
        for field in &defaults {
            assert!(
                ALLOWED_COLUMNS.contains(field),
                "default field '{}' not in ALLOWED_COLUMNS",
                field
            );
        }
    }

    #[test]
    fn test_analytics_validate_rejects_invalid_mode() {
        let pipeline = AnalyticsPipeline;
        let input = PipelineInput {
            job_id: "t".to_string(),
            import_batch_id: 0,
            org_id: None,
            domain: "t".to_string(),
            publications: vec![],
            options: HashMap::new(),
            payload: Some(ComputePayload::Analytics(crate::proto::AnalyticsRequest {
                domain_id: "test".to_string(),
                mode: "sql_injection".to_string(),
                limit: 10,
                field_filters: vec!["'; DROP TABLE--".to_string()],
            })),
        };
        assert!(pipeline.validate(&input).is_err());
    }
}
