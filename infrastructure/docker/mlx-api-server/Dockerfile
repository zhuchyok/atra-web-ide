# MLX API Server для Mac Studio M4 Max (Apple Silicon)
FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копирование requirements для MLX
COPY infrastructure/docker/mlx-api-server/requirements_mlx.txt .
RUN pip install --no-cache-dir -r requirements_mlx.txt

# Копирование кода MLX API Server
COPY knowledge_os/app/mlx_api_server.py .
COPY knowledge_os/app/mlx_router.py .

# Создание директорий
RUN mkdir -p /app/models /app/logs

# Переменные окружения
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV MLX_MODELS_DIR=/app/models

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:11434/ || exit 1

EXPOSE 11434

CMD ["python", "-m", "uvicorn", "mlx_api_server:app", "--host", "0.0.0.0", "--port", "11434"]

