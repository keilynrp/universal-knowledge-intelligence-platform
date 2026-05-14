pub mod analytics;
pub mod authority;
pub mod connectors;
pub mod disambiguation;
pub mod graph;
pub mod normalization;
pub mod text_analysis;

use std::collections::HashMap;
use std::sync::Arc;
use async_trait::async_trait;

/// Category marker for pipelines.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum PipelineCategory {
    Import,
    Compute,
}

/// Typed payload from the proto oneof, deserialized for compute pipelines.
#[derive(Debug, Clone)]
pub enum ComputePayload {
    Authority(crate::proto::AuthorityRequest),
    Analytics(crate::proto::AnalyticsRequest),
    Disambiguation(crate::proto::DisambiguationRequest),
    Normalization(crate::proto::NormalizationRequest),
    Connector(crate::proto::ConnectorRequest),
}

#[derive(Debug, Clone)]
pub struct PipelineInput {
    pub job_id: String,
    pub import_batch_id: i64,
    pub org_id: Option<i64>,
    pub domain: String,
    pub publications: Vec<crate::proto::Publication>,
    pub options: HashMap<String, String>,
    /// Typed payload for compute pipelines (None for import pipelines).
    pub payload: Option<ComputePayload>,
}

/// Typed output for compute pipelines, carried alongside the generic counters.
#[derive(Debug, Clone)]
pub enum ComputeResult {
    Authority(crate::proto::AuthorityResponse),
    Analytics(crate::proto::AnalyticsResponse),
    Disambiguation(crate::proto::DisambiguationResponse),
    Normalization(crate::proto::NormalizationResponse),
    Connector(crate::proto::ConnectorResponse),
}

#[derive(Debug, Default, Clone)]
pub struct PipelineOutput {
    pub nodes_created: i32,
    pub nodes_deduplicated: i32,
    pub relationships_created: i32,
    pub relationships_deduplicated: i32,
    pub keywords_extracted: i32,
    pub entities_classified: i32,
    pub counters: HashMap<String, i32>,
    /// Typed result for compute pipelines.
    pub compute_result: Option<ComputeResult>,
}

pub struct PipelineContext {
    pub pool: sqlx::PgPool,
    pub config: crate::config::Config,
    pub progress: crate::progress::ProgressTracker,
}

#[derive(Debug, thiserror::Error)]
pub enum PipelineError {
    #[error("validation: {0}")]
    Validation(String),
    #[error("database: {0}")]
    Database(#[from] sqlx::Error),
    #[error("internal: {0}")]
    Internal(String),
}

#[derive(Debug)]
pub enum ValidationError {
    EmptyInput,
    InvalidField(String),
}

impl std::fmt::Display for ValidationError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::EmptyInput => write!(f, "empty input"),
            Self::InvalidField(msg) => write!(f, "invalid field: {}", msg),
        }
    }
}

#[async_trait]
pub trait Pipeline: Send + Sync + 'static {
    fn name(&self) -> &'static str;

    /// Pipeline category: Import (default) or Compute.
    fn category(&self) -> PipelineCategory {
        PipelineCategory::Import
    }

    fn validate(&self, input: &PipelineInput) -> Result<(), ValidationError> {
        if input.publications.is_empty() && input.payload.is_none() {
            return Err(ValidationError::EmptyInput);
        }
        Ok(())
    }

    async fn process(
        &self,
        input: PipelineInput,
        ctx: &PipelineContext,
    ) -> Result<PipelineOutput, PipelineError>;
}

pub struct PipelineRegistry {
    pipelines: HashMap<String, Arc<dyn Pipeline>>,
}

impl PipelineRegistry {
    pub fn new_empty() -> Self {
        Self {
            pipelines: HashMap::new(),
        }
    }

    pub fn register(&mut self, pipeline: Arc<dyn Pipeline>) {
        self.pipelines
            .insert(pipeline.name().to_string(), pipeline);
    }

    pub fn get(&self, name: &str) -> Option<Arc<dyn Pipeline>> {
        self.pipelines.get(name).cloned()
    }

    pub fn list(&self) -> Vec<&str> {
        self.pipelines.keys().map(|k| k.as_str()).collect()
    }

    /// List pipelines grouped by category.
    pub fn list_by_category(&self) -> HashMap<PipelineCategory, Vec<&str>> {
        let mut grouped: HashMap<PipelineCategory, Vec<&str>> = HashMap::new();
        for (name, pipeline) in &self.pipelines {
            grouped
                .entry(pipeline.category())
                .or_default()
                .push(name.as_str());
        }
        grouped
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    struct DummyPipeline;

    #[async_trait::async_trait]
    impl Pipeline for DummyPipeline {
        fn name(&self) -> &'static str {
            "dummy"
        }

        async fn process(
            &self,
            _input: PipelineInput,
            _ctx: &PipelineContext,
        ) -> Result<PipelineOutput, PipelineError> {
            Ok(PipelineOutput::default())
        }
    }

    struct DummyComputePipeline;

    #[async_trait::async_trait]
    impl Pipeline for DummyComputePipeline {
        fn name(&self) -> &'static str {
            "dummy_compute"
        }

        fn category(&self) -> PipelineCategory {
            PipelineCategory::Compute
        }

        async fn process(
            &self,
            _input: PipelineInput,
            _ctx: &PipelineContext,
        ) -> Result<PipelineOutput, PipelineError> {
            Ok(PipelineOutput::default())
        }
    }

    #[test]
    fn test_registry_register_and_get() {
        let mut registry = PipelineRegistry::new_empty();
        registry.register(Arc::new(DummyPipeline));
        assert!(registry.get("dummy").is_some());
        assert!(registry.get("nonexistent").is_none());
    }

    #[test]
    fn test_registry_list() {
        let mut registry = PipelineRegistry::new_empty();
        registry.register(Arc::new(DummyPipeline));
        let names = registry.list();
        assert!(names.contains(&"dummy"));
    }

    #[test]
    fn test_validate_empty_input() {
        let pipeline = DummyPipeline;
        let input = PipelineInput {
            job_id: "test".to_string(),
            import_batch_id: 1,
            org_id: None,
            domain: "science".to_string(),
            publications: vec![],
            options: Default::default(),
            payload: None,
        };
        assert!(pipeline.validate(&input).is_err());
    }

    #[test]
    fn test_validate_accepts_payload_without_publications() {
        let pipeline = DummyComputePipeline;
        let input = PipelineInput {
            job_id: "test".to_string(),
            import_batch_id: 0,
            org_id: None,
            domain: "science".to_string(),
            publications: vec![],
            options: Default::default(),
            payload: Some(ComputePayload::Analytics(crate::proto::AnalyticsRequest {
                domain_id: "science".to_string(),
                mode: "topics".to_string(),
                limit: 10,
                field_filters: vec![],
            })),
        };
        assert!(pipeline.validate(&input).is_ok());
    }

    #[test]
    fn test_category_default_is_import() {
        let pipeline = DummyPipeline;
        assert_eq!(pipeline.category(), PipelineCategory::Import);
    }

    #[test]
    fn test_category_compute() {
        let pipeline = DummyComputePipeline;
        assert_eq!(pipeline.category(), PipelineCategory::Compute);
    }

    #[test]
    fn test_list_by_category() {
        let mut registry = PipelineRegistry::new_empty();
        registry.register(Arc::new(DummyPipeline));
        registry.register(Arc::new(DummyComputePipeline));
        let grouped = registry.list_by_category();
        assert!(grouped[&PipelineCategory::Import].contains(&"dummy"));
        assert!(grouped[&PipelineCategory::Compute].contains(&"dummy_compute"));
    }
}
