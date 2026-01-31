# 🔍 Результаты поиска production моделей на Mac Studio

**Дата поиска:** 2025-01-21  
**Устройство:** Mac Studio M4 Max

---

## 📊 РЕЗУЛЬТАТЫ ПОИСКА

### ✅ НАЙДЕННЫЕ МОДЕЛИ:

#### Ollama модели (6 шт., ~21 GB):
1. ✅ `moondream:latest` (1.7 GB) - Vision
2. ✅ `phi4:latest` (9.1 GB) - Fast/Balanced  
3. ✅ `deepseek-r1:7b` (4.7 GB) - Reasoning
4. ✅ `qwen2.5-coder:7b` (4.7 GB) - Coding
5. ✅ `qwen2.5-coder:3b` (1.9 GB) - Tiny/Fast
6. ✅ `nomic-embed-text:latest` (274 MB) - Embeddings

#### MLX модели в HuggingFace кеше (2 шт., ~7.3 GB):
1. ✅ `mlx-community/Phi-3-mini-4k-instruct-4bit` (4.01 GB)
2. ✅ `mlx-community/Qwen2.5-3B-Instruct-4bit` (3.26 GB)

---

## ❌ PRODUCTION МОДЕЛИ НЕ НАЙДЕНЫ:

### Основной стек:
- ❌ `deepseek-r1-distill-llama-70b` (55GB) — reasoning
- ❌ `qwen2.5-coder-32b` (35GB) — кодирование
- ❌ `phi3.5-mini-4k` (2GB) — быстрые задачи

### Мелкие модели:
- ❌ `tinyllama-1.1b-chat` (0.7GB)
- ❌ `qwen2.5-3b` (2GB)
- ❌ `phi3-mini-4k-instruct` (2GB)

### Дополнительные:
- ❌ `llama3.3-70b` (35GB)
- ❌ `command-r-plus` (65GB)

---

## 🔍 ГДЕ ИСКАЛИСЬ:

✅ Проверено:
- `~/.ollama/models/` - только текущие модели
- `~/.cache/huggingface/hub/` - только 2 MLX модели
- `~/.mlx_models/` - не существует
- `~/Downloads/`, `~/Documents/` - не найдено
- Все большие файлы (>10GB) - не найдено

---

## 💡 ВЫВОДЫ:

1. **Production модели не установлены** в стандартных местах
2. **Система настроена** для автоматического использования, когда они будут установлены
3. **Fallback модели работают** - текущие установленные модели используются как fallback

---

## 🚀 РЕКОМЕНДАЦИИ:

### Если модели действительно установлены:
1. Укажите точные пути к моделям
2. Или точные имена в Ollama (`ollama list`)
3. Или формат хранения (MLX, GGUF, safetensors)

### Если нужно установить:
```bash
# Через Ollama
ollama pull deepseek-r1-distill-llama-70b:instruct-q6_k
ollama pull qwen2.5-coder-32b-instruct:q8_0
ollama pull phi3.5-mini-4k-instruct:q4_k_m
ollama pull tinyllama:1.1b-chat-v1.0-q4_0
ollama pull qwen2.5-3b-instruct:q4_k_m
ollama pull phi3-mini-4k-instruct:q4_k_m
ollama pull llama3.3-70b-instruct:q6_k
ollama pull command-r-plus:q4_k_m
```

---

*Поиск выполнен на Mac Studio M4 Max - 2025-01-21*

