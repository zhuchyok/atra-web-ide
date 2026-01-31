#!/bin/bash
# Скрипт для дообучения локальных моделей

cd "$(dirname "$0")/.." || exit 1

echo "🚀 Запуск дообучения модели..."

# Параметры
MODEL_NAME="${1:-qwen2.5-coder:32b}"
INCLUDE_STYLE_PATTERNS="${2:-true}"        # ✅ По умолчанию собираем стиль
INCLUDE_ANTI_HALLUCINATION="${3:-false}"   # Опционально
INCLUDE_KNOWLEDGE_BASE="${4:-false}"       # ❌ По умолчанию НЕ собираем факты (они в RAG!)

# Проверка зависимостей
echo "📦 Проверка зависимостей..."
if ! python3 -c "import mlx_lm" 2>/dev/null; then
    echo "⚠️  MLX-LM не установлен. Устанавливаю..."
    pip3 install mlx-lm
fi

if ! python3 -c "import asyncpg" 2>/dev/null; then
    echo "⚠️  asyncpg не установлен. Устанавливаю..."
    pip3 install asyncpg
fi

# Запуск дообучения
cd knowledge_os || exit 1
python3 << EOF
import asyncio
import sys
sys.path.insert(0, '.')
from app.model_finetuner import ModelFineTuner

async def main():
    tuner = ModelFineTuner()
    results = await tuner.create_finetuning_pipeline(
        model_name="$MODEL_NAME",
        include_style_patterns=$INCLUDE_STYLE_PATTERNS,
        include_anti_hallucination=$INCLUDE_ANTI_HALLUCINATION,
        include_knowledge_base=$INCLUDE_KNOWLEDGE_BASE
    )
    
    import json
    print(json.dumps(results, indent=2, ensure_ascii=False))

asyncio.run(main())
EOF
