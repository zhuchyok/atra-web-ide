#!/usr/bin/env bash
set -euo pipefail

# Smoke-тест для окружения с OpenSSL>=3 и urllib3>=2.
# Используется внутри Docker образа infrastructure/docker/openssl_migration/.

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"

echo "🔁 Recreating virtual environment..."
python -m venv .venv-openssl
source .venv-openssl/bin/activate

echo "📦 Installing dependencies (urllib3>=2)..."
pip install --upgrade pip
pip install -r requirements.txt
pip install --upgrade \
    urllib3>=2.1.0 \
    requests>=2.32.0 \
    httpx>=0.28.1 \
    aiohttp>=3.13.2 \
    python-telegram-bot>=22.5

echo "📍 Environment diagnostics:"
python - <<'PY'
import ssl, urllib3
print("Python version:", ssl.OPENSSL_VERSION)
print("urllib3 version:", urllib3.__version__)
PY

echo "🧪 Running unit tests..."
pytest tests/unit

echo "🌀 Flash crash stress test..."
python scripts/run_flash_crash_stress_test.py --symbol BTCUSDT --output /tmp/flash.json

echo "💧 Liquidity crisis stress test..."
python scripts/run_liquidity_crisis_test.py --symbol BTCUSDT --output /tmp/liquidity.json

echo "📨 Telegram risk status dry run..."
python scripts/send_risk_status_report.py --dry-run

echo "✅ Smoke tests completed under OpenSSL migration sandbox."

