#!/bin/bash
# Скрипт для сканирования всех моделей на Mac Studio M4 Max
# Запустите этот скрипт на Mac Studio и отправьте результат

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
    echo "⚠️  Ollama не установлен"
fi

echo ""
echo ""

# 2. Все модели через Ollama API
echo "🌐 ВСЕ МОДЕЛИ ЧЕРЕЗ OLLAMA API:"
echo "------------------------------------------------------------"
curl -s http://localhost:11434/api/tags 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "API недоступен"

echo ""
echo ""

# 3. MLX модели в HuggingFace кеше
echo "🍎 MLX МОДЕЛИ (HuggingFace кеш):"
echo "------------------------------------------------------------"
hf_cache="$HOME/.cache/huggingface/hub"
if [ -d "$hf_cache" ]; then
    find "$hf_cache" -maxdepth 1 -type d -name "*mlx*" 2>/dev/null | while read -r dir; do
        if [ -n "$dir" ]; then
            model_name=$(basename "$dir" | sed 's/models--//' | sed 's/--/\//g')
            size=$(du -sh "$dir" 2>/dev/null | cut -f1)
            echo "  ✅ $model_name ($size)"
        fi
    done
    echo ""
    echo "📦 Все модели в HuggingFace кеше (больше 1GB):"
    du -sh "$hf_cache"/models--* 2>/dev/null | awk '$1 ~ /[0-9]+G/ || ($1 ~ /[0-9]+M/ && $1+0 > 1024)' | sort -h | while read -r line; do
        echo "  $line"
    done
else
    echo "  ⚠️  HuggingFace кеш не найден"
fi

echo ""
echo ""

# 4. MLX модели в стандартной директории
echo "📁 MLX МОДЕЛИ (~/.mlx_models):"
echo "------------------------------------------------------------"
if [ -d ~/.mlx_models ]; then
    ls -lh ~/.mlx_models/ | head -20
    du -sh ~/.mlx_models/* 2>/dev/null | sort -h
else
    echo "  ⚠️  Директория ~/.mlx_models не существует"
fi

echo ""
echo ""

# 5. Поиск больших файлов моделей
echo "🔍 ПОИСК БОЛЬШИХ ФАЙЛОВ МОДЕЛЕЙ (>5GB):"
echo "------------------------------------------------------------"
find ~/.ollama ~/.cache ~/.local ~/Library/Application\ Support -type f \( -name "*.gguf" -o -name "*.safetensors" -o -name "*.bin" -o -name "*.pt" -o -name "*.pth" \) -size +5G 2>/dev/null | head -20 | while read -r file; do
    size=$(du -sh "$file" 2>/dev/null | cut -f1)
    echo "  📦 $file ($size)"
done

echo ""
echo ""

# 6. Общая статистика
echo "💾 ОБЩАЯ СТАТИСТИКА:"
echo "------------------------------------------------------------"
[ -d ~/.ollama/models/blobs ] && echo "Ollama: $(du -sh ~/.ollama/models/blobs 2>/dev/null | cut -f1)"
[ -d ~/.cache/huggingface/hub ] && echo "HuggingFace cache: $(du -sh ~/.cache/huggingface/hub 2>/dev/null | cut -f1)"
[ -d ~/.mlx_models ] && echo "MLX models: $(du -sh ~/.mlx_models 2>/dev/null | cut -f1)"

echo ""
echo "============================================================"
echo "✅ Сканирование завершено!"
echo "============================================================"
