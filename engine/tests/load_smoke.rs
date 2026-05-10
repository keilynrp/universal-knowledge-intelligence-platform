use std::time::Instant;

use ukip_engine::config::Config;
use ukip_engine::pipelines::graph::nodes::extract_nodes;
use ukip_engine::pipelines::graph::relationships::compute_relationships;
use ukip_engine::pipelines::graph::GraphMaterializationPipeline;
use ukip_engine::pipelines::{Pipeline, PipelineContext, PipelineInput};
use ukip_engine::progress::ProgressTracker;
use ukip_engine::proto::{Author, Identifier, Publication};

fn load_size() -> usize {
    std::env::var("UKIP_ENGINE_LOAD_SIZE")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(10_000)
}

fn make_publications(n: usize) -> Vec<Publication> {
    (0..n)
        .map(|i| Publication {
            entity_id: i as i64 + 1,
            title: format!("Load Smoke Publication {}", i),
            doi: Some(format!("10.5555/load-smoke-{}", i)),
            year: Some(2026),
            source_title: Some("UKIP Load Smoke Journal".to_string()),
            publisher: Some("UKIP".to_string()),
            authors: vec![
                Author {
                    name: format!("Author A{}", i),
                    order: Some(1),
                    affiliations: vec![format!("Institute {}", i % 100)],
                    ..Default::default()
                },
                Author {
                    name: format!("Author B{}", i),
                    order: Some(2),
                    affiliations: vec![format!("Institute {}", (i + 1) % 100)],
                    ..Default::default()
                },
            ],
            concepts: vec!["Machine Learning".to_string(), format!("Topic {}", i % 50)],
            identifiers: vec![Identifier {
                scheme: "doi".to_string(),
                value: format!("10.5555/load-smoke-{}", i),
            }],
            ..Default::default()
        })
        .collect()
}

async fn prepare_minimal_schema(pool: &sqlx::PgPool) -> Result<(), sqlx::Error> {
    sqlx::query("DROP TABLE IF EXISTS entity_relationships")
        .execute(pool)
        .await?;
    sqlx::query("DROP TABLE IF EXISTS raw_entities")
        .execute(pool)
        .await?;
    sqlx::query(
        "CREATE TABLE raw_entities (
            id BIGSERIAL PRIMARY KEY,
            org_id BIGINT NULL,
            import_batch_id BIGINT NULL,
            domain TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            primary_label TEXT NOT NULL,
            secondary_label TEXT NULL,
            canonical_id TEXT NOT NULL,
            attributes_json TEXT NOT NULL,
            source TEXT NOT NULL,
            enrichment_source TEXT NULL,
            enrichment_concepts TEXT NULL,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )",
    )
    .execute(pool)
    .await?;
    sqlx::query(
        "CREATE TABLE entity_relationships (
            id BIGSERIAL PRIMARY KEY,
            org_id BIGINT NULL,
            source_id BIGINT NOT NULL REFERENCES raw_entities(id),
            target_id BIGINT NOT NULL REFERENCES raw_entities(id),
            relation_type TEXT NOT NULL,
            weight DOUBLE PRECISION NOT NULL
        )",
    )
    .execute(pool)
    .await?;
    sqlx::query(
        "CREATE UNIQUE INDEX uq_raw_entities_canonical
         ON raw_entities (org_id, domain, entity_type, canonical_id)
         WHERE org_id IS NOT NULL",
    )
    .execute(pool)
    .await?;
    sqlx::query(
        "CREATE UNIQUE INDEX uq_raw_entities_canonical_global
         ON raw_entities (domain, entity_type, canonical_id)
         WHERE org_id IS NULL",
    )
    .execute(pool)
    .await?;
    sqlx::query(
        "CREATE UNIQUE INDEX uq_entity_relationships_pair
         ON entity_relationships (org_id, source_id, target_id, relation_type)
         WHERE org_id IS NOT NULL",
    )
    .execute(pool)
    .await?;
    sqlx::query(
        "CREATE UNIQUE INDEX uq_entity_relationships_pair_global
         ON entity_relationships (source_id, target_id, relation_type)
         WHERE org_id IS NULL",
    )
    .execute(pool)
    .await?;
    Ok(())
}

