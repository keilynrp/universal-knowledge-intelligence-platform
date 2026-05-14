use std::sync::Arc;
use tokio::sync::mpsc;
use tokio_stream::wrappers::ReceiverStream;
use tonic::{Request, Response, Status};

use crate::config::Config;
use crate::jobs::{JobManager, JobStatus};
use crate::pipelines::{ComputePayload, ComputeResult, PipelineCategory, PipelineContext, PipelineInput};
use crate::progress::ProgressTracker;
use crate::proto::{
    engine_server::Engine, process_request, process_response, HealthRequest, HealthResponse,
    JobAccepted, JobStatusRequest, JobStatusResponse, JobSummary, ListJobsRequest,
    ListJobsResponse, ProcessRequest, ProcessResponse, ProcessResult,
    ProgressEvent as ProtoProgressEvent,
};
use crate::router::Router;

/// gRPC auth interceptor — checks the `authorization: Bearer <token>` metadata header.
/// When `expected_token` is `None`, all requests are allowed (useful in dev/test).
#[allow(clippy::result_large_err)]
pub fn auth_interceptor(
    expected_token: Option<String>,
) -> impl Fn(Request<()>) -> Result<Request<()>, Status> + Clone {
    move |req: Request<()>| match &expected_token {
        None => Ok(req),
        Some(token) => {
            let expected = format!("Bearer {}", token);
            match req.metadata().get("authorization") {
                Some(t) if t.to_str().unwrap_or("") == expected => Ok(req),
                _ => Err(Status::unauthenticated("invalid or missing auth token")),
            }
        }
    }
}

pub struct EngineService {
    router: Arc<Router>,
    job_manager: Arc<JobManager>,
    pool: sqlx::PgPool,
    config: Arc<Config>,
}

impl EngineService {
    pub fn new(
        router: Arc<Router>,
        job_manager: Arc<JobManager>,
        pool: sqlx::PgPool,
        config: Config,
    ) -> Self {
        Self {
            router,
            job_manager,
            pool,
            config: Arc::new(config),
        }
    }
}

/// Build a PipelineInput from a ProcessRequest proto message.
fn build_pipeline_input(req: &ProcessRequest) -> PipelineInput {
    let payload = req.payload.as_ref().map(|p| match p {
        process_request::Payload::AuthorityRequest(r) => ComputePayload::Authority(r.clone()),
        process_request::Payload::AnalyticsRequest(r) => ComputePayload::Analytics(r.clone()),
        process_request::Payload::DisambiguationRequest(r) => {
            ComputePayload::Disambiguation(r.clone())
        }
        process_request::Payload::NormalizationRequest(r) => {
            ComputePayload::Normalization(r.clone())
        }
        process_request::Payload::ConnectorRequest(r) => ComputePayload::Connector(r.clone()),
    });

    PipelineInput {
        job_id: req.job_id.clone(),
        import_batch_id: req.import_batch_id,
        org_id: req.org_id,
        domain: req.domain.clone(),
        publications: req.publications.clone(),
        options: req.options.clone(),
        payload,
    }
}

/// Convert PipelineOutput to proto ProcessResult.
fn build_process_result(output: &crate::pipelines::PipelineOutput) -> ProcessResult {
    ProcessResult {
        nodes_created: output.nodes_created,
        nodes_deduplicated: output.nodes_deduplicated,
        relationships_created: output.relationships_created,
        relationships_deduplicated: output.relationships_deduplicated,
        keywords_extracted: output.keywords_extracted,
        entities_classified: output.entities_classified,
        counters: output.counters.clone(),
    }
}

/// Convert ComputeResult to the proto typed_result oneof variant.
fn build_typed_result(result: &ComputeResult) -> process_response::TypedResult {
    match result {
        ComputeResult::Authority(r) => process_response::TypedResult::AuthorityResult(r.clone()),
        ComputeResult::Analytics(r) => process_response::TypedResult::AnalyticsResult(r.clone()),
        ComputeResult::Disambiguation(r) => {
            process_response::TypedResult::DisambiguationResult(r.clone())
        }
        ComputeResult::Normalization(r) => {
            process_response::TypedResult::NormalizationResult(r.clone())
        }
        ComputeResult::Connector(r) => process_response::TypedResult::ConnectorResult(r.clone()),
    }
}

