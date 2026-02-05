# Dockerfile для агентов ATRA (Victoria, Veronica, knowledge_os_worker) — Mac Studio
# Мировая практика: multi-stage — Rust-расширение собирается в builder, в образ попадает только wheel

# --- Stage 0: сборка cache_normalizer (Rust/PyO3) ---
FROM python:3.11-slim AS cache_normalizer_builder
WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Rust (rustup)
ENV RUSTUP_INIT_SKIP_PATH_CHECK=yes
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Только исходники расширения (не весь репо)
COPY knowledge_os/cache_normalizer_rs /build/cache_normalizer_rs

RUN pip install --no-cache-dir maturin \
    && cd /build/cache_normalizer_rs \
    && maturin build --release -o /out

# --- Stage 1: рантайм-образ ---
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential libpq-dev curl git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt* ./
RUN pip install --no-cache-dir -r requirements.txt 2>/dev/null || \
    pip install fastapi uvicorn httpx pydantic aiohttp asyncpg python-dotenv moondream Pillow

# Установка Rust-модуля из builder (мировая практика: один слой, без Rust в финальном образе)
COPY --from=cache_normalizer_builder /out/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/cache_normalizer*.whl && rm /tmp/cache_normalizer*.whl

COPY . .
RUN mkdir -p logs data cache

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "src.agents.bridge.victoria_server"]
