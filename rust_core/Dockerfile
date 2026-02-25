# ============================================
# Stage 1: Builder
# ============================================
FROM rust:1.75-slim-bookworm as builder

WORKDIR /usr/src/atra

# Установка зависимостей для сборки
RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Копируем Cargo файлы для кэширования слоев
COPY Cargo.toml .
COPY atra-core/Cargo.toml atra-core/
COPY atra-ai/Cargo.toml atra-ai/
COPY atra-tenant/Cargo.toml atra-tenant/
COPY atra-calc/Cargo.toml atra-calc/

# Создаем пустые файлы для предварительной компиляции зависимостей
RUN mkdir -p atra-core/src atra-ai/src atra-tenant/src atra-calc/src \
    && echo "fn main() {}" > atra-core/src/main.rs \
    && echo "" > atra-ai/src/lib.rs \
    && echo "" > atra-tenant/src/lib.rs \
    && echo "" > atra-calc/src/lib.rs

# Предварительная сборка зависимостей
RUN cargo build --release

# Копируем реальный исходный код
COPY . .

# Финальная сборка
RUN cargo build --release

# ============================================
# Stage 2: Runtime
# ============================================
FROM debian:bookworm-slim

WORKDIR /app

# Установка системных библиотек
RUN apt-get update && apt-get install -y \
    libssl3 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Копируем бинарный файл из builder
COPY --from=builder /usr/src/atra/target/release/atra-core /app/atra-core

# Порт для Rust Kernel
EXPOSE 8081

CMD ["./atra-core"]
