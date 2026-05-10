use crate::db::schema::{InsertedNode, PendingNode, PendingRelationship};
use sqlx::PgPool;
use std::collections::HashMap;

pub struct BulkWriter {
    pool: PgPool,
    node_chunk_size: usize,
    rel_chunk_size: usize,
}

impl BulkWriter {
    pub fn new(pool: PgPool, node_chunk_size: usize, rel_chunk_size: usize) -> Self {
        Self {
            pool,
            node_chunk_size,
            rel_chunk_size,
        }
    }

    /// Flush nodes to DB and return a canonical_id → id map covering both
    /// newly inserted rows AND rows that already existed (via upsert RETURNING).
    pub async fn flush_nodes(
        &self,
        nodes: &[PendingNode],
    ) -> Result<HashMap<String, i64>, sqlx::Error> {
        let mut id_map = HashMap::new();
        for chunk in nodes.chunks(self.node_chunk_size) {
            let inserted = self.upsert_node_chunk(chunk).await?;
            for node in inserted {
                id_map.insert(node.canonical_id, node.id);
            }
        }
        Ok(id_map)
    }

    pub async fn flush_relationships(
        &self,
        relationships: &[PendingRelationship],
        id_map: &HashMap<String, i64>,
    ) -> Result<i32, sqlx::Error> {
        let mut count = 0i32;
        for chunk in relationships.chunks(self.rel_chunk_size) {
            count += self.insert_rel_chunk(chunk, id_map).await?;
        }
        Ok(count)
    }

    /// INSERT with ON CONFLICT DO UPDATE (upsert) so that RETURNING always
    /// gives back the id — whether the row was inserted or already existed.
    ///
    /// We split into two groups by org_id nullability because PostgreSQL
    /// partial indexes require matching WHERE conditions for conflict targets.
    async fn upsert_node_chunk(
        &self,
        chunk: &[PendingNode],
    ) -> Result<Vec<InsertedNode>, sqlx::Error> {
        if chunk.is_empty() {
            return Ok(vec![]);
        }

        let mut results = Vec::new();

        // Split into org_id-present vs org_id-absent groups.
        let (with_org, without_org): (Vec<_>, Vec<_>) =
            chunk.iter().partition(|n| n.org_id.is_some());

        if !with_org.is_empty() {
            let rows = self.upsert_nodes_with_org(&with_org).await?;
            results.extend(rows);
        }
        if !without_org.is_empty() {
            let rows = self.upsert_nodes_global(&without_org).await?;
            results.extend(rows);
        }

        Ok(results)
    }

    /// Upsert for rows WHERE org_id IS NOT NULL.
    /// Conflict target: (org_id, domain, entity_type, canonical_id) WHERE org_id IS NOT NULL
    async fn upsert_nodes_with_org(
        &self,
        nodes: &[&PendingNode],
    ) -> Result<Vec<InsertedNode>, sqlx::Error> {
        let mut builder = sqlx::QueryBuilder::<sqlx::Postgres>::new(
            "INSERT INTO raw_entities \
             (org_id, import_batch_id, domain, entity_type, primary_label, \
              secondary_label, canonical_id, attributes_json, source, \
              enrichment_source, enrichment_concepts) ",
        );

        builder.push_values(nodes.iter().copied(), |mut b, node| {
            b.push_bind(node.org_id)
                .push_bind(node.import_batch_id)
                .push_bind(&node.domain)
                .push_bind(&node.entity_type)
                .push_bind(&node.primary_label)
                .push_bind(node.secondary_label.as_deref())
                .push_bind(&node.canonical_id)
                .push_bind(&node.attributes_json)
                .push_bind(&node.source)
                .push_bind(node.enrichment_source.as_deref())
                .push_bind(node.enrichment_concepts.as_deref());
        });

        builder.push(
            " ON CONFLICT (org_id, domain, entity_type, canonical_id) \
             WHERE org_id IS NOT NULL \
             DO UPDATE SET \
               primary_label = EXCLUDED.primary_label, \
               updated_at    = NOW() \
             RETURNING id, canonical_id",
        );

        builder
            .build_query_as::<InsertedNode>()
            .fetch_all(&self.pool)
            .await
    }

