use std::process;
use std::sync::Arc;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = std::env::args().collect();
    if args.iter().any(|a| a == "--health-check") {
        // Verify the gRPC port is open with a TCP probe.
        let port: u16 = std::env::var("ENGINE_GRPC_PORT")
            .ok()
            .and_then(|v| v.parse().ok())
            .unwrap_or(50051);
        let addr = format!("127.0.0.1:{}", port);
        let sock_addr: std::net::SocketAddr = match addr.parse() {
            Ok(a) => a,
            Err(e) => {
                eprintln!("invalid address '{}': {}", addr, e);
                process::exit(1);
            }
        };
        match std::net::TcpStream::connect_timeout(
            &sock_addr,
            std::time::Duration::from_secs(2),
        ) {
            Ok(_) => {
                println!("healthy");
                process::exit(0);
            }
            Err(e) => {
                eprintln!("health check failed: {}", e);
                process::exit(1);
            }
        }
    }

    // Init tracing
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into()),
        )
        .json()
        .init();

    let config =
        ukip_engine::config::Config::from_env().map_err(Box::<dyn std::error::Error>::from)?;
    let pool = ukip_engine::db::pool::create_pool(&config.database_url).await?;

    // Ensure engine_jobs table exists
    ukip_engine::db::job_store::ensure_table(&pool).await?;

    // Create job manager backed by Postgres
    let job_manager = Arc::new(ukip_engine::jobs::JobManager::with_pool(
        config.max_concurrent_jobs,
        pool.clone(),
    ));

    // Startup recovery: mark stale running/queued jobs as failed
    job_manager.recover_stale_jobs().await?;

    // Build pipeline registry
    let mut registry = ukip_engine::pipelines::PipelineRegistry::new_empty();
    registry.register(Arc::new(
        ukip_engine::pipelines::graph::GraphMaterializationPipeline,
    ));
    registry.register(Arc::new(
        ukip_engine::pipelines::text_analysis::TextAnalysisPipeline,
    ));
    registry.register(Arc::new(
        ukip_engine::pipelines::authority::AuthorityPipeline,
    ));
    registry.register(Arc::new(
        ukip_engine::pipelines::analytics::AnalyticsPipeline,
    ));
    registry.register(Arc::new(
        ukip_engine::pipelines::disambiguation::DisambiguationPipeline,
    ));
    registry.register(Arc::new(
        ukip_engine::pipelines::normalization::NormalizationPipeline,
    ));
    registry.register(Arc::new(
        ukip_engine::pipelines::connectors::ConnectorPipeline::new()
            .map_err(|e| format!("failed to initialize connector pipeline: {}", e))?,
    ));

    let router = Arc::new(ukip_engine::router::Router::new(registry));

    let addr = format!("0.0.0.0:{}", config.grpc_port).parse()?;
    tracing::info!(%addr, "starting ukip-engine");

    let auth_token = config.auth_token.clone();
    let shutdown_timeout = std::time::Duration::from_secs(config.shutdown_timeout_secs);
    let svc =
        ukip_engine::server::EngineService::new(router, job_manager.clone(), pool.clone(), config);
    let interceptor = ukip_engine::server::auth_interceptor(auth_token);

    // Spawn cache eviction task: remove completed/failed jobs from DashMap after 60s
    let eviction_mgr = job_manager.clone();
    tokio::spawn(async move {
        let mut interval = tokio::time::interval(std::time::Duration::from_secs(30));
        loop {
            interval.tick().await;
            eviction_mgr.evict_stale_cache(60);
        }
    });

    let (shutdown_tx, shutdown_rx) = tokio::sync::oneshot::channel::<()>();

    tokio::spawn(async move {
        tokio::signal::ctrl_c().await.ok();
        tracing::info!("received shutdown signal");
        let _ = shutdown_tx.send(());
    });

    tonic::transport::Server::builder()
        .add_service(
            ukip_engine::proto::engine_server::EngineServer::with_interceptor(svc, interceptor),
        )
        .serve_with_shutdown(addr, async {
            shutdown_rx.await.ok();
        })
        .await?;

    // After server stops: mark in-flight jobs as failed with timeout, close DB pool
    tracing::info!("shutting down, waiting up to {:?} for cleanup", shutdown_timeout);
    let cleanup = async {
        job_manager.fail_all_active("engine shutdown").await;
        pool.close().await;
    };
    if tokio::time::timeout(shutdown_timeout, cleanup).await.is_err() {
        tracing::warn!("shutdown cleanup timed out after {:?}", shutdown_timeout);
    }

    Ok(())
}
