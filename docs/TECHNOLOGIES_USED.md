# ✅ ТЕХНОЛОГИИ, ИСПОЛЬЗУЕМЫЕ В СИСТЕМЕ

**Дата:** 2026-01-28  
**Статус:** ✅ **АКТУАЛЬНО**

---

## 🎯 ВЕКТОРНАЯ БАЗА ДАННЫХ

### ✅ PostgreSQL + pgvector

- **Что это:** PostgreSQL с расширением pgvector для векторного поиска
- **Где используется:**
  - Таблица `knowledge_nodes` с полем `embedding vector(768)`
  - Семантический поиск: `(1 - (embedding <=> $1::vector)) as similarity`
  - Семантический кэш: `semantic_ai_cache` таблица
- **Конфигурация:**
  - Расширение: `CREATE EXTENSION IF NOT EXISTS vector;`
  - Размерность: 768 (для nomic-embed-text)
- **Статус:** ✅ **ИСПОЛЬЗУЕТСЯ**

### ❌ Qdrant (НЕ используется)

- **Что это:** Специализированная векторная БД
- **Почему НЕ используется:** У нас уже есть pgvector, который лучше интегрирован с PostgreSQL
- **Статус:** ❌ **НЕ ИСПОЛЬЗУЕТСЯ**

---

## 🤖 MODEL SERVING

### ✅ MLX API Server

- **Что это:** API сервер для локальных MLX моделей
- **Где используется:**
  - Порт: 11435
  - URL: `http://localhost:11435` (локально) или `http://host.docker.internal:11435` (Docker)
  - Используется всеми агентами (Victoria, Veronica, Smart Worker)
- **Модели:**
  - `command-r-plus:104b` (~65GB) - Максимальная мощность
  - `deepseek-r1-distill-llama:70b` (~40GB) - Reasoning
  - `llama3.3:70b` (~40GB) - Максимальное качество
  - `qwen2.5-coder:32b` (~20GB) - Качественный код
  - `phi3.5:3.8b` (~2.5GB) - Быстрые задачи
  - И другие...
- **Статус:** ✅ **ИСПОЛЬЗУЕТСЯ**

### ❌ KServe (НЕ используется)

- **Что это:** Kubernetes-based платформа для serving ML моделей
- **Почему НЕ используется:** У нас локальная инфраструктура на Mac Studio, не Kubernetes
- **Статус:** ❌ **НЕ ИСПОЛЬЗУЕТСЯ**

### ❌ Triton (НЕ используется)

- **Что это:** NVIDIA inference server для ML моделей
- **Почему НЕ используется:** У нас Mac Studio (не NVIDIA GPU), используем MLX API Server
- **Статус:** ❌ **НЕ ИСПОЛЬЗУЕТСЯ**

---

## 🔤 EMBEDDING SERVICE

### ✅ VectorCore

- **Что это:** FastAPI сервис для генерации эмбеддингов
- **Где используется:**
  - Порт: 8001
  - URL: `http://localhost:8001` или `http://knowledge_vector_core:8001` (Docker)
  - API: `POST /encode` → возвращает embedding
- **Модель:** `all-MiniLM-L6-v2` (SentenceTransformer)
- **Размерность:** 384
- **Использование:**
  - Дашборд: `knowledge_os/dashboard/app.py`
  - Поиск знаний: `knowledge_os/app/main.py`
  - Семантический кэш: `knowledge_os/app/semantic_cache.py`
- **Статус:** ✅ **ИСПОЛЬЗУЕТСЯ**

---

## 📊 ИТОГОВАЯ ТАБЛИЦА

| Компонент         | Технология            | Статус             | Альтернатива (если есть) |
| ----------------- | --------------------- | ------------------ | ------------------------ |
| Векторная БД      | PostgreSQL + pgvector | ✅ Используется    | -                        |
| Векторная БД      | Qdrant                | ❌ Не используется | pgvector                 |
| Model Serving     | MLX API Server        | ✅ Используется    | -                        |
| Model Serving     | KServe                | ❌ Не используется | MLX API Server           |
| Model Serving     | Triton                | ❌ Не используется | MLX API Server           |
| Embedding Service | VectorCore            | ✅ Используется    | -                        |

---

## 🧹 ОЧИСТКА

Все упоминания неиспользуемых технологий (Qdrant, KServe, Triton) удалены из кода.

**Оставлены только в документации:**

- Как примеры ошибок экспертов
- Как объяснение, почему они НЕ используются

**См. также:**

- `docs/UNUSED_TECHNOLOGIES_CLEANUP.md` - детали очистки
- `docs/DASHBOARD_AUDIT_ANALYSIS.md` - анализ проблемы

---

**Дата обновления:** 2026-01-28  
**Автор:** ATRA Corporation (Victoria Agent)
