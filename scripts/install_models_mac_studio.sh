#!/bin/bash
# Скрипт установки всех моделей на Mac Studio M4 Max

set -e

echo "🚀 Установка моделей для Mac Studio M4 Max"
echo ""

# Проверка зависимостей
echo "📦 Проверка зависимостей..."
python3 -c "import mlx_lm" 2>/dev/null || {
    echo "❌ MLX не установлен!"
    echo "   Установите: pip install mlx mlx-lm"
    exit 1
}

# Создание директории для моделей
mkdir -p ~/.mlx_models

echo "✅ Зависимости установлены"
echo ""

# Запуск Python скрипта установки
echo "🤖 Запуск установки моделей..."
python3 << 'PYTHON_SCRIPT'
import os
import subprocess
import sys
from pathlib import Path

# Модели для установки
MODELS = [
    {
        "name": "DeepSeek-R1-Distill-Llama-70B",
        "hf_id": "deepseek-ai/DeepSeek-R1-Distill-Llama-70B",
        "mlx_path": "~/.mlx_models/DeepSeek-R1-Distill-Llama-70B-Q6",
        "q_bits": 6,
        "size_gb": 55,
        "category": "reasoning"
    },
    {
        "name": "Qwen2.5-Coder-32B-Instruct",
        "hf_id": "Qwen/Qwen2.5-Coder-32B-Instruct",
        "mlx_path": "~/.mlx_models/Qwen2.5-Coder-32B-Instruct-Q8",
        "q_bits": 8,
        "size_gb": 35,
        "category": "coding"
    },
    {
        "name": "Phi-3.5-Mini-Instruct",
        "hf_id": "microsoft/Phi-3.5-mini-instruct",
        "mlx_path": "~/.mlx_models/Phi-3.5-mini-instruct-Q4",
        "q_bits": 4,
        "size_gb": 2,
        "category": "fast"
    },
    {
        "name": "TinyLlama-1.1B-Chat",
        "hf_id": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
        "mlx_path": "~/.mlx_models/TinyLlama-1.1B-Chat-Q4",
        "q_bits": 4,
        "size_gb": 0.7,
        "category": "tiny"
    },
    {
        "name": "Qwen2.5-3B-Instruct",
        "hf_id": "Qwen/Qwen2.5-3B-Instruct",
        "mlx_path": "~/.mlx_models/Qwen2.5-3B-Instruct-Q4",
        "q_bits": 4,
        "size_gb": 2,
        "category": "fast"
    },
    {
        "name": "Phi-3-Mini-4K-Instruct",
        "hf_id": "microsoft/Phi-3-mini-4k-instruct",
        "mlx_path": "~/.mlx_models/Phi-3-mini-4k-instruct-Q4",
        "q_bits": 4,
        "size_gb": 2,
        "category": "fast"
    }
]

def install_model(model_config):
    """Устанавливает одну модель"""
    mlx_path = os.path.expanduser(model_config['mlx_path'])

    if os.path.exists(mlx_path) and os.listdir(mlx_path):
        print(f"✅ {model_config['name']} уже установлена")
        return True

    print(f"\n🔄 Установка: {model_config['name']}")
    print(f"   HuggingFace: {model_config['hf_id']}")
    print(f"   Размер: ~{model_config['size_gb']}GB")

    cmd = [
        sys.executable, "-m", "mlx_lm.convert",
        "--hf-path", model_config['hf_id'],
        "--q-bits", str(model_config['q_bits']),
        "-q",
        "--mlx-path", mlx_path
    ]

    try:
        subprocess.run(cmd, check=True)
        print(f"✅ {model_config['name']} установлена успешно")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка установки {model_config['name']}: {e}")
        return False

# Установка моделей
total_size = 0
for model in MODELS:
    if install_model(model):
        total_size += model['size_gb']

print(f"\n✅ Установка завершена!")
print(f"📊 Общий размер: ~{total_size}GB")

PYTHON_SCRIPT

echo ""
echo "✅ Модели установлены!"
echo "📁 Расположение: ~/.mlx_models"
