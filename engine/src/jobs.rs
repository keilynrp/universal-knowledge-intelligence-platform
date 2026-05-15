use dashmap::DashMap;
use std::sync::Arc;
use std::time::Instant;
use tokio::sync::{OwnedSemaphorePermit, Semaphore};

use crate::db::job_store;

#[derive(Debug, Clone)]
pub enum JobStatus {
    Queued,
    Running,
    Completed,
    Failed(String),
}

#[derive(Clone)]
pub struct JobState {
    pub pipeline: String,
    pub status: JobStatus,
    pub progress: f32,
    pub started_at: Instant,
    pub result: Option<crate::pipelines::PipelineOutput>,
    pub tracker: Option<Arc<crate::progress::ProgressTracker>>,
    /// When the job reached a terminal state (completed/failed)
    completed_at: Option<Instant>,
}

pub struct JobManager {
    jobs: DashMap<String, JobState>,
    #[allow(dead_code)]
    max_concurrent: usize,
    pool: Option<sqlx::PgPool>,
    semaphore: Arc<Semaphore>,
}

impl JobManager {
    pub fn new(max_concurrent: usize) -> Self {
        Self {
            jobs: DashMap::new(),
            max_concurrent,
            pool: None,
            semaphore: Arc::new(Semaphore::new(max_concurrent)),
        }
    }

    /// Create a JobManager backed by Postgres for persistence.
    pub fn with_pool(max_concurrent: usize, pool: sqlx::PgPool) -> Self {
        Self {
            jobs: DashMap::new(),
            max_concurrent,
            pool: Some(pool),
            semaphore: Arc::new(Semaphore::new(max_concurrent)),
        }
    }

    pub async fn create(&self, job_id: &str, pipeline: &str) {
        // Insert into Postgres first
        if let Some(pool) = &self.pool {
            if let Err(e) = job_store::insert_job(pool, job_id, pipeline).await {
                tracing::error!(job_id, error = %e, "failed to persist job creation");
            }
        }

        self.jobs.insert(
            job_id.to_string(),
            JobState {
                pipeline: pipeline.to_string(),
                status: JobStatus::Queued,
                progress: 0.0,
                started_at: Instant::now(),
                result: None,
                tracker: None,
                completed_at: None,
            },
        );
    }

    pub fn store_tracker(&self, job_id: &str, tracker: Arc<crate::progress::ProgressTracker>) {
        if let Some(mut job) = self.jobs.get_mut(job_id) {
            job.tracker = Some(tracker);
        }
    }

    pub fn get_tracker(&self, job_id: &str) -> Option<Arc<crate::progress::ProgressTracker>> {
        self.jobs.get(job_id).and_then(|r| r.tracker.clone())
    }

    /// Get job state from in-memory cache. Returns None if evicted.
    pub fn get(&self, job_id: &str) -> Option<JobState> {
        self.jobs.get(job_id).map(|r| r.clone())
    }

    /// Get job state, falling back to Postgres if not in cache.
    pub async fn get_or_fetch(&self, job_id: &str) -> Option<JobState> {
        if let Some(state) = self.get(job_id) {
            return Some(state);
        }

        // Fall back to Postgres
        let pool = self.pool.as_ref()?;
        let row = job_store::find_by_job_id(pool, job_id).await.ok()??;
        Some(job_row_to_state(&row))
    }

    pub async fn set_running(&self, job_id: &str) {
        if let Some(pool) = &self.pool {
            if let Err(e) = job_store::update_status(pool, job_id, "running", 0.0).await {
                tracing::error!(job_id, error = %e, "failed to persist running status");
            }
        }

        if let Some(mut job) = self.jobs.get_mut(job_id) {
            job.status = JobStatus::Running;
        }
    }

    pub async fn set_completed(&self, job_id: &str, result: crate::pipelines::PipelineOutput) {
        // Serialize both counters and basic stats for persistence
        let result_json = serde_json::to_value(&result.counters)
            .ok()
            .map(|counters| {
                serde_json::json!({
                    "counters": counters,
                    "nodes_created": result.nodes_created,
                    "nodes_deduplicated": result.nodes_deduplicated,
                    "relationships_created": result.relationships_created,
                    "relationships_deduplicated": result.relationships_deduplicated,
                    "keywords_extracted": result.keywords_extracted,
                    "entities_classified": result.entities_classified,
                })
            })
            .and_then(|v| serde_json::to_string(&v).ok());

        if let Some(pool) = &self.pool {
            if let Err(e) =
                job_store::update_completed(pool, job_id, result_json.as_deref()).await
            {
                tracing::error!(job_id, error = %e, "failed to persist completion");
            }
        }

        if let Some(mut job) = self.jobs.get_mut(job_id) {
            job.status = JobStatus::Completed;
            job.progress = 1.0;
            job.result = Some(result);
            job.completed_at = Some(Instant::now());
        }
    }

    pub async fn set_failed(&self, job_id: &str, error: String) {
        if let Some(pool) = &self.pool {
            if let Err(e) = job_store::update_failed(pool, job_id, &error).await {
                tracing::error!(job_id, error = %e, "failed to persist failure");
            }
        }

        if let Some(mut job) = self.jobs.get_mut(job_id) {
            job.status = JobStatus::Failed(error);
            job.completed_at = Some(Instant::now());
        }
    }

    pub fn active_count(&self) -> usize {
        self.jobs
            .iter()
            .filter(|r| matches!(r.value().status, JobStatus::Running))
            .count()
    }

    pub fn can_accept(&self) -> bool {
        self.semaphore.available_permits() > 0
    }

