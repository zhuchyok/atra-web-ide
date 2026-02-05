# cache_normalizer (Rust/PyO3)

Нормализация текста и MD5-хэш для ключей кэша эмбеддингов. Используется в `embedding_optimizer` и `semantic_cache` при наличии модуля; иначе — Python fallback.

**API:** `normalize_text(s)`, `normalize_and_hash(s)`, `normalize_and_hash_batch(texts)` — батч для списка текстов (меньше переходов Python↔Rust). Hex MD5 — через **faster-hex** (SIMD), результат совпадает с Python hashlib.

## Сборка и установка (локально)

Требуется: Rust (`rustup`), Python 3.9+, maturin.

```bash
# Установка Rust (если ещё нет)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
. "$HOME/.cargo/env"

# Установка maturin в venv проекта
knowledge_os/.venv/bin/pip install maturin

# Сборка и установка в knowledge_os venv
cd knowledge_os/cache_normalizer_rs
PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 knowledge_os/.venv/bin/maturin develop --release
```

При Python 3.14 PyO3 0.23 требует `PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1` (сборка с stable ABI). В Docker используется Python 3.11 — переменная не нужна.

## Проверка

```bash
knowledge_os/.venv/bin/python -c "from cache_normalizer import normalize_and_hash; print(normalize_and_hash('test'))"
```

## Docker (Victoria, воркер)

Используется **multi-stage build** в [infrastructure/docker/agents/Dockerfile](../../infrastructure/docker/agents/Dockerfile):

1. **Stage 0 (builder):** в образе на базе `python:3.11-slim` ставится Rust (rustup) и maturin, копируется только `knowledge_os/cache_normalizer_rs`, выполняется `maturin build --release -o /out`. В финальный образ не попадают ни Rust, ни исходники — только wheel.
2. **Stage 1 (runtime):** в рантайм-образ копируется готовый wheel из builder и ставится через `pip install`. Остальная часть Dockerfile без изменений.

При сборке `docker-compose -f knowledge_os/docker-compose.yml build victoria-agent` (или `knowledge_os_worker`) образ уже содержит `cache_normalizer`; Python fallback в контейнерах не используется.
