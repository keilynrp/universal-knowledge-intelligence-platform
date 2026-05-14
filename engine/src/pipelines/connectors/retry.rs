//! Exponential backoff retry logic for transient HTTP errors.

use reqwest::StatusCode;
use std::time::Duration;

/// Retry configuration.
pub struct RetryConfig {
    pub max_retries: u32,
    pub base_delay: Duration,
}

impl Default for RetryConfig {
    fn default() -> Self {
        Self {
            max_retries: 3,
            base_delay: Duration::from_secs(1),
        }
    }
}

/// Whether a status code is retryable (transient).
pub fn is_retryable(status: StatusCode) -> bool {
    matches!(
        status,
        StatusCode::TOO_MANY_REQUESTS
            | StatusCode::SERVICE_UNAVAILABLE
            | StatusCode::GATEWAY_TIMEOUT
            | StatusCode::BAD_GATEWAY
    )
}

/// Compute the delay for the nth retry (exponential backoff).
pub fn retry_delay(config: &RetryConfig, attempt: u32) -> Duration {
    config.base_delay * 2u32.pow(attempt)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_is_retryable() {
        assert!(is_retryable(StatusCode::TOO_MANY_REQUESTS));
        assert!(is_retryable(StatusCode::SERVICE_UNAVAILABLE));
        assert!(is_retryable(StatusCode::GATEWAY_TIMEOUT));
        assert!(!is_retryable(StatusCode::OK));
        assert!(!is_retryable(StatusCode::NOT_FOUND));
        assert!(!is_retryable(StatusCode::BAD_REQUEST));
    }

    #[test]
    fn test_retry_delay_exponential() {
        let config = RetryConfig::default();
        assert_eq!(retry_delay(&config, 0), Duration::from_secs(1));
        assert_eq!(retry_delay(&config, 1), Duration::from_secs(2));
        assert_eq!(retry_delay(&config, 2), Duration::from_secs(4));
    }
}
