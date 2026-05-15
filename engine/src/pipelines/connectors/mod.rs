pub mod crossref;
pub mod openalex;
pub mod pubmed;
pub mod rate_limiter;
pub mod retry;

use std::collections::HashMap;

use reqwest::Client;

use crate::pipelines::{
    ComputePayload, ComputeResult, Pipeline, PipelineCategory, PipelineContext, PipelineError,
    PipelineInput, PipelineOutput, ValidationError,
};
use crate::proto::ConnectorResponse;

use self::rate_limiter::RateLimiter;

const VALID_SOURCES: &[&str] = &["openalex", "crossref", "pubmed"];
const VALID_QUERY_TYPES: &[&str] = &["doi", "title", "pmid", "search"];

/// Maximum response body size (10 MB) to prevent OOM from malicious/broken APIs.
pub const MAX_RESPONSE_BYTES: u64 = 10 * 1024 * 1024;

/// Read a response body as bytes with a size guard.
/// Returns an error if the content-length header exceeds MAX_RESPONSE_BYTES
/// or if the accumulated body exceeds the limit.
pub async fn guarded_json<T: serde::de::DeserializeOwned>(
    resp: reqwest::Response,
) -> Result<T, String> {
    if let Some(len) = resp.content_length() {
        if len > MAX_RESPONSE_BYTES {
            return Err(format!(
                "response too large: {} bytes (max {})",
                len, MAX_RESPONSE_BYTES
            ));
        }
    }
    let bytes = resp
        .bytes()
        .await
        .map_err(|e| format!("failed to read response body: {}", e))?;
    if bytes.len() as u64 > MAX_RESPONSE_BYTES {
        return Err(format!(
            "response body too large: {} bytes (max {})",
            bytes.len(),
            MAX_RESPONSE_BYTES
        ));
    }
    serde_json::from_slice(&bytes).map_err(|e| format!("json parse: {}", e))
}

/// Pipeline for fetching publications from external scientific APIs.
/// No `Default` impl because construction is fallible (HTTP client init).
#[allow(clippy::new_ret_no_self)]
pub struct ConnectorPipeline {
    client: Client,
    limiter: RateLimiter,
}

impl ConnectorPipeline {
    pub fn new() -> Result<Self, String> {
        let client = Client::builder()
            .user_agent("UKIP-Engine/0.1 (mailto:admin@ukip.dev)")
            .timeout(std::time::Duration::from_secs(30))
            .connect_timeout(std::time::Duration::from_secs(10))
            .pool_max_idle_per_host(10)
            .build()
            .map_err(|e| format!("failed to build HTTP client: {}", e))?;
        Ok(Self {
            client,
            limiter: RateLimiter::new(5.0, 10.0), // 5 req/s burst 10
        })
    }
}

