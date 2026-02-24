# 📦 СПИСОК ДОСТУПНЫХ МОДЕЛЕЙ

**Дата:** 2026-01-28  
**Статус:** ✅ **АКТУАЛЬНЫЙ СПИСОК**

---

## 🌐 OLLAMA МОДЕЛИ (порт 11434)

| Модель               | Параметры | Квантование | Размер   | Назначение                                               |
| -------------------- | --------- | ----------- | -------- | -------------------------------------------------------- |
| `qwq:32b`            | 32.8B     | Q4_K_M      | ~18.5 GB | Coding/General                                           |
| `qwen2.5-coder:32b`  | 32.8B     | Q4_K_M      | ~18.5 GB | Coding (high quality)                                    |
| `glm-4.7-flash:q8_0` | 29.9B     | Q8_0        | ~29.7 GB | Reasoning/Coding                                         |
| `llava:7b`           | 7B        | Q4_0        | ~4.4 GB  | Vision (PDF, images)                                     |
| `phi3.5:3.8b`        | 3.8B      | Q4_0        | ~2.0 GB  | Fast/General                                             |
| `moondream:latest`   | -         | -           | ~1.6 GB  | Vision (lightweight)                                     |
| `nomic-embed-text`   | -         | -           | ~0.27 GB | **Эмбеддинги** (RAG, semantic_cache, OLLAMA_EMBED_MODEL) |

---

## 🚀 MLX МОДЕЛИ (порт 11435)

| Модель                          | Формат | Назначение               |
| ------------------------------- | ------ | ------------------------ |
| `command-r-plus:104b`           | MLX    | Enterprise/Complex       |
| `deepseek-r1-distill-llama:70b` | MLX    | Reasoning (самый мощный) |
| `llama3.3:70b`                  | MLX    | Complex/General          |
| `qwen2.5-coder:32b`             | MLX    | Coding (high quality)    |
| `phi3.5:3.8b`                   | MLX    | Fast/General             |
| `phi3:mini-4k`                  | MLX    | Fast (lightweight)       |
| `qwen2.5:3b`                    | MLX    | Fast/Tiny                |
| `reasoning`                     | MLX    | Reasoning (алиас)        |
| `coding`                        | MLX    | Coding (алиас)           |
| `fast`                          | MLX    | Fast (алиас)             |
| `tiny`                          | MLX    | Tiny (алиас)             |
| `default`                       | MLX    | Default (алиас)          |
| `qwen_3b`                       | MLX    | Fast (алиас)             |
| `phi3_mini`                     | MLX    | Fast (алиас)             |

---

## 📊 ИТОГО

- **Ollama модели:** 7 (включая nomic-embed-text для эмбеддингов)
- **MLX модели:** 14 (включая алиасы)
- **Всего уникальных моделей:** ~10-12

---

## 🎯 ИСПОЛЬЗОВАНИЕ

### Ollama (порт 11434):

- Используется для быстрых задач
- Поддерживает vision модели (llava, moondream)
- **Эмбеддинги:** модель `nomic-embed-text` (OLLAMA_EMBED_MODEL) — без неё POST /api/embeddings даёт 404
- Fallback для MLX моделей

### MLX (порт 11435):

- Используется для мощных задач
- Приоритет для reasoning и coding
- Оптимизировано для Mac Studio M4 Max

---

## 🔄 СИНХРОНИЗАЦИЯ С КОДОМ

Конфиги приведены в соответствие с этим списком (2026-01-28):

- **Ollama:** везде используется тег `glm-4.7-flash:q8_0` (не `latest`).
- **Файлы:** `local_router.py`, `intelligent_model_router.py`, `model_performance_tracker.py`, `ai_core.py`.
- При добавлении/удалении моделей в Ollama/MLX обновите этот документ и перечисленные файлы.

**Дата обновления:** 2026-01-28
