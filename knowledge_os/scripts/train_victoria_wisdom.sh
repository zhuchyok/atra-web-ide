#!/bin/bash
# [SINGULARITY 20.0] Fine-tuning script for victoria-wisdom-v3.5
# Uses MLX-LM for efficient QLoRA on Apple Silicon

# Пути к данным и модели
DATASET_PATH="training_data/wisdom_dataset.jsonl"
ADAPTER_PATH="training_data/adapters/victoria-wisdom-v1"
# Используем локальную сжатую Qwen 2.5 Coder 32B как базу (она идентична Qwen 3 по архитектуре)
MODEL_NAME="/Users/bikos/mlx-models/qwen2.5-coder-32b"

# Параметры обучения (ЭКСТРЕМАЛЬНО-Щадящий режим для 128GB RAM)
RANK=4
ALPHA=8
LAYERS=4
BATCH_SIZE=1
ITERS=1000
LEARNING_RATE=1e-5

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

mkdir -p "$ADAPTER_PATH"

# Запуск обучения через mlx_lm lora
python3 -m mlx_lm lora \
    --model "$MODEL_NAME" \
    --train \
    --data "training_data" \
    --iters "$ITERS" \
    --batch-size "$BATCH_SIZE" \
    --num-layers "$LAYERS" \
    --learning-rate "$LEARNING_RATE" \
    --adapter-path "$ADAPTER_PATH" \
    --save-every 100 \
    --test

echo "✅ [TRAINING] Цикл обучения завершен."
