use std::env;

#[derive(Debug, Clone)]
pub struct Config {
    pub database_url: String,
    pub grpc_port: u16,
    pub log_level: String,
    pub node_chunk_size: usize,
    pub rel_chunk_size: usize,
    pub auth_token: Option<String>,
    pub max_concurrent_jobs: usize,
    pub shutdown_timeout_secs: u64,
}

impl Config {
    pub fn from_env() -> Result<Self, String> {
        let database_url = env::var("ENGINE_DATABASE_URL")
            .map_err(|_| "ENGINE_DATABASE_URL is required")?;

        Ok(Self {
            database_url,
            grpc_port: parse_env("ENGINE_GRPC_PORT", 50051),
            log_level: env::var("ENGINE_LOG_LEVEL").unwrap_or_else(|_| "info".to_string()),
            node_chunk_size: parse_env("ENGINE_NODE_CHUNK_SIZE", 1000),
            rel_chunk_size: parse_env("ENGINE_REL_CHUNK_SIZE", 2000),
            auth_token: env::var("ENGINE_AUTH_TOKEN").ok(),
            max_concurrent_jobs: parse_env("ENGINE_MAX_CONCURRENT_JOBS", 4),
            shutdown_timeout_secs: parse_env("ENGINE_SHUTDOWN_TIMEOUT_SECS", 60),
        })
    }
}

fn parse_env<T: std::str::FromStr>(key: &str, default: T) -> T {
    env::var(key)
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(default)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_config() {
        let config = Config {
            database_url: "postgresql://test:test@localhost/test".to_string(),
            grpc_port: 50051,
            log_level: "info".to_string(),
            node_chunk_size: 1000,
            rel_chunk_size: 2000,
            auth_token: None,
            max_concurrent_jobs: 4,
            shutdown_timeout_secs: 60,
        };
        assert_eq!(config.grpc_port, 50051);
        assert_eq!(config.node_chunk_size, 1000);
    }

    #[test]
    fn test_config_from_env() {
        std::env::set_var("ENGINE_DATABASE_URL", "postgresql://x:x@localhost/x");
        std::env::set_var("ENGINE_GRPC_PORT", "9999");
        let config = Config::from_env().unwrap();
        assert_eq!(config.grpc_port, 9999);
        std::env::remove_var("ENGINE_DATABASE_URL");
        std::env::remove_var("ENGINE_GRPC_PORT");
    }
}
