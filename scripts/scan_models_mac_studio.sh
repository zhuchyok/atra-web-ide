#!/bin/bash
# Скрипт сканирования всех моделей на Mac Studio M4 Max

echo "🔍 ПОЛНОЕ СКАНИРОВАНИЕ МОДЕЛЕЙ НА MAC STUDIO M4 MAX"
echo "============================================================"
echo ""

# 1. Ollama модели
echo "📦 OLLAMA МОДЕЛИ:"
echo "------------------------------------------------------------"
if command -v ollama &> /dev/null; then
    ollama list
    echo ""
    if [ -d ~/.ollama/models/blobs ]; then
        ollama_size=$(du -sh ~/.ollama/models/blobs 2>/dev/null | cut -f1)
        echo "Общий размер Ollama: $ollama_size"
    fi
else
    echo "⚠️  Ollama не установлен или не в PATH"
fi

echo ""
echo ""

# 2. MLX модели в HuggingFace кеше
echo "🍎 MLX МОДЕЛИ (HuggingFace кеш):"
echo "------------------------------------------------------------"
hf_cache="$HOME/.cache/huggingface/hub"
if [ -d "$hf_cache" ]; then
    mlx_models=$(find "$hf_cache" -maxdepth 1 -type d -name "*mlx-community*" 2>/dev/null)
    if [ -n "$mlx_models" ]; then
        echo "$mlx_models" | while read -r dir; do
            if [ -n "$dir" ]; then
                model_name=$(basename "$dir" | sed 's/models--//' | sed 's/--/\//g')
                size=$(du -sh "$dir" 2>/dev/null | cut -f1)
                echo "  ✅ $model_name ($size)"
            fi
        done
        echo ""
        echo "Общий размер MLX (HF cache): $(du -sh "$hf_cache"/models--mlx-community-* 2>/dev/null | awk '{s+=$1} END {print s}')" 2>/dev/null || echo "  (не удалось подсчитать)"
    else
        echo "  ⚠️  MLX модели не найдены в HuggingFace кеше"
    fi
else
    echo "  ⚠️  HuggingFace кеш не найден"
fi

echo ""
echo ""

# 3. MLX модели в стандартной директории
echo "📁 MLX МОДЕЛИ (стандартная директория ~/.mlx_models):"
echo "------------------------------------------------------------"
mlx_dir="$HOME/.mlx_models"
if [ -d "$mlx_dir" ]; then
    models=$(find "$mlx_dir" -maxdepth 1 -type d ! -path "$mlx_dir" 2>/dev/null)
    if [ -n "$models" ]; then
        echo "$models" | while read -r model; do
            if [ -n "$model" ]; then
                model_name=$(basename "$model")
                size=$(du -sh "$model" 2>/dev/null | cut -f1)
                echo "  ✅ $model_name ($size)"
            fi
        done
    else
        echo "  ⚠️  Директория существует, но пуста"
    fi
else
    echo "  ⚠️  Директория ~/.mlx_models не существует"
fi

echo ""
echo ""

# 4. Проверка через Ollama API
echo "🌐 ПРОВЕРКА ЧЕРЕЗ OLLAMA API:"
echo "------------------------------------------------------------"
if curl -s http://localhost:11434/api/tags &> /dev/null; then
    echo "✅ Ollama API доступен на localhost:11434"
    curl -s http://localhost:11434/api/tags | python3 -m json.tool 2>/dev/null | grep -A 3 '"name"' | head -30 || echo "  (не удалось получить список)"
else
    echo "  ⚠️  Ollama API недоступен на localhost:11434"
fi

echo ""
echo ""

# 5. Python проверка MLX
echo "🐍 ПРОВЕРКА MLX (через Python):"
echo "------------------------------------------------------------"
python3 << 'PYTHON_EOF'
try:
    import mlx.core as mx
    from mlx_lm import load
    print("✅ MLX доступен")
    print(f"  MLX версия: {getattr(mx, '__version__', 'unknown')}")
except ImportError as e:
    print(f"⚠️  MLX не установлен: {e}")
PYTHON_EOF

echo ""
echo ""

# 6. Общая статистика
echo "💾 ОБЩАЯ СТАТИСТИКА:"
echo "------------------------------------------------------------"
[ -d ~/.ollama/models/blobs ] && echo "Ollama модели: $(du -sh ~/.ollama/models/blobs 2>/dev/null | cut -f1)"
[ -d "$hf_cache" ] && [ -n "$(find "$hf_cache" -maxdepth 1 -type d -name "*mlx-community*" 2>/dev/null)" ] && echo "MLX (HF cache): $(du -sh "$hf_cache"/models--mlx-community-* 2>/dev/null | awk '{sum+=$1} END {if (sum) printf "%.1fG", sum/1024; else print "0"}' 2>/dev/null || echo "?")"
[ -d "$mlx_dir" ] && echo "MLX (~/.mlx_models): $(du -sh "$mlx_dir" 2>/dev/null | cut -f1)"

echo ""
echo "============================================================"
echo "✅ Сканирование завершено!"
echo "============================================================"
