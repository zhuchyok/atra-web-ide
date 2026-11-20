#!/usr/bin/env bash
# LIVE RAG quality (Mac Studio / host with Ollama + Postgres).
# Fail-closed: missing Ollama/DB → exit 1 (never silent green).
#
# One-liner:
#   LIVE_RAG_QUALITY=1 ./scripts/run_live_rag_quality.sh
#
# Hands Ollama (nomic) defaults to :11437; override with OLLAMA_URL if needed.
# PR CI stays on --mode reference_smoke (see .github/workflows/quality-validation.yml).

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

if [ -f "$REPO_ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$REPO_ROOT/.env"
  set +a
fi

export LIVE_RAG_QUALITY=1
# Embeddings (nomic) live on hands 11437 on Mac Studio; brain 11434 has victoria-qwen38 only.
# Prefer LIVE_OLLAMA_URL / OLLAMA_EMBED_URL so a brain-only OLLAMA_URL from .env cannot hijack embeds.
export OLLAMA_URL="${LIVE_OLLAMA_URL:-${OLLAMA_EMBED_URL:-http://127.0.0.1:11437}}"
export DATABASE_URL="${DATABASE_URL:-postgresql://admin:secret@localhost:5432/knowledge_os}"
export PYTHONPATH="${REPO_ROOT}/backend:${REPO_ROOT}${PYTHONPATH:+:$PYTHONPATH}"
export RERANKING_ENABLED="${RERANKING_ENABLED:-false}"
# Require nomic on the Ollama used for live embeds (no silent MiniLM dim-mismatch greenwash).
export LIVE_RAG_REQUIRE_NOMIC="${LIVE_RAG_REQUIRE_NOMIC:-1}"

if [ -x "${REPO_ROOT}/backend/.venv/bin/python3" ]; then
  PYTHON="${REPO_ROOT}/backend/.venv/bin/python3"
else
  PYTHON="${PYTHON:-python3}"
fi

OUT_DIR="${REPO_ROOT}/logs"
mkdir -p "$OUT_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
REPORT="${OUT_DIR}/rag_quality_live_${STAMP}.json"
LATEST="${OUT_DIR}/rag_quality_live.json"

echo "=== LIVE RAG quality ==="
echo "OLLAMA_URL=$OLLAMA_URL"
echo "report=$REPORT"

# RAG_LIVE_LIMIT defaults to 20 for host smoke; set 0 for full dataset.
LIMIT_ARGS=()
SEED_LIMIT_ARGS=()
if [ "${RAG_LIVE_LIMIT:-20}" != "0" ]; then
  LIMIT_ARGS=(--limit "${RAG_LIVE_LIMIT:-20}")
  SEED_LIMIT_ARGS=(--limit "${RAG_LIVE_LIMIT:-20}")
fi

# Relevance is F1(response, reference). Without seed_dataset Q/A nodes, vector/keyword
# hits land on corpus noise → faithfulness≈1, relevance≈0. Seed is required, not optional.
if [ "${RAG_LIVE_SKIP_SEED:-0}" != "1" ]; then
  echo "=== Ensuring seed_dataset Q/A in knowledge_nodes ==="
  "$PYTHON" -u scripts/seed_knowledge_from_dataset.py "${SEED_LIMIT_ARGS[@]}"
fi

set +e
"$PYTHON" -u scripts/evaluate_rag_quality.py \
  --mode live \
  --require-live \
  --dataset data/validation_queries.json \
  "${LIMIT_ARGS[@]}" \
  --threshold faithfulness:0.8,relevance:0.85,coherence:0.7 \
  --output "$REPORT" \
  --timeout-per-query "${RAG_LIVE_TIMEOUT_PER_QUERY:-30}" \
  --verbose
EVAL_EC=$?
set -e

if [ -f "$REPORT" ]; then
  cp -f "$REPORT" "$LATEST"
  echo "Report saved: $REPORT (also $LATEST)"
else
  echo "LIVE RAG FAIL: report missing after evaluate" >&2
  exit 1
fi

set +e
"$PYTHON" scripts/check_quality_thresholds.py "$REPORT" \
  --require-mode live \
  --threshold faithfulness:0.8,relevance:0.85,coherence:0.7
GATE_EC=$?
set -e

if [ "$EVAL_EC" -ne 0 ] || [ "$GATE_EC" -ne 0 ]; then
  echo "LIVE RAG FAIL: evaluate_exit=$EVAL_EC thresholds_exit=$GATE_EC (honest; see $REPORT)" >&2
  exit 1
fi
echo "OK: live report at $REPORT (also $LATEST)"