fn status_str_to_proto(s: &str) -> crate::proto::Status {
    match s {
        "queued" => crate::proto::Status::Queued,
        "running" => crate::proto::Status::Running,
        "completed" => crate::proto::Status::Completed,
        "failed" => crate::proto::Status::Failed,
        _ => crate::proto::Status::Unknown,
    }
}

#[tonic::async_trait]
impl Engine for EngineService {
    type StreamProgressStream = ReceiverStream<Result<ProtoProgressEvent, Status>>;

    async fn process_sync(
        &self,
        request: Request<ProcessRequest>,
    ) -> Result<Response<ProcessResponse>, Status> {
        let req = request.into_inner();
        let pipeline_name = &req.pipeline;

        let pipeline = self
            .router
            .get_pipeline(pipeline_name)
            .ok_or_else(|| Status::not_found(format!("pipeline '{}' not found", pipeline_name)))?;

        let input = build_pipeline_input(&req);
        let job_id = input.job_id.clone();

        if let Err(e) = pipeline.validate(&input) {
            return Err(Status::invalid_argument(format!(
                "validation failed: {}",
                e
            )));
        }

        let progress = ProgressTracker::new(job_id.clone());
        let ctx = PipelineContext {
            pool: self.pool.clone(),
            config: (*self.config).clone(),
            progress,
        };

        let start = std::time::Instant::now();

        match pipeline.process(input, &ctx).await {
            Ok(output) => {
                let duration_ms = start.elapsed().as_millis() as f64;
                let typed_result = output.compute_result.as_ref().map(build_typed_result);
                Ok(Response::new(ProcessResponse {
                    job_id,
                    pipeline: pipeline_name.clone(),
                    status: crate::proto::Status::Completed as i32,
                    result: Some(build_process_result(&output)),
                    error: None,
                    duration_ms,
                    typed_result,
                }))
            }
            Err(e) => {
                let duration_ms = start.elapsed().as_millis() as f64;
                Ok(Response::new(ProcessResponse {
                    job_id,
                    pipeline: pipeline_name.clone(),
                    status: crate::proto::Status::Failed as i32,
                    result: None,
                    error: Some(e.to_string()),
                    duration_ms,
                    typed_result: None,
                }))
            }
        }
    }

    async fn process_async(
        &self,
        request: Request<ProcessRequest>,
    ) -> Result<Response<JobAccepted>, Status> {
        if !self.job_manager.can_accept() {
            return Err(Status::resource_exhausted("max concurrent jobs reached"));
        }

        let req = request.into_inner();
        let pipeline_name = req.pipeline.clone();
        let job_id = req.job_id.clone();

        let pipeline = self
            .router
            .get_pipeline(&pipeline_name)
            .ok_or_else(|| Status::not_found(format!("pipeline '{}' not found", &pipeline_name)))?;

        let input = build_pipeline_input(&req);

        if let Err(e) = pipeline.validate(&input) {
            return Err(Status::invalid_argument(format!(
                "validation failed: {}",
                e
            )));
        }

        self.job_manager.create(&job_id, &pipeline_name).await;

        // Create tracker before spawning so stream_progress can subscribe immediately.
        let tracker = Arc::new(ProgressTracker::new(job_id.clone()));
        self.job_manager.store_tracker(&job_id, tracker.clone());

        // Spawn async task
        let job_manager = self.job_manager.clone();
        let pool = self.pool.clone();
        let config = (*self.config).clone();
        let jid = job_id.clone();

        tokio::spawn(async move {
            job_manager.set_running(&jid).await;
            let ctx = PipelineContext {
                pool,
                config,
                progress: (*tracker).clone(),
            };

            match pipeline.process(input, &ctx).await {
                Ok(output) => job_manager.set_completed(&jid, output).await,
                Err(e) => job_manager.set_failed(&jid, e.to_string()).await,
            }
        });

        Ok(Response::new(JobAccepted {
            job_id,
            pipeline: pipeline_name,
            estimated_duration_ms: 0,
        }))
    }

