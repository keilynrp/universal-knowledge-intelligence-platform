use std::collections::HashMap;
use sqlx::PgPool;
use crate::db::schema::InsertedNode;

/// Query the DB for existing nodes matching the given canonical_ids.
/// Returns a map of canonical_id → DB id for nodes that already exist.
pub async fn resolve_existing(
    pool: &PgPool,
    org_id: Option<i64>,
    domain: &str,
    canonical_ids: &[String],
) -> Result<HashMap<String, i64>, sqlx::Error> {
    if canonical_ids.is_empty() {
        return Ok(HashMap::new());
    }

    let rows = sqlx::query_as::<_, InsertedNode>(
        "SELECT id, canonical_id FROM raw_entities
         WHERE org_id IS NOT DISTINCT FROM $1
         AND domain = $2
         AND canonical_id = ANY($3)",
    )
    .bind(org_id)
    .bind(domain)
    .bind(canonical_ids)
    .fetch_all(pool)
    .await?;

    Ok(rows.into_iter().map(|r| (r.canonical_id, r.id)).collect())
}
