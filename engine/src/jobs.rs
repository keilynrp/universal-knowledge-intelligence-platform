use dashmap::DashMap;
use std::time::Instant;

#[derive(Debug, Clone)]
pub enum JobStatus {
    Queued,
    Running,
    Completed,
    Failed(String),
}

#[derive(Debug, Clone)]
pub struct JobState {
    pub pipeline: String,
    pub status: JobStatus,
    pub progress: f32,
    pub started_at: Instant,
    pub result: Option<crate::pipelines::PipelineOutput>,
}

pub struct JobManager {
    jobs: DashMap<String, JobState>,
    max_concurrent: usize,
}

impl JobManager {
    pub fn new(max_concurrent: usize) -> Self {
        Self {
            jobs: DashMap::new(),
            max_concurrent,
        }
    }

    pub fn create(&self, job_id: &str, pipeline: &str) {
        self.jobs.insert(
            job_id.to_string(),
            JobState {
                pipeline: pipeline.to_string(),
                status: JobStatus::Queued,
                progress: 0.0,
                started_at: Instant::now(),
                result: None,
            },
        );
    }

    pub fn get(&self, job_id: &str) -> Option<JobState> {
        self.jobs.get(job_id).map(|r| r.clone())
    }

    pub fn set_running(&self, job_id: &str) {
        if let Some(mut job) = self.jobs.get_mut(job_id) {
            job.status = JobStatus::Running;
        }
    }

    pub fn set_completed(&self, job_id: &str, result: crate::pipelines::PipelineOutput) {
        if let Some(mut job) = self.jobs.get_mut(job_id) {
            job.status = JobStatus::Completed;
            job.progress = 1.0;
            job.result = Some(result);
        }
    }

    pub fn set_failed(&self, job_id: &str, error: String) {
        if let Some(mut job) = self.jobs.get_mut(job_id) {
            job.status = JobStatus::Failed(error);
        }
    }

    pub fn active_count(&self) -> usize {
        self.jobs
            .iter()
            .filter(|r| matches!(r.value().status, JobStatus::Running))
            .count()
    }

    pub fn can_accept(&self) -> bool {
        self.active_count() < self.max_concurrent
    }

    pub fn fail_all_active(&self, error: &str) {
        for mut entry in self.jobs.iter_mut() {
            if matches!(
                entry.value().status,
                JobStatus::Running | JobStatus::Queued
            ) {
                entry.value_mut().status = JobStatus::Failed(error.to_string());
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_and_get_job() {
        let mgr = JobManager::new(4);
        let job_id = "test-job-1".to_string();
        mgr.create(&job_id, "graph_materialization");
        let status = mgr.get(&job_id).unwrap();
        assert_eq!(status.pipeline, "graph_materialization");
        assert!(matches!(status.status, JobStatus::Queued));
    }

    #[test]
    fn test_update_job_status() {
        let mgr = JobManager::new(4);
        mgr.create("j1", "graph_materialization");
        mgr.set_running("j1");
        let status = mgr.get("j1").unwrap();
        assert!(matches!(status.status, JobStatus::Running));
    }

    #[test]
    fn test_active_count() {
        let mgr = JobManager::new(4);
        mgr.create("j1", "test");
        mgr.set_running("j1");
        mgr.create("j2", "test");
        mgr.set_running("j2");
        assert_eq!(mgr.active_count(), 2);
    }

    #[test]
    fn test_max_concurrent_exceeded() {
        let mgr = JobManager::new(1);
        mgr.create("j1", "test");
        mgr.set_running("j1");
        assert!(!mgr.can_accept());
    }
}
