use tokio::sync::broadcast;

#[derive(Debug, Clone)]
pub struct ProgressEvent {
    pub job_id: String,
    pub progress: f32,
    pub phase: String,
    pub message: String,
    pub counters: std::collections::HashMap<String, i32>,
}

pub struct ProgressTracker {
    job_id: String,
    tx: broadcast::Sender<ProgressEvent>,
}

impl ProgressTracker {
    pub fn new(job_id: String) -> Self {
        let (tx, _) = broadcast::channel(64);
        Self { job_id, tx }
    }

    pub async fn update(&self, progress: f32, phase: &str, message: &str) {
        let event = ProgressEvent {
            job_id: self.job_id.clone(),
            progress,
            phase: phase.to_string(),
            message: message.to_string(),
            counters: Default::default(),
        };
        let _ = self.tx.send(event);
    }

    pub fn subscribe(&self) -> broadcast::Receiver<ProgressEvent> {
        self.tx.subscribe()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_progress_update_and_subscribe() {
        let tracker = ProgressTracker::new("job-1".to_string());
        let mut rx = tracker.subscribe();

        tracker.update(0.5, "writing_nodes", "50% done").await;

        let event = rx.recv().await.unwrap();
        assert_eq!(event.progress, 0.5);
        assert_eq!(event.phase, "writing_nodes");
    }

    #[tokio::test]
    async fn test_progress_complete() {
        let tracker = ProgressTracker::new("job-2".to_string());
        tracker.update(1.0, "done", "complete").await;
        // No panic on drop
    }
}
