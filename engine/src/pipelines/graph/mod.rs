pub mod canonical;
pub mod dedup;
pub mod nodes;
pub mod relationships;

use async_trait::async_trait;
use std::collections::HashMap;

use crate::db::bulk_writer::BulkWriter;
use crate::db::schema::{PendingNode, PendingRelationship};
use crate::pipelines::{Pipeline, PipelineContext, PipelineError, PipelineInput, PipelineOutput};

pub struct GraphMaterializationPipeline;

#[async_trait]
impl Pipeline for GraphMaterializationPipeline {
    fn name(&self) -> &'static str {
        "graph_materialization"
    }

    async fn process(
        &self,
        input: PipelineInput,
        ctx: &PipelineContext,
    ) -> Result<PipelineOutput, PipelineError> {
        let org_id = input.org_id;
        let domain = &input.domain;
        let import_batch_id = input.import_batch_id;

        ctx.progress
            .update(0.1, "extracting_nodes", "Extracting nodes")
            .await;

        // 1. Extract all nodes (dedup within batch by canonical_id)
        let mut node_map: HashMap<String, PendingNode> = HashMap::new();
        let mut all_relationships: Vec<PendingRelationship> = Vec::new();

        for pub_ in &input.publications {
            let extracted = nodes::extract_nodes(pub_, org_id, import_batch_id, domain);
            for node in extracted {
                node_map.entry(node.canonical_id.clone()).or_insert(node);
            }

            let pub_canonical_id = format!("pub:{}", pub_.entity_id);
            let rels = relationships::compute_relationships(
                pub_.entity_id,
                &pub_canonical_id,
                pub_,
                org_id,
            );
            all_relationships.extend(rels);
        }

        let unique_nodes: Vec<PendingNode> = node_map.into_values().collect();
        let _total_nodes = unique_nodes.len();

        ctx.progress
            .update(0.5, "writing_nodes", "Writing nodes to DB")
            .await;

        let writer = BulkWriter::new(
            ctx.pool.clone(),
            ctx.config.node_chunk_size,
            ctx.config.rel_chunk_size,
        );
        let stats = writer
            .flush_graph_staged(&unique_nodes, &all_relationships, org_id, domain)
            .await
            .map_err(PipelineError::Database)?;

        ctx.progress
            .update(0.8, "writing_relationships", "Writing relationships")
            .await;

        ctx.progress
            .update(1.0, "done", "Graph materialization complete")
            .await;

        Ok(PipelineOutput {
            nodes_created: stats.nodes_created,
            nodes_deduplicated: stats.nodes_deduplicated,
            relationships_created: stats.relationships_created,
            relationships_deduplicated: 0,
            keywords_extracted: 0,
            entities_classified: 0,
            counters: HashMap::new(),
            compute_result: None,
        })
    }
}
