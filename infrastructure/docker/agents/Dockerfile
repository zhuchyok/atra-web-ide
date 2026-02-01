# Dockerfile для агентов ATRA (Victoria, Veronica) — Mac Studio
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential libpq-dev curl git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt* ./
RUN pip install --no-cache-dir -r requirements.txt 2>/dev/null || \
    pip install fastapi uvicorn httpx pydantic aiohttp asyncpg python-dotenv moondream Pillow

COPY . .
RUN mkdir -p logs data cache

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "src.agents.bridge.victoria_server"]
