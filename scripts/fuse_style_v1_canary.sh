#!/usr/bin/env bash
# Fuse style LoRA → GGUF → Ollama tag (default :style-canary, NEVER :latest).
#
# Pipeline (facts 2026-11-24):
# 1) Unload day brain (keep_alive=0); prefer Docker quit for ~50GB free.
# 2) mlx_lm fuse --dequantize → training_data/style_v1_fused_fp16 (safetensors).
# 3) llama.cpp convert_hf_to_gguf.py --outtype q8_0 → *.gguf (~27G).
# 4) ollama create $TAG -f Modelfile (FROM local GGUF).
#
# NOTE: plain convert GGUF lacks Unsloth MTP blk.64 (day has 65 blocks + nextn=1).
# After CONVERT run: python scripts/graft_style_canary_mtp.py → *-mtp.gguf, then CREATE
# with STYLE_FUSE_GGUF_PATH pointing at *-mtp.gguf. Do NOT promote to :latest.
# MoE canary stays victoria-qwen38:canary (restore from :canary-moe-backup if needed).
#
# Usage:
#   bash scripts/fuse_style_v1_canary.sh          # ALL
#   bash scripts/fuse_style_v1_canary.sh FUSE     # dequant fuse only
#   bash scripts/fuse_style_v1_canary.sh CONVERT  # gguf only (needs fp16 dir)
#   bash scripts/fuse_style_v1_canary.sh CREATE   # ollama create only (needs gguf)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY="${ROOT}/.venv/bin/python"
[[ -x "$PY" ]] || PY="$(command -v python3)"
BASE="${MLX_LORA_BASE_MODEL:-$HOME/mlx-models/qwen38-27b-4bit}"
ADAPTER="${STYLE_LORA_ADAPTER:-$ROOT/configs/training/style_v1/adapters}"
EXPORT="${STYLE_FUSE_OUT:-$ROOT/training_data/style_v1_fused_fp16}"
# Prefer MTP-grafted GGUF when present (ollama 0.33 needs blk.64).
if [[ -z "${STYLE_FUSE_GGUF_PATH:-}" ]]; then
  if [[ -f "$EXPORT/victoria-style-qwen38-q8_0-mtp-normfix.gguf" ]]; then
    GGUF="$EXPORT/victoria-style-qwen38-q8_0-mtp-normfix.gguf"
  elif [[ -f "$EXPORT/victoria-style-qwen38-q8_0-mtp.gguf" ]]; then
    GGUF="$EXPORT/victoria-style-qwen38-q8_0-mtp.gguf"
  else
    GGUF="$EXPORT/victoria-style-qwen38-q8_0.gguf"
  fi
else
  GGUF="$STYLE_FUSE_GGUF_PATH"
fi
TAG="${STYLE_CANARY_TAG:-victoria-qwen38:style-canary}"
MODEFILE="$EXPORT/Modelfile.style-canary"
CONVERT="${LLAMA_CONVERT:-$HOME/Downloads/llama.cpp/convert_hf_to_gguf.py}"
OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"
export OLLAMA_HOST
MODE="${1:-ALL}"

die() { echo "ERROR: $*" >&2; exit 1; }
[[ -d "$BASE" ]] || die "MLX base missing: $BASE"
[[ -f "$ADAPTER/adapters.safetensors" ]] || die "adapters missing: $ADAPTER"
[[ "$TAG" == *":latest" ]] && die "refusing tag ending in :latest ($TAG)"

unload_day() {
  curl -s "http://${OLLAMA_HOST}/api/generate" \
    -d '{"model":"victoria-qwen38:latest","keep_alive":0}' >/dev/null 2>&1 || true
  curl -s "http://${OLLAMA_HOST}/api/generate" \
    -d "{\"model\":\"$TAG\",\"keep_alive\":0}" >/dev/null 2>&1 || true
  sleep 2
}

fuse_dequant() {
  echo "== FUSE dequant =="
  unload_day
  mkdir -p "$EXPORT"
  PYTHONUNBUFFERED=1 "$PY" -m mlx_lm fuse \
    --model "$BASE" \
    --adapter-path "$ADAPTER" \
    --save-path "$EXPORT" \
    --dequantize
  echo "OK fused fp16 → $EXPORT"
}

convert_gguf() {
  [[ -f "$EXPORT/config.json" ]] || die "missing $EXPORT/config.json (run FUSE)"
  [[ -f "$CONVERT" ]] || die "missing convert_hf_to_gguf.py at $CONVERT"
  echo "== CONVERT q8_0 =="
  PYTHONUNBUFFERED=1 "$PY" "$CONVERT" "$EXPORT" \
    --outfile "$GGUF" \
    --outtype q8_0
  echo "OK gguf → $GGUF"
  # Optional: drop safetensors to free ~50G
  if [[ "${STYLE_DROP_FP16_SHARDS:-1}" == "1" ]]; then
    rm -f "$EXPORT"/model-*.safetensors "$EXPORT"/model.safetensors.index.json || true
    echo "dropped fp16 shards"
  fi
}

write_modelfile() {
  [[ -f "$GGUF" ]] || die "GGUF missing: $GGUF"
  cat >"$MODEFILE" <<EOF
# Style LoRA canary — fused qwen38 + style_v1 → Q8_0. NEVER :latest.
FROM $GGUF
PARAMETER num_ctx 16384
PARAMETER temperature 0.2
TEMPLATE """{{ if .System }}<|im_start|>system
{{ .System }}<|im_end|>
{{ end }}{{ if .Prompt }}<|im_start|>user
{{ .Prompt }}<|im_end|>
{{ end }}<|im_start|>assistant
{{ .Response }}<|im_end|>
"""
EOF
}

create_tag() {
  write_modelfile
  echo "== OLLAMA CREATE $TAG =="
  ollama create "$TAG" -f "$MODEFILE"
  echo "OK created $TAG"
  echo "NOTE: after MTP graft run scripts/fix_style_canary_rmsnorm.py (161 F32 norms −1.0) before CREATE."
  echo "Prefer *-mtp-normfix.gguf. Smoke chat/generate + refusals; NO_PROMOTE to :latest."
  echo "Day pin stays victoria-qwen38:latest. MoE battle canary: victoria-qwen38:canary."
}

case "$MODE" in
  FUSE) fuse_dequant ;;
  CONVERT) convert_gguf ;;
  CREATE) create_tag ;;
  ALL)
    fuse_dequant
    convert_gguf
    create_tag
    ;;
  *) die "usage: $0 [ALL|FUSE|CONVERT|CREATE]" ;;
esac
