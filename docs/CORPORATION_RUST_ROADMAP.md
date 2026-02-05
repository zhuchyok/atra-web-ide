# Дорожная карта: корпорация на Rust

**Назначение:** единый документ по стратегии «корпорация на Rust» — поэтапное наращивание доли Rust в узких местах при сохранении контрактов, fallback и рекомендаций специалистов. При любых решениях по Rust сверяться с этим документом и с [MASTER_REFERENCE.md](MASTER_REFERENCE.md), [OPTIMIZATION_AND_RUST_CANDIDATES.md](OPTIMIZATION_AND_RUST_CANDIDATES.md), [VERIFICATION_CHECKLIST_OPTIMIZATIONS.md](VERIFICATION_CHECKLIST_OPTIMIZATIONS.md).

**Обновлено:** 2026-02-04

---

## 1. Видение и границы

- **Цель:** корпорация (Knowledge OS, Victoria, воркер, чат, RAG, кэши) со временем всё больше опирается на Rust там, где это даёт выигрыш по скорости, памяти и предсказуемости, **без** полной переписывания на Rust.
- **Что не делаем:** не переписываем оркестрацию, Victoria, ai_core, вызовы LLM целиком на Rust — по библии и OPTIMIZATION_AND_RUST_CANDIDATES это I/O-bound, выигрыш мал, стоимость переноса высокая. Узкое место — сеть и модели, не Python.
- **Что делаем:** выносим в Rust только **CPU-bound участки** и участки, где профиль (py-spy, cProfile) показывает заметное время; сохраняем тонкие обёртки в Python и контракты; каждый шаг верифицируем (тесты, бенчмарк, чеклист).

---

## 2. Принципы (согласованы со специалистами и библией)

| Принцип | Источник | Как соблюдать |
|--------|----------|----------------|
| Один контракт — одна замена | OPTIMIZATION_AND_RUST_CANDIDATES §6 | Python вызывает `normalize_and_hash()`, `get_pool()` и т.д.; при переходе на Rust меняется только реализация за обёрткой. |
| Сначала инфраструктура, потом горячие пути | Там же | Нормализация/кэш уже есть; дальше — по профилю (пул БД, батч эмбеддингов, векторная близость). |
| Не трогать первыми оркестрацию/LLM | Там же, §3 | Victoria, worker, ai_core, вызовы Ollama/MLX остаются на Python, пока не появится явная CPU-узкость. |
| Fallback и откат | VERIFICATION_CHECKLIST §5 | При отсутствии Rust-модуля — работа на чистом Python (cache_normalizer: try/except ImportError). Документировать способ отката. |
| Постоянная проверка результата | MASTER_REFERENCE §6 | После каждого шага: тесты (cargo test, pytest), бенчмарк при необходимости, проход по чеклисту §1 VERIFICATION_CHECKLIST по затронутой области. |
| Исправлять причины сбоев | VERIFICATION_CHECKLIST §3 | При сбое — таблица «Проблема / Причина / Решение»; дополнять её и править корневую причину. |
| Библия актуальна | MASTER_REFERENCE §6 | После изменений обновлять MASTER_REFERENCE (и при необходимости CHANGES_FROM_OTHER_CHATS, OPTIMIZATION_AND_RUST_CANDIDATES). |

---

## 3. Фазы и статус

| Фаза | Что | Статус | Где |
|------|-----|--------|-----|
| **1** | Нормализация текста + MD5 для ключей кэша | ✅ Сделано | cache_normalizer_rs: normalize_text, normalize_and_hash |
| **1b** | Батч нормализации+хэша (меньше переходов Python↔Rust) | ✅ Сделано | cache_normalizer_rs: normalize_and_hash_batch |
| **2** | Пул БД (опционально) | В плане | Контракт: get_pool(), acquire(); замена asyncpg на Rust — по профилю. |
| **3** | Батч эмбеддингов / векторная близость | В плане | При появлении in-memory индекса или росте нагрузки — см. OPTIMIZATION_AND_RUST_CANDIDATES §6. |
| **4** | Скрипты массовой обработки (CLI на Rust) | В плане | Отдельные бинарники; вызов из Python через subprocess при необходимости. |

---

## 4. Текущий Rust-код в репозитории

| Компонент | Назначение | Контракт (Python) | Откат |
|-----------|------------|-------------------|-------|
| **cache_normalizer_rs** | Нормализация + MD5 для ключей кэша эмбеддингов | normalize_text(s), normalize_and_hash(s), normalize_and_hash_batch(texts) | pip uninstall cache_normalizer; Python hashlib + ' '.join(s.lower().split()) |

Подключение: embedding_optimizer.py, semantic_cache.py — try/except ImportError, при успехе используют Rust, иначе Python.

---

## 5. Следующие шаги (рекомендации специалистов)

1. **Профилирование:** при росте нагрузки замерить py-spy/cProfile и подтвердить очередность кандидатов (OPTIMIZATION_AND_RUST_CANDIDATES §6).
2. **Использование batch в Python:** в местах, где подряд вызывается normalize_and_hash для многих строк, вызывать normalize_and_hash_batch один раз. ✅ **Применено:** embedding_optimizer.get_embeddings_batch использует _get_text_hashes_batch(texts) (Rust batch при наличии). semantic_cache — по одному запросу на вызов, батч-пути нет.
3. **Новые Rust-модули:** документировать в OPTIMIZATION_AND_RUST_CANDIDATES с контрактом и способом отката; добавить пункт в §5 VERIFICATION_CHECKLIST «При следующих изменениях».
4. **При сбоях:** фиксировать причину в VERIFICATION_CHECKLIST §3 и устранять корень.

---

## 6. Ссылки

- [MASTER_REFERENCE.md](MASTER_REFERENCE.md) — библия проекта.
- [OPTIMIZATION_AND_RUST_CANDIDATES.md](OPTIMIZATION_AND_RUST_CANDIDATES.md) — кандидаты на Rust, порядок перевода, Docker, cache_normalizer.
- [VERIFICATION_CHECKLIST_OPTIMIZATIONS.md](VERIFICATION_CHECKLIST_OPTIMIZATIONS.md) — чеклист, причины сбоев, при следующих изменениях.
- [knowledge_os/cache_normalizer_rs/README.md](../knowledge_os/cache_normalizer_rs/README.md) — сборка и установка cache_normalizer.
