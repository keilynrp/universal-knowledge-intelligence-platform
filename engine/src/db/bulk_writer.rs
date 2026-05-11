use crate::db::schema::{InsertedNode, PendingNode, PendingRelationship};
use sqlx::postgres::PgConnection;
use sqlx::{Executor, PgPool};
use std::collections::HashMap;

#[derive(Debug, Clone, Copy)]
pub struct GraphFlushStats {
    pub nodes_created: i32,
    pub nodes_deduplicated: i32,
    pub relationships_created: i32,
}

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

    pub async fn flush_graph_staged(
        &self,
        nodes: &[PendingNode],
        relationships: &[PendingRelationship],
        org_id: Option<i64>,
        domain: &str,
    ) -> Result<GraphFlushStats, sqlx::Error> {
        let mut conn = self.pool.acquire().await?;
        let conn = &mut *conn;

        Self::prepare_stage_tables(conn).await?;
        Self::copy_nodes(conn, nodes).await?;
        Self::copy_relationships(conn, relationships).await?;
        Self::index_stage_tables(conn).await?;

        let staged_nodes: i64 = sqlx::query_scalar("SELECT COUNT(*) FROM ukip_stage_nodes")
            .fetch_one(&mut *conn)
            .await?;

        let nodes_created = Self::merge_nodes(conn).await? as i32;
        let relationships_created = Self::merge_relationships(conn, org_id, domain).await? as i32;

        Ok(GraphFlushStats {
            nodes_created,
            nodes_deduplicated: (staged_nodes as i32).saturating_sub(nodes_created),
            relationships_created,
        })
    }

    async fn prepare_stage_tables(conn: &mut PgConnection) -> Result<(), sqlx::Error> {
        conn.execute(
            "CREATE TEMP TABLE IF NOT EXISTS ukip_stage_nodes (
                org_id BIGINT NULL,
                import_batch_id BIGINT NULL,
                domain TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                primary_label TEXT NOT NULL,
                secondary_label TEXT NULL,
                canonical_id TEXT NOT NULL,
                attributes_json TEXT NOT NULL,
                source TEXT NOT NULL,
                enrichment_source TEXT NULL,
                enrichment_concepts TEXT NULL
            ) ON COMMIT PRESERVE ROWS",
        )
        .await?;
        conn.execute(
            "CREATE TEMP TABLE IF NOT EXISTS ukip_stage_relationships (
                org_id BIGINT NULL,
                source_canonical_id TEXT NOT NULL,
                target_canonical_id TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                weight DOUBLE PRECISION NOT NULL
            ) ON COMMIT PRESERVE ROWS",
        )
        .await?;
        conn.execute("TRUNCATE ukip_stage_nodes").await?;
        conn.execute("TRUNCATE ukip_stage_relationships").await?;
        conn.execute("DROP INDEX IF EXISTS ukip_stage_nodes_key_idx")
            .await?;
        conn.execute("DROP INDEX IF EXISTS ukip_stage_relationships_source_idx")
            .await?;
        conn.execute("DROP INDEX IF EXISTS ukip_stage_relationships_target_idx")
            .await?;
        Ok(())
    }

    async fn copy_nodes(conn: &mut PgConnection, nodes: &[PendingNode]) -> Result<(), sqlx::Error> {
        if nodes.is_empty() {
            return Ok(());
        }

        let mut copy = conn
            .copy_in_raw(
                "COPY ukip_stage_nodes \
                 (org_id, import_batch_id, domain, entity_type, primary_label, secondary_label, \
                  canonical_id, attributes_json, source, enrichment_source, enrichment_concepts) \
                 FROM STDIN WITH (FORMAT text, DELIMITER E'\\t', NULL '\\N')",
            )
            .await?;

        let mut buffer = String::with_capacity(nodes.len().min(10_000) * 256);
        for chunk in nodes.chunks(10_000) {
            buffer.clear();
            for node in chunk {
                push_opt_i64(&mut buffer, node.org_id);
                buffer.push('\t');
                push_opt_i64(&mut buffer, node.import_batch_id);
                buffer.push('\t');
                push_copy_text(&mut buffer, Some(&node.domain));
                buffer.push('\t');
                push_copy_text(&mut buffer, Some(&node.entity_type));
                buffer.push('\t');
                push_copy_text(&mut buffer, Some(&node.primary_label));
                buffer.push('\t');
                push_copy_text(&mut buffer, node.secondary_label.as_deref());
                buffer.push('\t');
                push_copy_text(&mut buffer, Some(&node.canonical_id));
                buffer.push('\t');
                push_copy_text(&mut buffer, Some(&node.attributes_json));
                buffer.push('\t');
                push_copy_text(&mut buffer, Some(&node.source));
                buffer.push('\t');
                push_copy_text(&mut buffer, node.enrichment_source.as_deref());
                buffer.push('\t');
                push_copy_text(&mut buffer, node.enrichment_concepts.as_deref());
                buffer.push('\n');
            }
            copy.send(buffer.as_bytes()).await?;
        }

        copy.finish().await?;
        Ok(())
    }

    async fn copy_relationships(
        conn: &mut PgConnection,
        relationships: &[PendingRelationship],
    ) -> Result<(), sqlx::Error> {
        if relationships.is_empty() {
            return Ok(());
        }

        let mut copy = conn
            .copy_in_raw(
                "COPY ukip_stage_relationships \
                 (org_id, source_canonical_id, target_canonical_id, relation_type, weight) \
                 FROM STDIN WITH (FORMAT text, DELIMITER E'\\t', NULL '\\N')",
            )
            .await?;

        let mut buffer = String::with_capacity(relationships.len().min(10_000) * 128);
        for chunk in relationships.chunks(10_000) {
            buffer.clear();
            for rel in chunk {
                push_opt_i64(&mut buffer, rel.org_id);
                buffer.push('\t');
                push_copy_text(&mut buffer, Some(&rel.source_canonical_id));
                buffer.push('\t');
                push_copy_text(&mut buffer, Some(&rel.target_canonical_id));
                buffer.push('\t');
                push_copy_text(&mut buffer, Some(&rel.relation_type));
                buffer.push('\t');
                buffer.push_str(&rel.weight.to_string());
                buffer.push('\n');
            }
            copy.send(buffer.as_bytes()).await?;
        }

        copy.finish().await?;
        Ok(())
    }

    async fn index_stage_tables(conn: &mut PgConnection) -> Result<(), sqlx::Error> {
        conn.execute(
            "CREATE INDEX ukip_stage_nodes_key_idx
             ON ukip_stage_nodes (org_id, domain, entity_type, canonical_id)",
        )
        .await?;
        conn.execute(
            "CREATE INDEX ukip_stage_relationships_source_idx
             ON ukip_stage_relationships (org_id, source_canonical_id)",
        )
        .await?;
        conn.execute(
            "CREATE INDEX ukip_stage_relationships_target_idx
             ON ukip_stage_relationships (org_id, target_canonical_id)",
        )
        .await?;
        conn.execute("ANALYZE ukip_stage_nodes").await?;
        conn.execute("ANALYZE ukip_stage_relationships").await?;
        Ok(())
    }

    async fn merge_nodes(conn: &mut PgConnection) -> Result<u64, sqlx::Error> {
        let with_org = sqlx::query(
            "INSERT INTO raw_entities
                (org_id, import_batch_id, domain, entity_type, primary_label,
                 secondary_label, canonical_id, attributes_json, source,
                 enrichment_source, enrichment_concepts)
             SELECT org_id, import_batch_id, domain, entity_type, primary_label,
                    secondary_label, canonical_id, attributes_json, source,
                    enrichment_source, enrichment_concepts
             FROM (
                 SELECT DISTINCT ON (org_id, domain, entity_type, canonical_id)
                        org_id, import_batch_id, domain, entity_type, primary_label,
                        secondary_label, canonical_id, attributes_json, source,
                        enrichment_source, enrichment_concepts
                 FROM ukip_stage_nodes
                 WHERE org_id IS NOT NULL
                 ORDER BY org_id, domain, entity_type, canonical_id
             ) deduped
             ON CONFLICT (org_id, domain, entity_type, canonical_id)
             WHERE org_id IS NOT NULL
             DO NOTHING",
        )
        .execute(&mut *conn)
        .await?
        .rows_affected();

        let without_org = sqlx::query(
            "INSERT INTO raw_entities
                (org_id, import_batch_id, domain, entity_type, primary_label,
                 secondary_label, canonical_id, attributes_json, source,
                 enrichment_source, enrichment_concepts)
             SELECT org_id, import_batch_id, domain, entity_type, primary_label,
                    secondary_label, canonical_id, attributes_json, source,
                    enrichment_source, enrichment_concepts
             FROM (
                 SELECT DISTINCT ON (domain, entity_type, canonical_id)
                        org_id, import_batch_id, domain, entity_type, primary_label,
                        secondary_label, canonical_id, attributes_json, source,
                        enrichment_source, enrichment_concepts
                 FROM ukip_stage_nodes
                 WHERE org_id IS NULL
                 ORDER BY domain, entity_type, canonical_id
             ) deduped
             ON CONFLICT (domain, entity_type, canonical_id)
             WHERE org_id IS NULL
             DO NOTHING",
        )
        .execute(&mut *conn)
        .await?
        .rows_affected();

        Ok(with_org + without_org)
    }

    async fn merge_relationships(
        conn: &mut PgConnection,
        org_id: Option<i64>,
        domain: &str,
    ) -> Result<u64, sqlx::Error> {
        if let Some(org_id) = org_id {
            sqlx::query(
                "INSERT INTO entity_relationships
                    (source_id, target_id, relation_type, weight, org_id)
                 SELECT src.id, dst.id, rel.relation_type, MAX(rel.weight), rel.org_id
                 FROM ukip_stage_relationships rel
                 JOIN raw_entities src
                   ON src.org_id = $2
                  AND src.domain = $1
                  AND src.canonical_id = rel.source_canonical_id
                 JOIN raw_entities dst
                   ON dst.org_id = $2
                  AND dst.domain = $1
                  AND dst.canonical_id = rel.target_canonical_id
                 WHERE rel.org_id = $2
                 GROUP BY src.id, dst.id, rel.relation_type, rel.org_id
                 ON CONFLICT DO NOTHING",
            )
            .bind(domain)
            .bind(org_id)
            .execute(conn)
            .await
            .map(|result| result.rows_affected())
        } else {
            sqlx::query(
                "INSERT INTO entity_relationships
                    (source_id, target_id, relation_type, weight, org_id)
                 SELECT src.id, dst.id, rel.relation_type, MAX(rel.weight), NULL
                 FROM ukip_stage_relationships rel
                 JOIN raw_entities src
                   ON src.org_id IS NULL
                  AND src.domain = $1
                  AND src.canonical_id = rel.source_canonical_id
                 JOIN raw_entities dst
                   ON dst.org_id IS NULL
                  AND dst.domain = $1
                  AND dst.canonical_id = rel.target_canonical_id
                 WHERE rel.org_id IS NULL
                 GROUP BY src.id, dst.id, rel.relation_type
                 ON CONFLICT DO NOTHING",
            )
            .bind(domain)
            .execute(conn)
            .await
            .map(|result| result.rows_affected())
        }
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

fn push_opt_i64(buffer: &mut String, value: Option<i64>) {
    match value {
        Some(value) => buffer.push_str(&value.to_string()),
        None => buffer.push_str("\\N"),
    }
}

fn push_copy_text(buffer: &mut String, value: Option<&str>) {
    match value {
        Some(value) => {
            for ch in value.chars() {
                match ch {
                    '\\' => buffer.push_str("\\\\"),
                    '\t' => buffer.push_str("\\t"),
                    '\n' => buffer.push_str("\\n"),
                    '\r' => buffer.push_str("\\r"),
                    _ => buffer.push(ch),
                }
            }
        }
        None => buffer.push_str("\\N"),
    }
}