    /// Atomically acquire a concurrency permit. Returns `None` if at capacity.
    /// The caller must hold the permit until the job completes.
    #[must_use = "dropping the permit immediately releases the concurrency slot"]
    pub fn try_acquire(&self) -> Option<OwnedSemaphorePermit> {
        Arc::clone(&self.semaphore).try_acquire_owned().ok()
    }

    pub async fn fail_all_active(&self, error: &str) {
        for mut entry in self.jobs.iter_mut() {
            if matches!(
                entry.value().status,
                JobStatus::Running | JobStatus::Queued
            ) {
                entry.value_mut().status = JobStatus::Failed(error.to_string());
                entry.value_mut().completed_at = Some(Instant::now());
            }
        }

        if let Some(pool) = &self.pool {
            if let Err(e) = job_store::fail_stale_jobs(pool, error).await {
                tracing::error!(error = %e, "failed to persist fail_all_active");
            }
        }
    }

    /// Startup recovery: mark stale running/queued jobs as failed in Postgres.
    pub async fn recover_stale_jobs(&self) -> Result<u64, sqlx::Error> {
        if let Some(pool) = &self.pool {
            let count = job_store::fail_stale_jobs(pool, "engine restarted").await?;
            if count > 0 {
                tracing::info!(count, "recovered stale jobs on startup");
            }
            Ok(count)
        } else {
            Ok(0)
        }
    }

    /// List jobs from Postgres with optional filters.
    pub async fn list_jobs(
        &self,
        pipeline_filter: Option<&str>,
        status_filter: Option<&str>,
        limit: i64,
    ) -> Result<Vec<job_store::JobRow>, sqlx::Error> {
        if let Some(pool) = &self.pool {
            job_store::list_jobs(pool, pipeline_filter, status_filter, limit).await
        } else {
            Ok(vec![])
        }
    }

    /// Evict completed/failed jobs from the DashMap cache after `ttl` seconds.
    pub fn evict_stale_cache(&self, ttl_secs: u64) {
        let cutoff = std::time::Duration::from_secs(ttl_secs);
        self.jobs.retain(|_key, state| {
            match state.completed_at {
                Some(completed) => completed.elapsed() < cutoff,
                None => true, // keep active jobs
            }
        });
    }
}

/// Convert a Postgres row to an in-memory JobState (for cache-miss fallback).
fn job_row_to_state(row: &job_store::JobRow) -> JobState {
    let status = match row.status.as_str() {
        "queued" => JobStatus::Queued,
        "running" => JobStatus::Running,
        "completed" => JobStatus::Completed,
        "failed" => JobStatus::Failed(row.error.clone().unwrap_or_default()),
        _ => JobStatus::Failed(format!("unknown status: {}", row.status)),
    };

    JobState {
        pipeline: row.pipeline.clone(),
        status,
        progress: row.progress,
        started_at: Instant::now(), // approximate — original instant not stored
        result: None,               // result not reconstructed from JSON for cache fallback
        tracker: None,
        completed_at: if row.completed_at.is_some() {
            Some(Instant::now())
        } else {
            None
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_create_and_get_job() {
        let mgr = JobManager::new(4);
        mgr.create("test-job-1", "graph_materialization").await;
        let status = mgr.get("test-job-1").unwrap();
        assert_eq!(status.pipeline, "graph_materialization");
        assert!(matches!(status.status, JobStatus::Queued));
    }

    #[tokio::test]
    async fn test_update_job_status() {
        let mgr = JobManager::new(4);
        mgr.create("j1", "graph_materialization").await;
        mgr.set_running("j1").await;
        let status = mgr.get("j1").unwrap();
        assert!(matches!(status.status, JobStatus::Running));
    }

    #[tokio::test]
    async fn test_active_count() {
        let mgr = JobManager::new(4);
        mgr.create("j1", "test").await;
        mgr.set_running("j1").await;
        mgr.create("j2", "test").await;
        mgr.set_running("j2").await;
        assert_eq!(mgr.active_count(), 2);
    }

    #[tokio::test]
    async fn test_max_concurrent_exceeded() {
        let mgr = JobManager::new(1);
        // Acquire the single permit
        let _permit = mgr.try_acquire().expect("should get first permit");
        // Second acquire should fail — at capacity
        assert!(mgr.try_acquire().is_none());
        assert!(!mgr.can_accept());
    }

    #[tokio::test]
    async fn test_evict_stale_cache() {
        let mgr = JobManager::new(4);
        mgr.create("j1", "test").await;
        mgr.set_completed("j1", crate::pipelines::PipelineOutput::default())
            .await;

        // Job still in cache right after completion (within 60s TTL)
        assert!(mgr.get("j1").is_some());

        // Evict with 0s TTL — should remove completed jobs immediately
        mgr.evict_stale_cache(0);
        assert!(mgr.get("j1").is_none());
    }

    #[tokio::test]
    async fn test_evict_keeps_active_jobs() {
        let mgr = JobManager::new(4);
        mgr.create("j1", "test").await;
        mgr.set_running("j1").await;

        // Evict with 0s TTL — running jobs have no completed_at, so they stay
        mgr.evict_stale_cache(0);
        assert!(mgr.get("j1").is_some());
    }

    #[tokio::test]
    async fn test_get_or_fetch_returns_cached() {
        let mgr = JobManager::new(4);
        mgr.create("j1", "test").await;
        let state = mgr.get_or_fetch("j1").await;
        assert!(state.is_some());
    }

    #[tokio::test]
    async fn test_get_or_fetch_returns_none_without_pool() {
        let mgr = JobManager::new(4);
        // No pool, no cache entry → None
        let state = mgr.get_or_fetch("nonexistent").await;
        assert!(state.is_none());
    }
}
