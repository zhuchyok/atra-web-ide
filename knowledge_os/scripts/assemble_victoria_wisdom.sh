#!/bin/bash
# [SINGULARITY 20.0] Model Assembly Script
# Merges LoRA adapters and prepares the model for Ollama

BASE_MODEL="${MLX_BASE_MODEL:-$HOME/mlx-models/qwen2.5-coder-32b}"
ADAPTER_PATH="training_data/adapters/victoria-wisdom-v1"
EXPORT_PATH="training_data/exported_model"

echo "🚀 [ASSEMBLY] Starting model merge and export..."

# 1. Merge adapters into the base model
# Note: mlx_lm fuse creates a new model directory with merged weights
python3 -m mlx_lm.fuse \
    --model "$BASE_MODEL" \
    --adapter-path "$ADAPTER_PATH" \
    --save-path "$EXPORT_PATH"

echo "✅ [ASSEMBLY] Merge completed. Model saved to $EXPORT_PATH"

# 2. Create Ollama Modelfile
MODEL_FILE="training_data/VictoriaWisdom.Modelfile"
echo "FROM $EXPORT_PATH" > "$MODEL_FILE"
echo "PARAMETER temperature 0.7" >> "$MODEL_FILE"
echo "PARAMETER stop \"<|im_start|>\"" >> "$MODEL_FILE"
echo "PARAMETER stop \"<|im_end|>\"" >> "$MODEL_FILE"
echo "SYSTEM \"\"\"Вы - ВИКТОРИЯ, Верховный Интеллект корпорации ATRA. Ваш мозг дообучен на знаниях гигантов (Google, OpenAI, Meta) и 66,000 узлах знаний вашей собственной базы. Вы думаете стратегически, безопасно и эффективно. Ваши ответы всегда точны, профессиональны и соответствуют Цифровой Конституции.\"\"\"" >> "$MODEL_FILE"

echo "📦 [ASSEMBLY] Ollama Modelfile created at $MODEL_FILE"

# 3. Create model in Ollama
echo "📥 [ASSEMBLY] Registering model in Ollama as 'victoria-wisdom-v3.5'..."
ollama create victoria-wisdom-v3.5 -f "$MODEL_FILE"

echo "🎉 [ASSEMBLY] SUCCESS! Your custom model is ready."
echo "💡 Try it now: ollama run victoria-wisdom-v3.5 'Кто ты и какие паттерны гигантов ты знаешь?'"