    /// Upsert for rows WHERE org_id IS NULL (global / legacy entities).
    /// Conflict target: (domain, entity_type, canonical_id) WHERE org_id IS NULL
    async fn upsert_nodes_global(
        &self,
        nodes: &[&PendingNode],
    ) -> Result<Vec<InsertedNode>, sqlx::Error> {
        let mut builder = sqlx::QueryBuilder::<sqlx::Postgres>::new(
            "INSERT INTO raw_entities \
             (org_id, import_batch_id, domain, entity_type, primary_label, \
              secondary_label, canonical_id, attributes_json, source, \
              enrichment_source, enrichment_concepts) ",
        );

        builder.push_values(nodes.iter().copied(), |mut b, node| {
            b.push_bind(node.org_id) // NULL
                .push_bind(node.import_batch_id)
                .push_bind(&node.domain)
                .push_bind(&node.entity_type)
                .push_bind(&node.primary_label)
                .push_bind(node.secondary_label.as_deref())
                .push_bind(&node.canonical_id)
                .push_bind(&node.attributes_json)
                .push_bind(&node.source)
                .push_bind(node.enrichment_source.as_deref())
                .push_bind(node.enrichment_concepts.as_deref());
        });

        builder.push(
            " ON CONFLICT (domain, entity_type, canonical_id) \
             WHERE org_id IS NULL \
             DO UPDATE SET \
               primary_label = EXCLUDED.primary_label, \
               updated_at    = NOW() \
             RETURNING id, canonical_id",
        );

        builder
            .build_query_as::<InsertedNode>()
            .fetch_all(&self.pool)
            .await
    }

    async fn insert_rel_chunk(
        &self,
        chunk: &[PendingRelationship],
        id_map: &HashMap<String, i64>,
    ) -> Result<i32, sqlx::Error> {
        if chunk.is_empty() {
            return Ok(0);
        }

        let resolved: Vec<(i64, i64, &str, f64, Option<i64>)> = chunk
            .iter()
            .filter_map(|rel| {
                let source_id = id_map.get(&rel.source_canonical_id)?;
                let target_id = id_map.get(&rel.target_canonical_id)?;
                Some((
                    *source_id,
                    *target_id,
                    rel.relation_type.as_str(),
                    rel.weight,
                    rel.org_id,
                ))
            })
            .collect();

        if resolved.is_empty() {
            return Ok(0);
        }

        let (with_org, without_org): (Vec<_>, Vec<_>) = resolved
            .iter()
            .partition(|(_, _, _, _, org_id)| org_id.is_some());

        let mut total = 0i32;
        if !with_org.is_empty() {
            total += self.insert_rels_chunk_inner(&with_org).await?;
        }
        if !without_org.is_empty() {
            total += self.insert_rels_chunk_inner(&without_org).await?;
        }
        Ok(total)
    }

    async fn insert_rels_chunk_inner(
        &self,
        resolved: &[(i64, i64, &str, f64, Option<i64>)],
    ) -> Result<i32, sqlx::Error> {
        let mut builder = sqlx::QueryBuilder::<sqlx::Postgres>::new(
            "INSERT INTO entity_relationships \
             (source_id, target_id, relation_type, weight, org_id) ",
        );

        builder.push_values(resolved, |mut b, (src, tgt, rel_type, weight, org_id)| {
            b.push_bind(src)
                .push_bind(tgt)
                .push_bind(*rel_type)
                .push_bind(weight)
                .push_bind(org_id);
        });

        // Use matching partial index for each group
        builder.push(" ON CONFLICT DO NOTHING");

        let result = builder.build().execute(&self.pool).await?;
        Ok(result.rows_affected() as i32)
    }
}
