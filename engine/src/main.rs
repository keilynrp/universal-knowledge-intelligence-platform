use std::process;
use std::sync::Arc;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = std::env::args().collect();
    if args.iter().any(|a| a == "--health-check") {
        // TODO: implement real health check via gRPC reflection
        println!("healthy");
        process::exit(0);
    }

    // Init tracing
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "info".into()),
        )
        .json()
        .init();

    let config = ukip_engine::config::Config::from_env()
        .map_err(|e| Box::<dyn std::error::Error>::from(e))?;
    let pool = ukip_engine::db::pool::create_pool(&config.database_url).await?;
    let job_manager = Arc::new(ukip_engine::jobs::JobManager::new(config.max_concurrent_jobs));

    // Build pipeline registry
    let mut registry = ukip_engine::pipelines::PipelineRegistry::new_empty();
    registry.register(Arc::new(ukip_engine::pipelines::graph::GraphMaterializationPipeline));
    registry.register(Arc::new(ukip_engine::pipelines::text_analysis::TextAnalysisPipeline));

    let router = Arc::new(ukip_engine::router::Router::new(registry));

    let addr = format!("0.0.0.0:{}", config.grpc_port).parse()?;
    tracing::info!(%addr, "starting ukip-engine");

    let svc = ukip_engine::server::EngineService::new(router, job_manager.clone(), pool.clone(), config);

    let (shutdown_tx, shutdown_rx) = tokio::sync::oneshot::channel::<()>();

    tokio::spawn(async move {
        tokio::signal::ctrl_c().await.ok();
        tracing::info!("received shutdown signal");
        let _ = shutdown_tx.send(());
    });

    tonic::transport::Server::builder()
        .add_service(ukip_engine::proto::engine_server::EngineServer::new(svc))
        .serve_with_shutdown(addr, async {
            shutdown_rx.await.ok();
        })
        .await?;

    // After server stops: mark in-flight jobs as failed, close DB pool
    job_manager.fail_all_active("engine shutdown");
    pool.close().await;

    Ok(())
}
