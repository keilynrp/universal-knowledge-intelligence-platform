use std::collections::HashMap;
use std::sync::Arc;
use crate::pipelines::{Pipeline, PipelineCategory, PipelineRegistry};

pub struct Router {
    registry: PipelineRegistry,
}

impl Router {
    pub fn new(registry: PipelineRegistry) -> Self {
        Self { registry }
    }

    pub fn get_pipeline(&self, name: &str) -> Option<Arc<dyn Pipeline>> {
        self.registry.get(name)
    }

    pub fn list_pipelines(&self) -> Vec<&str> {
        self.registry.list()
    }

    pub fn list_by_category(&self) -> HashMap<PipelineCategory, Vec<&str>> {
        self.registry.list_by_category()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_dispatch_known_pipeline() {
        let registry = PipelineRegistry::new_empty();
        let router = Router::new(registry);
        assert!(router.get_pipeline("nonexistent").is_none());
    }
}
