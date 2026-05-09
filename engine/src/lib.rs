pub mod config;
pub mod db;
pub mod jobs;
pub mod pipelines;
pub mod progress;
pub mod router;
pub mod server;

pub mod proto {
    tonic::include_proto!("ukip.engine.v1");
}