#[tokio::test]
#[ignore = "requires a disposable PostgreSQL database and UKIP_ENGINE_LOAD_TEST=1"]
async fn graph_materialization_large_batch_postgres_smoke() {
    assert_eq!(
        std::env::var("UKIP_ENGINE_LOAD_TEST").as_deref(),
        Ok("1"),
        "Set UKIP_ENGINE_LOAD_TEST=1 to confirm this can reset its target database"
    );
    let database_url = std::env::var("ENGINE_DATABASE_URL")
        .expect("ENGINE_DATABASE_URL must point to a disposable PostgreSQL database");
    assert!(
        database_url.contains("ukip_engine_load"),
        "Refusing to run destructive load smoke test unless database URL contains ukip_engine_load"
    );

    let pool = ukip_engine::db::pool::create_pool(&database_url)
        .await
        .expect("connect to PostgreSQL");
    prepare_minimal_schema(&pool).await.expect("prepare schema");

    let n = load_size();
    let input = PipelineInput {
        job_id: "load-smoke".to_string(),
        import_batch_id: 1,
        org_id: None,
        domain: "science".to_string(),
        publications: make_publications(n),
        options: Default::default(),
    };
    let ctx = PipelineContext {
        pool: pool.clone(),
        config: Config {
            database_url,
            grpc_port: 50051,
            log_level: "info".to_string(),
            node_chunk_size: 2_000,
            rel_chunk_size: 5_000,
            auth_token: None,
            max_concurrent_jobs: 4,
            shutdown_timeout_secs: 60,
        },
        progress: ProgressTracker::new("load-smoke".to_string()),
    };

    let started = Instant::now();
    let output = GraphMaterializationPipeline
        .process(input.clone(), &ctx)
        .await
        .expect("graph materialization succeeds");
    let elapsed = started.elapsed();

    assert!(output.nodes_created > 0);
    assert!(output.relationships_created > 0);
    println!(
        "load_smoke size={} elapsed_ms={} nodes_created={} relationships_created={}",
        n,
        elapsed.as_millis(),
        output.nodes_created,
        output.relationships_created
    );

    let second_started = Instant::now();
    let second_output = GraphMaterializationPipeline
        .process(input, &ctx)
        .await
        .expect("graph materialization is idempotent");
    let second_elapsed = second_started.elapsed();

    assert_eq!(second_output.nodes_created, 0);
    assert_eq!(second_output.relationships_created, 0);
    assert!(second_output.nodes_deduplicated > 0);
    println!(
        "load_smoke_idempotency size={} elapsed_ms={} nodes_deduplicated={}",
        n,
        second_elapsed.as_millis(),
        second_output.nodes_deduplicated
    );

    pool.close().await;
}

#[test]
#[ignore = "CPU/memory stress test; set UKIP_ENGINE_SYNTHETIC_EXTREME=1"]
fn graph_extraction_one_million_synthetic_extreme() {
    assert_eq!(
        std::env::var("UKIP_ENGINE_SYNTHETIC_EXTREME").as_deref(),
        Ok("1"),
        "Set UKIP_ENGINE_SYNTHETIC_EXTREME=1 to run the 1M synthetic stress test"
    );

    let n = std::env::var("UKIP_ENGINE_SYNTHETIC_SIZE")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(1_000_000);
    let publications = make_publications(n);

    let started = Instant::now();
    let mut node_count = 0usize;
    let mut relationship_count = 0usize;
    for publication in &publications {
        node_count += extract_nodes(publication, None, 1, "science").len();
        relationship_count += compute_relationships(
            publication.entity_id,
            &format!("pub:{}", publication.entity_id),
            publication,
            None,
        )
        .len();
    }
    let elapsed = started.elapsed();

    assert!(node_count >= n);
    assert!(relationship_count >= n);
    println!(
        "synthetic_extreme size={} elapsed_ms={} nodes_extracted={} relationships_computed={}",
        n,
        elapsed.as_millis(),
        node_count,
        relationship_count
    );
}
