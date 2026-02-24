# ✅ Исправление 429 ошибок на /api/tags

**Дата:** 2026-01-27  
**Проблема:** Частые 429 ошибки из-за rate limiting на `/api/tags`  
**Статус:** ✅ **ИСПРАВЛЕНО**

---

## 🔍 Проблема

В логах MLX API Server частые 429 ошибки из-за слишком частых запросов к `/api/tags`:

- `check_health()` в `local_router.py` - каждые 30 секунд
- `_get_available_models()` в `extended_thinking.py` - без кэширования
- `check_model_available()` в `model_selector.py` - без кэширования
- Другие компоненты также делают запросы

---

## ✅ Решения

### 1. Увеличен TTL кэша в `check_health()`

**Файл:** `knowledge_os/app/local_router.py`

- ✅ TTL увеличен с **30 секунд до 120 секунд** (2 минуты)
- ✅ Используется легкий `/health` endpoint вместо `/api/tags` где возможно
- ✅ Fallback на `/api/tags` только если `/health` недоступен

### 2. Добавлено кэширование в MLX API Server

**Файл:** `knowledge_os/app/mlx_api_server.py`

- ✅ Кэш для `/api/tags` на **60 секунд**
- ✅ Rate limiting для `/api/tags`: **60 запросов в минуту** (1 запрос/сек)
- ✅ При превышении лимита возвращается кэшированный результат

### 3. Добавлено кэширование в `extended_thinking.py`

**Файл:** `knowledge_os/app/extended_thinking.py`

- ✅ Глобальный кэш `_models_cache` с TTL **120 секунд**
- ✅ Оба метода `_get_available_models()` используют кэш
- ✅ Fallback на устаревший кэш при ошибках

### 4. Добавлено кэширование в `model_selector.py`

**Файл:** `knowledge_os/app/model_selector.py`

- ✅ Глобальный кэш `_models_cache` с TTL **120 секунд**
- ✅ `check_model_available()` использует кэш перед запросом
- ✅ Fallback на кэш при ошибках

---

## 📊 Оптимизации

### До исправления:

- ❌ Запросы к `/api/tags` каждые 30 секунд из `check_health()`
- ❌ Множественные запросы без кэширования
- ❌ Нет rate limiting для `/api/tags`
- ❌ 429 ошибки при высокой нагрузке

### После исправления:

- ✅ Запросы к `/api/tags` максимум раз в 60-120 секунд
- ✅ Кэширование на всех уровнях
- ✅ Rate limiting: 60 запросов/минуту для `/api/tags`
- ✅ Использование легкого `/health` endpoint где возможно
- ✅ Fallback на кэш при ошибках

---

## 🎯 Итог

**Все компоненты оптимизированы:**

- ✅ `local_router.py` - увеличен TTL, используется `/health`
- ✅ `mlx_api_server.py` - кэш + rate limiting для `/api/tags`
- ✅ `extended_thinking.py` - кэширование списка моделей
- ✅ `model_selector.py` - кэширование проверки моделей

**429 ошибки должны исчезнуть!** 🎉
