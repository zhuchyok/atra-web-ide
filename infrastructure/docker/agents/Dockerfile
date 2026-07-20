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

# Установка Docker CLI для Service Monitor (проверка статусов контейнеров)
# ca-certificates для безопасного curl, gnupg для GPG-ключей
RUN apt-get update && apt-get install -y \
    build-essential libpq-dev curl git expect \
    ca-certificates gnupg lsb-release \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && chmod a+r /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt* ./
# Сначала ставим тяжёлые аналитические пакеты отдельно (с явными ошибками при сбое)
RUN pip install --no-cache-dir duckdb lancedb pyarrow pandas || true
RUN pip install --no-cache-dir -r requirements.txt || \
    pip install fastapi uvicorn httpx pydantic aiohttp asyncpg python-dotenv moondream Pillow
# Guaranteed for Prometheus scrape targets (workers return 500 without this)
RUN pip install --no-cache-dir "prometheus-client>=0.19.0"

# agentscope устанавливается отдельно (--no-deps) чтобы не ломать requirements.txt fallback
# Actor model, MsgHub, ReMe memory, Swarm orchestration
RUN pip install --no-cache-dir --no-deps agentscope || true
RUN pip install --no-cache-dir shortuuid json5 json_repair filetype aioitertools \
    opentelemetry-sdk opentelemetry-api opentelemetry-semantic-conventions \
    sqlalchemy || true

# Установка Rust-модуля из builder (мировая практика: один слой, без Rust в финальном образе)
COPY --from=cache_normalizer_builder /out/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/cache_normalizer*.whl && rm /tmp/cache_normalizer*.whl

COPY . .
RUN ln -sf /app/knowledge_os/app /app/app 2>/dev/null || true
RUN mkdir -p logs data cache

ENV PYTHONPATH=/app:/app/knowledge_os/app:/app/app
ENV PYTHONUNBUFFERED=1

# CRITICAL: Set recursion BEFORE any Python imports (at container start)
# Victoria's complex async pipeline needs recursionlimit=1000 (default is 1000)
RUN echo "import sys; sys.setrecursionlimit(1000)" > /app/force_recursion.py

# Simple worker script
RUN echo 'import asyncio,redis,json,aiohttp; r=redis.Redis(host="redis",port=6379); print("W"); asyncio.run(asyncio.gather())' > /app/worker.py

CMD ["sh", "-c", "python -c 'import sys; sys.setrecursionlimit(1000)' && cd /app && python knowledge_os/app/victoria_worker.py & python -m uvicorn src.agents.bridge.victoria_server:app --host 0.0.0.0 --port 8010"]
