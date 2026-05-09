use serde::{Deserialize, Serialize};

/// Mirrors raw_entities table for INSERT
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PendingNode {
    pub org_id: Option<i64>,
    pub import_batch_id: Option<i64>,
    pub domain: String,
    pub entity_type: String,
    pub primary_label: String,
    pub secondary_label: Option<String>,
    pub canonical_id: String,
    pub attributes_json: String,
    pub source: String,
    pub enrichment_source: Option<String>,
    pub enrichment_concepts: Option<String>,
}

/// Mirrors entity_relationships table for INSERT
#[derive(Debug, Clone)]
pub struct PendingRelationship {
    pub org_id: Option<i64>,
    pub source_canonical_id: String,
    pub target_canonical_id: String,
    pub relation_type: String,
    pub weight: f64,
}

/// Returned from flush_nodes RETURNING clause
#[derive(Debug, Clone, sqlx::FromRow)]
pub struct InsertedNode {
    pub id: i64,
    pub canonical_id: String,
}
