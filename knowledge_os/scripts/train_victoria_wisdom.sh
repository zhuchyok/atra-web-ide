#!/bin/bash
# [SINGULARITY 20.0] Fine-tuning script for victoria-wisdom-v3.5
# Uses MLX-LM for efficient QLoRA on Apple Silicon
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Пути к данным и модели
DATASET_PATH="$KO_ROOT/training_data/train.jsonl"
ADAPTER_PATH="$KO_ROOT/training_data/adapters/victoria-wisdom-v1"
# Используем локальную базу, которая реально доступна на хосте.
# Можно переопределить через MLX_LORA_BASE_MODEL.
MODEL_NAME="${MLX_LORA_BASE_MODEL:-/Users/bikos/mlx-models/qwen2.5-3b}"

# Параметры обучения (ЭКСТРЕМАЛЬНО-Щадящий режим для 128GB RAM)
RANK=4
ALPHA=8
LAYERS=4
BATCH_SIZE=1
ITERS=1000
LEARNING_RATE=1e-5
MAX_SEQ_LENGTH="${MLX_LORA_MAX_SEQ_LENGTH:-1024}"

echo "🚀 [TRAINING] Запуск Fine-tuning на базе СЖАТОЙ МОДЕЛИ (Радикальная разгрузка)..."
echo "📊 Датасет: $DATASET_PATH"
echo "🧠 Базовая модель: $MODEL_NAME (Локальная)"
echo "⚙️ Параметры: Rank=$RANK, Alpha=$ALPHA, Layers=$LAYERS, Batch=1"

# Ограничение ресурсов
export MLX_MAX_BATCH_SIZE=1
export MLX_GPU_LAYERS=4

# Проверка наличия MLX-LM
if ! python3 -c "import mlx_lm" &> /dev/null; then
    echo "⚠️ [TRAINING] MLX-LM не найден. Установка..."
    python3 -m pip install mlx-lm
fi

# Build dataset from distilled nodes and validate LoRA readiness gate.
python3 "$SCRIPT_DIR/build_lora_dataset_from_distilled.py" --output-dir "$KO_ROOT/training_data" --required-distilled-pct 50
python3 "$SCRIPT_DIR/evaluate_lora_gate.py" --manifest "$KO_ROOT/training_data/lora_dataset_manifest.json" --report "$KO_ROOT/../docs/audits/lora-readiness-gate.md"

if [ ! -s "$DATASET_PATH" ]; then
    echo "❌ [TRAINING] Dataset missing or empty at $DATASET_PATH"
    exit 1
fi

mkdir -p "$ADAPTER_PATH"

# Авто-resume: если есть сохраненные веса, продолжаем обучение с них.
RESUME_FILE="${MLX_LORA_RESUME_FILE:-}"
if [ -z "$RESUME_FILE" ] && [ -s "$ADAPTER_PATH/adapters.safetensors" ]; then
    RESUME_FILE="$ADAPTER_PATH/adapters.safetensors"
fi

LORA_ARGS=(
    --model "$MODEL_NAME"
    --train
    --data "$KO_ROOT/training_data"
    --iters "$ITERS"
    --batch-size "$BATCH_SIZE"
    --num-layers "$LAYERS"
    --learning-rate "$LEARNING_RATE"
    --max-seq-length "$MAX_SEQ_LENGTH"
    --grad-checkpoint
    --adapter-path "$ADAPTER_PATH"
    --save-every 100
    --test
)

if [ -n "$RESUME_FILE" ] && [ -s "$RESUME_FILE" ]; then
    echo "♻️ [TRAINING] Resume from: $RESUME_FILE"
    LORA_ARGS+=(--resume-adapter-file "$RESUME_FILE")
fi

# Запуск обучения через mlx_lm lora
python3 -m mlx_lm lora "${LORA_ARGS[@]}"

echo "✅ [TRAINING] Цикл обучения завершен."
