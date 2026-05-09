fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Use vendored protoc so no system installation is required
    let protoc = protoc_bin_vendored::protoc_bin_path().unwrap();
    std::env::set_var("PROTOC", protoc);

    tonic_build::configure()
        .build_server(true)
        .build_client(true)
        .compile_protos(
            &["proto/ukip/engine/v1/engine.proto"],
            &["proto"],
        )?;
    Ok(())
}