#[async_trait::async_trait]
impl Pipeline for ConnectorPipeline {
    fn name(&self) -> &'static str {
        "compute_connectors"
    }

    fn category(&self) -> PipelineCategory {
        PipelineCategory::Compute
    }

    fn validate(&self, input: &PipelineInput) -> Result<(), ValidationError> {
        match &input.payload {
            Some(ComputePayload::Connector(req)) => {
                if !VALID_SOURCES.contains(&req.source.as_str()) {
                    return Err(ValidationError::InvalidField(format!(
                        "invalid source '{}', expected one of: {:?}",
                        req.source, VALID_SOURCES
                    )));
                }
                if !VALID_QUERY_TYPES.contains(&req.query_type.as_str()) {
                    return Err(ValidationError::InvalidField(format!(
                        "invalid query_type '{}', expected one of: {:?}",
                        req.query_type, VALID_QUERY_TYPES
                    )));
                }
                if req.queries.is_empty() {
                    return Err(ValidationError::EmptyInput);
                }
                if req.queries.len() > 200 {
                    return Err(ValidationError::InvalidField(format!(
                        "too many queries: {} (max 200)",
                        req.queries.len()
                    )));
                }
                Ok(())
            }
            _ => Err(ValidationError::EmptyInput),
        }
    }

    async fn process(
        &self,
        input: PipelineInput,
        ctx: &PipelineContext,
    ) -> Result<PipelineOutput, PipelineError> {
        let req = match input.payload {
            Some(ComputePayload::Connector(r)) => r,
            _ => {
                return Err(PipelineError::Validation(
                    "missing connector request payload".to_string(),
                ))
            }
        };

        let limit = if req.limit > 0 { req.limit as usize } else { 10 };

        ctx.progress
            .update(0.0, "connectors", &format!("Fetching from {}", req.source))
            .await;

        let publications = match req.source.as_str() {
            "openalex" => {
                openalex::fetch(&self.client, &self.limiter, &req.query_type, &req.queries, limit)
                    .await
                    .map_err(PipelineError::Internal)?
            }
            "crossref" => {
                crossref::fetch(&self.client, &self.limiter, &req.query_type, &req.queries, limit)
                    .await
                    .map_err(PipelineError::Internal)?
            }
            "pubmed" => {
                pubmed::fetch(&self.client, &self.limiter, &req.query_type, &req.queries, limit)
                    .await
                    .map_err(PipelineError::Internal)?
            }
            other => {
                return Err(PipelineError::Validation(format!(
                    "unsupported connector source: {}",
                    other
                )));
            }
        };

        ctx.progress
            .update(1.0, "done", &format!("Fetched {} publications", publications.len()))
            .await;

        let total_results = publications.len() as i32;
        let mut counters = HashMap::new();
        counters.insert("publications_fetched".to_string(), total_results);

        Ok(PipelineOutput {
            counters,
            compute_result: Some(ComputeResult::Connector(ConnectorResponse {
                publications,
                total_results,
            })),
            ..PipelineOutput::default()
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_connector_validate_valid() {
        let pipeline = ConnectorPipeline::new().unwrap();
        let input = PipelineInput {
            job_id: "t".to_string(),
            import_batch_id: 0,
            org_id: None,
            domain: "t".to_string(),
            publications: vec![],
            options: HashMap::new(),
            payload: Some(ComputePayload::Connector(crate::proto::ConnectorRequest {
                source: "openalex".to_string(),
                query_type: "doi".to_string(),
                queries: vec!["10.1234/test".to_string()],
                limit: 10,
                filters: HashMap::new(),
            })),
        };
        assert!(pipeline.validate(&input).is_ok());
    }

    #[test]
    fn test_connector_validate_bad_source() {
        let pipeline = ConnectorPipeline::new().unwrap();
        let input = PipelineInput {
            job_id: "t".to_string(),
            import_batch_id: 0,
            org_id: None,
            domain: "t".to_string(),
            publications: vec![],
            options: HashMap::new(),
            payload: Some(ComputePayload::Connector(crate::proto::ConnectorRequest {
                source: "unknown".to_string(),
                query_type: "doi".to_string(),
                queries: vec!["test".to_string()],
                limit: 10,
                filters: HashMap::new(),
            })),
        };
        assert!(pipeline.validate(&input).is_err());
    }

    #[test]
    fn test_connector_validate_empty_queries() {
        let pipeline = ConnectorPipeline::new().unwrap();
        let input = PipelineInput {
            job_id: "t".to_string(),
            import_batch_id: 0,
            org_id: None,
            domain: "t".to_string(),
            publications: vec![],
            options: HashMap::new(),
            payload: Some(ComputePayload::Connector(crate::proto::ConnectorRequest {
                source: "openalex".to_string(),
                query_type: "search".to_string(),
                queries: vec![],
                limit: 10,
                filters: HashMap::new(),
            })),
        };
        assert!(pipeline.validate(&input).is_err());
    }

    #[test]
    fn test_connector_validate_too_many_queries() {
        let pipeline = ConnectorPipeline::new().unwrap();
        let queries: Vec<String> = (0..201).map(|i| format!("query_{}", i)).collect();
        let input = PipelineInput {
            job_id: "t".to_string(),
            import_batch_id: 0,
            org_id: None,
            domain: "t".to_string(),
            publications: vec![],
            options: HashMap::new(),
            payload: Some(ComputePayload::Connector(crate::proto::ConnectorRequest {
                source: "openalex".to_string(),
                query_type: "doi".to_string(),
                queries,
                limit: 10,
                filters: HashMap::new(),
            })),
        };
        let err = pipeline.validate(&input).unwrap_err();
        assert!(format!("{}", err).contains("too many queries"));
    }

    #[test]
    fn test_connector_validate_bad_query_type() {
        let pipeline = ConnectorPipeline::new().unwrap();
        let input = PipelineInput {
            job_id: "t".to_string(),
            import_batch_id: 0,
            org_id: None,
            domain: "t".to_string(),
            publications: vec![],
            options: HashMap::new(),
            payload: Some(ComputePayload::Connector(crate::proto::ConnectorRequest {
                source: "crossref".to_string(),
                query_type: "invalid_type".to_string(),
                queries: vec!["test".to_string()],
                limit: 10,
                filters: HashMap::new(),
            })),
        };
        assert!(pipeline.validate(&input).is_err());
    }
}
