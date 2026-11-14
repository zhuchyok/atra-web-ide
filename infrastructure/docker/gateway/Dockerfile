# Rust Gateway (atra-cli chat → Victoria/Ollama). Сборка из корня воркспейса.
# Сборка: из корня репо: docker build -f infrastructure/docker/gateway/Dockerfile -t atra-gateway .
# Запуск: порт 8081, нужны DATABASE_URL, VICTORIA_URL, OLLAMA_URL (в Docker: host.docker.internal:11434)

# --- Stage 1: Builder ---
FROM rust:1-slim-bookworm AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Копируем воркспейс (корень + rust_core)
COPY Cargo.toml Cargo.lock ./
COPY rust_core ./rust_core

# Сборка gateway (knowledge_engine — зависимость)
RUN cargo build -p gateway --release

# --- Stage 2: Runtime ---
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates libssl3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /build/target/release/gateway /app/gateway

EXPOSE 8081

ENV RUST_LOG=info

CMD ["/app/gateway"]
