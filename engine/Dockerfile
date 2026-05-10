# Build stage
FROM rust:1.85-slim AS builder

RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency manifests + build script + proto for dep caching
COPY Cargo.toml Cargo.lock* ./
COPY build.rs ./
COPY proto/ proto/

# Create dummy src to download + compile dependencies (crate build may fail — that's fine)
RUN mkdir src && \
    echo 'fn main() {}' > src/main.rs && \
    echo '' > src/lib.rs && \
    cargo build --release 2>&1 || true && \
    rm -rf src && \
    rm -f target/release/deps/ukip_engine* target/release/deps/libukip_engine* \
          target/release/engine* target/release/libukip_engine*

# Build the real project
COPY src/ src/
COPY benches/ benches/
RUN touch src/main.rs src/lib.rs && cargo build --release

# Runtime stage
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y \
    ca-certificates \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/target/release/engine /app/engine

WORKDIR /app

ENTRYPOINT ["/app/engine"]