    async fn get_job_status(
        &self,
        request: Request<JobStatusRequest>,
    ) -> Result<Response<JobStatusResponse>, Status> {
        let req = request.into_inner();

        // Try in-memory cache first, then fall back to Postgres
        let job = self
            .job_manager
            .get_or_fetch(&req.job_id)
            .await
            .ok_or_else(|| Status::not_found(format!("job '{}' not found", req.job_id)))?;

        let (status, error, result) = match &job.status {
            JobStatus::Queued => (crate::proto::Status::Queued, None, None),
            JobStatus::Running => (crate::proto::Status::Running, None, None),
            JobStatus::Completed => (
                crate::proto::Status::Completed,
                None,
                job.result.as_ref().map(build_process_result),
            ),
            JobStatus::Failed(err) => (crate::proto::Status::Failed, Some(err.clone()), None),
        };

        Ok(Response::new(JobStatusResponse {
            job_id: req.job_id,
            status: status as i32,
            progress: job.progress,
            result,
            error,
        }))
    }

    async fn list_jobs(
        &self,
        request: Request<ListJobsRequest>,
    ) -> Result<Response<ListJobsResponse>, Status> {
        let req = request.into_inner();
        let limit = if req.limit > 0 { req.limit as i64 } else { 50 };
        let limit = limit.min(500);

        let rows = self
            .job_manager
            .list_jobs(
                req.pipeline_filter.as_deref(),
                req.status_filter.as_deref(),
                limit,
            )
            .await
            .map_err(|e| Status::internal(format!("failed to list jobs: {}", e)))?;

        let jobs = rows
            .into_iter()
            .map(|row| JobSummary {
                job_id: row.job_id,
                pipeline: row.pipeline,
                status: status_str_to_proto(&row.status) as i32,
                progress: row.progress,
                error: row.error,
                created_at: row.created_at.to_rfc3339(),
                started_at: row.started_at.map(|t| t.to_rfc3339()),
                completed_at: row.completed_at.map(|t| t.to_rfc3339()),
            })
            .collect();

        Ok(Response::new(ListJobsResponse { jobs }))
    }

    async fn stream_progress(
        &self,
        request: Request<JobStatusRequest>,
    ) -> Result<Response<Self::StreamProgressStream>, Status> {
        let req = request.into_inner();

        let tracker = self
            .job_manager
            .get_tracker(&req.job_id)
            .ok_or_else(|| Status::not_found(format!("job '{}' not running", req.job_id)))?;

        let mut broadcast_rx = tracker.subscribe();
        let (tx, rx) = mpsc::channel::<Result<ProtoProgressEvent, Status>>(64);

        tokio::spawn(async move {
            loop {
                match broadcast_rx.recv().await {
                    Ok(ev) => {
                        let proto = ProtoProgressEvent {
                            job_id: ev.job_id,
                            progress: ev.progress,
                            phase: ev.phase,
                            message: ev.message,
                            counters: ev.counters,
                        };
                        if tx.send(Ok(proto)).await.is_err() {
                            break; // client disconnected
                        }
                    }
                    Err(tokio::sync::broadcast::error::RecvError::Closed) => break,
                    Err(tokio::sync::broadcast::error::RecvError::Lagged(_)) => continue,
                }
            }
        });

        Ok(Response::new(ReceiverStream::new(rx)))
    }

    async fn health(
        &self,
        _request: Request<HealthRequest>,
    ) -> Result<Response<HealthResponse>, Status> {
        let grouped = self.router.list_by_category();
        let mut pipelines: Vec<String> = Vec::new();

        if let Some(import) = grouped.get(&PipelineCategory::Import) {
            for name in import {
                pipelines.push(format!("import:{}", name));
            }
        }
        if let Some(compute) = grouped.get(&PipelineCategory::Compute) {
            for name in compute {
                pipelines.push(format!("compute:{}", name));
            }
        }

        Ok(Response::new(HealthResponse {
            healthy: true,
            version: env!("CARGO_PKG_VERSION").to_string(),
            pipelines,
            active_jobs: self.job_manager.active_count() as i32,
        }))
    }
}
