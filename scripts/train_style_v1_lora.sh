#!/bin/bash
# Wave-4 style LoRA (refusals+facts+pairs) on qwen38-family MLX base.
# Off-live: does NOT pin Ollama :latest. Optional brain unload for RAM.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="${STYLE_LORA_DATA:-$ROOT/configs/training/style_v1}"
ADAPTER_PATH="${STYLE_LORA_ADAPTER:-$ROOT/configs/training/style_v1/adapters}"
MODEL_NAME="${MLX_LORA_BASE_MODEL:-$HOME/mlx-models/qwen38-27b-4bit}"
OLLAMA="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"

ITERS="${STYLE_LORA_ITERS:-40}"
LAYERS="${STYLE_LORA_LAYERS:-4}"
BATCH_SIZE="${STYLE_LORA_BATCH:-1}"
LR="${STYLE_LORA_LR:-1e-5}"
MAX_SEQ="${STYLE_LORA_MAX_SEQ:-1024}"
UNLOAD_BRAIN="${STYLE_LORA_UNLOAD_BRAIN:-true}"

_base_lc="$(echo "$MODEL_NAME" | tr '[:upper:]' '[:lower:]')"
case "$_base_lc" in
  *qwen2.5-3b*|*llama-3.2-3b*|*llama3.2*)
    echo "❌ Refusing wrong-family base: $MODEL_NAME"; exit 2 ;;
esac
case "$_base_lc" in
  *qwen3.8*|*qwen38*|*victoria-qwen38*) ;;
  *)
    echo "❌ Base must be qwen38 / Qwen3.8 family: $MODEL_NAME"; exit 2 ;;
esac

if [ ! -s "$DATA_DIR/train.jsonl" ] || [ ! -s "$DATA_DIR/valid.jsonl" ]; then
  echo "❌ Missing $DATA_DIR/{train,valid}.jsonl — run scripts/build_lora_style_corpus.py"
  exit 2
fi
if [ ! -e "$MODEL_NAME" ] && [[ "$MODEL_NAME" != */* ]]; then
  echo "❌ Model path missing: $MODEL_NAME"
  exit 2
fi
if [ ! -e "$MODEL_NAME/config.json" ] && [ ! -d "$MODEL_NAME" ]; then
  # HF id form also ok for mlx_lm
  true
fi

python3 "$ROOT/knowledge_os/scripts/evaluate_lora_gate.py" \
  --manifest "$DATA_DIR/manifest.json" \
  --min-train-samples 200 --min-eval-samples 40 \
  --fuse-target victoria-qwen38:latest --require-fuse \
  --report "$ROOT/docs/audits/lora-style-v1-canary-gate.md"

mkdir -p "$ADAPTER_PATH"

_restore_brain() {
  if [ "${_BRAIN_UNLOADED:-0}" = "1" ]; then
    echo "♻️ Reloading day brain victoria-qwen38:latest @16384…"
    curl -s "$OLLAMA/api/generate" -d '{"model":"victoria-qwen38:latest","prompt":"ping","stream":false,"keep_alive":"24h","options":{"num_ctx":16384,"num_predict":1}}' >/dev/null || true
    curl -s "$OLLAMA/api/ps" | python3 -c 'import sys,json; print("11434", [m.get("name") for m in json.load(sys.stdin).get("models",[])])' || true
  fi
}
trap _restore_brain EXIT

if [ "$UNLOAD_BRAIN" = "true" ] || [ "$UNLOAD_BRAIN" = "1" ]; then
  echo "⏸ Unloading 11434 brain for train window (restore on exit)…"
  if command -v ollama >/dev/null 2>&1; then
    ollama stop victoria-qwen38:latest >/dev/null 2>&1 || true
  fi
  curl -s "$OLLAMA/api/generate" -d '{"model":"victoria-qwen38:latest","prompt":"","keep_alive":0,"stream":false}' >/dev/null || true
  sleep 3
  _BRAIN_UNLOADED=1
  curl -s "$OLLAMA/api/ps" | python3 -c 'import sys,json; print("11434 after unload", [m.get("name") for m in json.load(sys.stdin).get("models",[])])' || true
fi

RESUME_ARGS=()
if [ "${STYLE_LORA_RESUME:-true}" = "true" ] || [ "${STYLE_LORA_RESUME:-true}" = "1" ]; then
  if [ -s "$ADAPTER_PATH/adapters.safetensors" ]; then
    echo "♻️ Resume from $ADAPTER_PATH/adapters.safetensors"
    RESUME_ARGS+=(--resume-adapter-file "$ADAPTER_PATH/adapters.safetensors")
  fi
fi

echo "🚀 style_v1 LoRA"
echo "  model=$MODEL_NAME"
echo "  data=$DATA_DIR"
echo "  adapter=$ADAPTER_PATH"
echo "  iters=$ITERS layers=$LAYERS batch=$BATCH_SIZE seq=$MAX_SEQ"

export MLX_MAX_BATCH_SIZE=1
python3 -m mlx_lm lora \
  --model "$MODEL_NAME" \
  --train \
  --data "$DATA_DIR" \
  --fine-tune-type lora \
  --mask-prompt \
  --batch-size "$BATCH_SIZE" \
  --iters "$ITERS" \
  --num-layers "$LAYERS" \
  --learning-rate "$LR" \
  --max-seq-length "$MAX_SEQ" \
  --grad-checkpoint \
  --adapter-path "$ADAPTER_PATH" \
  --save-every 50 \
  --steps-per-report 10 \
  --steps-per-eval 50 \
  --val-batches 4 \
  "${RESUME_ARGS[@]}"

echo "✅ style_v1 adapters → $ADAPTER_PATH"
echo "⚠ NOT fused / NOT pinned to day. Run canary before promote."
