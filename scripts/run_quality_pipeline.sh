#!/bin/bash
# Фаза 4: полный пайплайн качества RAG
# Запуск: из корня репозитория: ./scripts/run_quality_pipeline.sh

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
PIPELINE_FAIL=0

echo "🚀 Запуск пайплайна качества"

# Используем venv backend если есть (нужны asyncpg, httpx, app.*)
if [ -x "${REPO_ROOT}/backend/.venv/bin/python3" ]; then
  PYTHON="${REPO_ROOT}/backend/.venv/bin/python3"
else
  PYTHON="${PYTHON:-python3}"
fi
export PYTHONPATH="${REPO_ROOT}/backend:${REPO_ROOT}"

# 1. Валидация на validation set (с реранкингом для повышения метрик)
echo "1. Валидация..."
export RERANKING_ENABLED="${RERANKING_ENABLED:-true}"
if [ ! -f data/validation_queries.json ]; then
  echo "❌ Нет data/validation_queries.json"
  PIPELINE_FAIL=1
else
  if ! $PYTHON scripts/evaluate_rag_quality.py \
    --dataset data/validation_queries.json \
    --threshold faithfulness:0.8,relevance:0.85,coherence:0.7 \
    --output backend/validation_report.json \
    --timeout-per-query 5 \
    --verbose; then
    PIPELINE_FAIL=1
  fi
fi

# Missing report must not green-pass
if [ ! -f backend/validation_report.json ]; then
  echo '{"avg_metrics":{},"total_queries":0,"passed":false,"skipped":true}' > backend/validation_report.json
  PIPELINE_FAIL=1
fi

# 2–4. Best-effort report gens (do not mask validation failures)
if [ -f scripts/analyze_feedback.py ]; then
  echo "2. Анализ обратной связи..."
  $PYTHON scripts/analyze_feedback.py --days 7 2>/dev/null || true
fi
if [ -f scripts/run_auto_improvements.py ]; then
  echo "3. Автоулучшения..."
  $PYTHON scripts/run_auto_improvements.py 2>/dev/null || true
fi
if [ -f scripts/generate_quality_report.py ]; then
  echo "4. Генерация отчёта..."
  $PYTHON scripts/generate_quality_report.py \
    --validation backend/validation_report.json \
    --output quality_report.html 2>/dev/null || true
fi
if [ -f scripts/create_simple_dashboard.py ] && [ -f backend/validation_report.json ]; then
  echo "   Дашборд..."
  $PYTHON scripts/create_simple_dashboard.py 2>/dev/null || true
fi
if [ -f scripts/benchmark_latency.py ]; then
  echo "   Latency бенчмарк..."
  if command -v timeout >/dev/null 2>&1; then
    if ! timeout 45 $PYTHON scripts/benchmark_latency.py 2>/dev/null; then
      PIPELINE_FAIL=1
    fi
  else
    if ! $PYTHON scripts/benchmark_latency.py 2>/dev/null; then
      PIPELINE_FAIL=1
    fi
  fi
fi
if [ -f scripts/create_latency_dashboard.py ] && [ -f latency_benchmark.json ]; then
  $PYTHON scripts/create_latency_dashboard.py 2>/dev/null || true
fi

# 5. Проверка порогов — critical
if [ -f scripts/check_quality_thresholds.py ] && [ -f backend/validation_report.json ]; then
  echo "5. Проверка порогов..."
  if ! $PYTHON scripts/check_quality_thresholds.py backend/validation_report.json \
    --threshold faithfulness:0.8,relevance:0.85,coherence:0.7; then
    echo "⚠️ Пороги не пройдены. Self-healing: $PYTHON scripts/quality_heal_rag_cache.py && ./scripts/run_quality_pipeline.sh"
    PIPELINE_FAIL=1
  fi
  if [ -f scripts/analyze_low_relevance.py ]; then
    echo "5a. Анализ проблемных запросов..."
    $PYTHON scripts/analyze_low_relevance.py 0.85 2>/dev/null || true
  fi
fi

# 6. Алерты
if [ -f scripts/check_quality_alerts.py ]; then
  echo "6. Проверка алертов..."
  if ! $PYTHON scripts/check_quality_alerts.py \
    --report backend/validation_report.json \
    --threshold faithfulness:0.8,relevance:0.85,coherence:0.7 2>/dev/null; then
    PIPELINE_FAIL=1
  fi
fi

if [ "$PIPELINE_FAIL" -eq 0 ]; then
  echo "✅ Пайплайн качества завершён"
else
  echo "⚠️ Пайплайн качества завершён С ОШИБКАМИ"
fi
exit "$PIPELINE_FAIL"
