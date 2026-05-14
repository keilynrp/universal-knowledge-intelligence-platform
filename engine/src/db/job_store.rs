use sqlx::PgPool;
use uuid::Uuid;

#[derive(Debug, Clone, sqlx::FromRow)]
pub struct JobRow {
    pub id: Uuid,
    pub job_id: String,
    pub pipeline: String,
    pub status: String,
    pub progress: f32,
    pub result_json: Option<String>,
    pub error: Option<String>,
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub started_at: Option<chrono::DateTime<chrono::Utc>>,
    pub completed_at: Option<chrono::DateTime<chrono::Utc>>,
}

pub async fn ensure_table(pool: &PgPool) -> Result<(), sqlx::Error> {
    sqlx::query(
        "CREATE TABLE IF NOT EXISTS engine_jobs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            job_id TEXT UNIQUE NOT NULL,
            pipeline TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            progress REAL NOT NULL DEFAULT 0.0,
            result_json TEXT NULL,
            error TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            started_at TIMESTAMPTZ NULL,
            completed_at TIMESTAMPTZ NULL
        )",
    )
    .execute(pool)
    .await?;
    Ok(())
}

pub async fn insert_job(
    pool: &PgPool,
    job_id: &str,
    pipeline: &str,
) -> Result<JobRow, sqlx::Error> {
    sqlx::query_as::<_, JobRow>(
        "INSERT INTO engine_jobs (job_id, pipeline, status, progress)
         VALUES ($1, $2, 'queued', 0.0)
         RETURNING *",
    )
    .bind(job_id)
    .bind(pipeline)
    .fetch_one(pool)
    .await
}

pub async fn update_status(
    pool: &PgPool,
    job_id: &str,
    status: &str,
    progress: f32,
) -> Result<(), sqlx::Error> {
    let started_at_expr = if status == "running" {
        "COALESCE(started_at, NOW())"
    } else {
        "started_at"
    };

    let sql = format!(
        "UPDATE engine_jobs SET status = $2, progress = $3, started_at = {}
         WHERE job_id = $1",
        started_at_expr
    );
    sqlx::query(&sql)
        .bind(job_id)
        .bind(status)
        .bind(progress)
        .execute(pool)
        .await?;
    Ok(())
}

pub async fn update_completed(
    pool: &PgPool,
    job_id: &str,
    result_json: Option<&str>,
) -> Result<(), sqlx::Error> {
    sqlx::query(
        "UPDATE engine_jobs SET status = 'completed', progress = 1.0,
         result_json = $2, completed_at = NOW()
         WHERE job_id = $1",
    )
    .bind(job_id)
    .bind(result_json)
    .execute(pool)
    .await?;
    Ok(())
}

pub async fn update_failed(
    pool: &PgPool,
    job_id: &str,
    error: &str,
) -> Result<(), sqlx::Error> {
    sqlx::query(
        "UPDATE engine_jobs SET status = 'failed', error = $2, completed_at = NOW()
         WHERE job_id = $1",
    )
    .bind(job_id)
    .bind(error)
    .execute(pool)
    .await?;
    Ok(())
}

pub async fn find_by_job_id(
    pool: &PgPool,
    job_id: &str,
) -> Result<Option<JobRow>, sqlx::Error> {
    sqlx::query_as::<_, JobRow>(
        "SELECT * FROM engine_jobs WHERE job_id = $1",
    )
    .bind(job_id)
    .fetch_optional(pool)
    .await
}

pub async fn list_jobs(
    pool: &PgPool,
    pipeline_filter: Option<&str>,
    status_filter: Option<&str>,
    limit: i64,
) -> Result<Vec<JobRow>, sqlx::Error> {
    let mut builder = sqlx::QueryBuilder::<sqlx::Postgres>::new(
        "SELECT * FROM engine_jobs WHERE 1=1",
    );
    if let Some(pipeline) = pipeline_filter {
        builder.push(" AND pipeline = ");
        builder.push_bind(pipeline.to_string());
    }
    if let Some(status) = status_filter {
        builder.push(" AND status = ");
        builder.push_bind(status.to_string());
    }
    builder.push(" ORDER BY created_at DESC LIMIT ");
    builder.push_bind(limit);

    builder
        .build_query_as::<JobRow>()
        .fetch_all(pool)
        .await
}

pub async fn fail_stale_jobs(pool: &PgPool, error: &str) -> Result<u64, sqlx::Error> {
    let result = sqlx::query(
        "UPDATE engine_jobs SET status = 'failed', error = $1, completed_at = NOW()
         WHERE status IN ('running', 'queued')",
    )
    .bind(error)
    .execute(pool)
    .await?;
    Ok(result.rows_affected())
}
