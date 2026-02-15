#!/usr/bin/env bash
# Замер coverage baseline (PROJECT_GAPS §3, CHANGES §0.4g)
# Запуск: ./scripts/measure_coverage_baseline.sh
# Результат: coverage.xml, вывод в stdout; затем обновить COVERAGE_FAIL_UNDER в CI
# Требуется: knowledge_os/.venv (bash knowledge_os/scripts/setup_knowledge_os.sh)
set -e

cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD"

PYTHON="${PYTHON:-python3}"
if [ -x "knowledge_os/.venv/bin/python" ]; then
  PYTHON="knowledge_os/.venv/bin/python"
fi

echo "=== Measure coverage baseline (no DB) ==="
$PYTHON -m pip install pytest pytest-asyncio pytest-cov orjson httpx -q 2>/dev/null || true
$PYTHON -m pip install -r knowledge_os/requirements.txt -q 2>/dev/null || true

$PYTHON -m pytest knowledge_os/tests/test_json_fast_http_client.py -v --tb=short \
  --cov=knowledge_os.app --cov-report=xml --cov-report=term-missing --no-cov-on-fail \
  --cov-fail-under=0

echo ""
echo "=== Coverage baseline measured. Update COVERAGE_FAIL_UNDER in .github/workflows/pytest-knowledge-os.yml (e.g. 5 or 10) ==="
