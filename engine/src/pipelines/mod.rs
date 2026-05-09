pub mod graph;
pub mod text_analysis;

use std::collections::HashMap;
use std::sync::Arc;
use async_trait::async_trait;

#[derive(Debug, Clone)]
pub struct PipelineInput {
    pub job_id: String,
    pub import_batch_id: i64,
    pub org_id: Option<i64>,
    pub domain: String,
    pub publications: Vec<crate::proto::Publication>,
    pub options: HashMap<String, String>,
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
}

impl std::fmt::Display for ValidationError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::EmptyInput => write!(f, "empty input"),
        }
    }
}

#[async_trait]
pub trait Pipeline: Send + Sync + 'static {
    fn name(&self) -> &'static str;

    fn validate(&self, input: &PipelineInput) -> Result<(), ValidationError> {
        if input.publications.is_empty() {
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
        };
        assert!(pipeline.validate(&input).is_err());
    }
}
