//! Token-bucket rate limiter for API sources.

use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::Mutex;
use tokio::time::{Duration, Instant};

/// Per-source token-bucket rate limiter.
#[derive(Clone)]
pub struct RateLimiter {
    buckets: Arc<Mutex<HashMap<String, Bucket>>>,
    tokens_per_second: f64,
    max_tokens: f64,
}

struct Bucket {
    tokens: f64,
    last_refill: Instant,
}

impl RateLimiter {
    /// Create a new rate limiter with the given tokens-per-second and burst capacity.
    pub fn new(tokens_per_second: f64, max_tokens: f64) -> Self {
        Self {
            buckets: Arc::new(Mutex::new(HashMap::new())),
            tokens_per_second,
            max_tokens,
        }
    }

    /// Wait until a token is available for the given source, then consume one.
    pub async fn acquire(&self, source: &str) {
        loop {
            let wait = {
                let mut buckets = self.buckets.lock().await;
                let bucket = buckets.entry(source.to_string()).or_insert_with(|| Bucket {
                    tokens: self.max_tokens,
                    last_refill: Instant::now(),
                });

                // Refill
                let now = Instant::now();
                let elapsed = now.duration_since(bucket.last_refill).as_secs_f64();
                bucket.tokens = (bucket.tokens + elapsed * self.tokens_per_second).min(self.max_tokens);
                bucket.last_refill = now;

                if bucket.tokens >= 1.0 {
                    bucket.tokens -= 1.0;
                    None
                } else {
                    // Compute wait time
                    let deficit = 1.0 - bucket.tokens;
                    Some(Duration::from_secs_f64(deficit / self.tokens_per_second))
                }
            };

            match wait {
                None => return,
                Some(d) => tokio::time::sleep(d).await,
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_rate_limiter_immediate_acquire() {
        let limiter = RateLimiter::new(10.0, 5.0);
        // First few should be instant (burst capacity)
        for _ in 0..5 {
            limiter.acquire("test").await;
        }
    }

    #[tokio::test]
    async fn test_rate_limiter_separate_sources() {
        let limiter = RateLimiter::new(10.0, 2.0);
        limiter.acquire("openalex").await;
        limiter.acquire("crossref").await;
        // Different sources use different buckets
    }
}
