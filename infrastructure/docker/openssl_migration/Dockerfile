FROM python:3.11-slim

# Экспериментальный контейнер для проверки совместимости с OpenSSL ≥ 3 и urllib3 ≥ 2.
# Цель: воспроизвести рабочее окружение ATRA, установить обновлённые зависимости
# (requests/aiohttp/httpx/python-telegram-bot/urllib3) и прогнать smoke-тесты.

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /opt/atra

# Обновляем системные пакеты и ставим build-зависимости.
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
        build-essential \
        curl \
        git \
        libffi-dev \
        libssl-dev \
        libpq-dev \
        libxml2-dev \
        libxslt1-dev \
        pkg-config \
        sqlite3 \
        tzdata \
    && rm -rf /var/lib/apt/lists/*

# Копируем только файлы зависимостей, чтобы использовать layer caching.
COPY requirements.txt ./requirements.txt

# Дополняем базовые зависимости инструментами для тестирования и фиксируем urllib3>=2.
RUN python -m pip install --upgrade pip && \
    python -m pip install \
        -r requirements.txt \
        urllib3>=2.1.0 \
        requests>=2.32.0 \
        httpx>=0.28.1 \
        aiohttp>=3.13.2 \
        python-telegram-bot>=22.5 \
        pytest>=8.2 \
        pytest-asyncio>=0.23 \
        mypy>=1.11 \
        black>=24.8

# По умолчанию контейнер перейдёт в shell. Тесты запускаются через
#   docker run --rm -it atratest bash ./scripts/run_openssl_smoke_tests.sh
ENTRYPOINT ["/bin/bash"]

