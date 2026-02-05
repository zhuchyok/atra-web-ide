# Оптимизация и кандидаты на Rust

## 1. Всё ли применено

### В репозитории уже есть

- **collective_memory.py**: лимиты traces (200 на location, 500 locations), обрезка result в памяти до 2000 символов, **полный result в БД** (`full_result` в `_save_trace_to_db`).
- **isolated_context.py**: лимит памяти контекста (100 сообщений).
- **smart_worker_autonomous.py**: автосброс зависших in_progress в начале цикла воркера.
- **docs/MEMORY_LEAK_FIX_56GB.md**: описание лимитов и подхода с БД.

### Что нужно сделать один раз

Чтобы изменения в **Victoria** (Collective Memory, IsolatedContext) заработали, перезапусти контейнер:

```bash
docker-compose -f knowledge_os/docker-compose.yml restart victoria-agent
```

Воркер (`knowledge_os_worker`) мы уже перезапускали ранее; при необходимости:

```bash
docker-compose -f knowledge_os/docker-compose.yml restart knowledge_os_worker
```

---

## 2. Дополнительная оптимизация (без Rust)

- **Retention для environmental_traces**: периодически удалять строки старше N дней (например 90), чтобы БД не росла бесконечно.
- **Connection pooling**: везде использовать общий пул к БД (asyncpg pool), не создавать новое подключение на каждый запрос.
- **Кэши**: уже есть лимиты (semantic_cache 500, embedding_optimizer 1000); при росте нагрузки можно вынести горячий кэш в Redis.
- **Метрики**: профилирование (cProfile, py-spy) для поиска узких мест перед переносом чего-то в Rust.

### План «Speed without losing quality» (завершён)

Пул БД, параллельные fetch в ai_core, батч эмбеддингов в context_analyzer, общий HTTP-клиент, orjson в горячих путях, кэш перед RAG, стриминг (уже был), документ по миграции на Rust, граничные случаи и resilience — всё выполнено. Итоговый чеклист и статус: [VERIFICATION_CHECKLIST_OPTIMIZATIONS.md](VERIFICATION_CHECKLIST_OPTIMIZATIONS.md).

### Мировые практики (применённые)

| Практика | Реализация |
|----------|------------|
| **Connection pooling (БД)** | Единый пул в `db_pool.py`; `rest_api`, `collective_memory`, `context_analyzer` используют `get_pool()`. При миграции на Rust — замена только в `db_pool.py`. |
| **Переиспользование HTTP-клиента** | Общий `httpx.AsyncClient` в `http_client.py`: лимиты (max_connections=50, keepalive), ленивая инициализация, `close_http_client()` при shutdown (rest_api). В `semantic_cache.get_embedding` используется общий клиент вместо создания на каждый запрос. |
| **Быстрый JSON в горячих путях** | `orjson` в requirements.txt; модуль `json_fast.py` (loads/dumps с fallback на stdlib). Используется в `semantic_cache` (парсинг ответа Ollama) и в `main.py` (кэш поиска). Зависимости только в requirements.txt, не в рантайме (12-Factor). |
| **Порядок кэш → RAG** | В `ai_core.run_smart_agent_async`: сначала проверка semantic cache (`get_cached_response`), при попадании — возврат без вызова LLM и без RAG; при промахе — далее hybrid strategy и RAG (`_get_knowledge_context`). Лишние эмбеддинги и запросы к БД не выполняются при cache hit. |

---

## 3. Что имеет смысл переводить на Rust

Идея: переводить на Rust только **узкие CPU-bound участки**, где Python тратит заметное время. Большая часть стека (запросы к LLM, БД, HTTP) — I/O bound; там Rust даёт мало выигрыша.

### Кандидаты по приоритету

| Участок | Где | Зачем Rust | Выигрыш |
|--------|-----|------------|---------|
| **Нормализация текста + хэш для кэша** | `embedding_optimizer.py`, `semantic_cache.py` | Много вызовов `_normalize_text` + `hashlib.md5` на каждый запрос; в Rust — быстрее и без GIL. | Средний при большом RPS кэша. |
| **Векторная близость (cosine/similarity)** | Локальный поиск по эмбеддингам до запроса в pgvector | Если появится in-memory префильтр по векторам (тысячи векторов), Rust + SIMD даст ускорение. | Пока не актуально — поиск в pgvector. |
| **Скрипты массовой обработки** | `scripts/`, импорт/экспорт, парсинг логов | CLI на Rust: меньше памяти, быстрее на больших файлах. | Высокий для конкретных скриптов. |
| **Прокси/агрегатор для эмбеддингов** | Отдельный сервис между приложением и Ollama | Пулы соединений, батчинг, retry в одном процессе без GIL. | Средний при очень высокой нагрузке на embeddings. |

### Что не стоит переводить первым

- **Оркестрация (Victoria, worker, ai_core)** — много I/O, логика, интеграции; выигрыш от Rust мал, стоимость переноса высокая.
- **Сам вызов LLM (Ollama/MLX)** — узкое место сеть/модель, не Python.
- **Обычные CRUD и кэши в памяти** — dict/LRU в Python достаточно быстрые.

### Как интегрировать Rust

1. **Библиотека (PyO3)** — Rust-код как Python-модуль: нормализация + хэш, опционально батч-препроцессинг текстов для кэша. Python вызывает одну функцию `normalize_and_hash(text)` или `normalize_batch(texts)`.
2. **Отдельный бинарник** — CLI для скриптов (импорт, парсинг); вызывать через `subprocess` или как сервис.
3. **Микросервис** — например, HTTP-сервис «нормализация + хэш» или батч-эмбеддинг-прокси; вызывать по HTTP из Python.

Практичный первый шаг: вынести в Rust **нормализацию текста и хэш для ключей кэша** (embedding_optimizer, semantic_cache) в виде PyO3-модуля или маленького HTTP-сервиса, замерить выигрыш под нагрузкой.

---

## 4. Реализовано: cache_normalizer (Rust/PyO3)

### Где лежит

- **Rust-проект:** [knowledge_os/cache_normalizer_rs/](knowledge_os/cache_normalizer_rs/) — Cargo.toml, src/lib.rs, pyproject.toml для maturin.
- **Подключение в Python:** [knowledge_os/app/embedding_optimizer.py](knowledge_os/app/embedding_optimizer.py) и [knowledge_os/app/semantic_cache.py](knowledge_os/app/semantic_cache.py) при старте пробуют импорт `cache_normalizer`; при успехе используют `normalize_and_hash` / `normalize_text`, иначе — текущую реализацию (Python hashlib + normalize).
- **Батч (2026-02-04):** `normalize_and_hash_batch(texts: list[str]) -> list[str]` — один вызов для списка текстов, меньше переходов Python↔Rust при массовой обработке. В местах, где подряд вызывается normalize_and_hash для многих строк, можно собирать список и вызывать batch один раз.

### Оптимизации (2026-02-04)

- **Меньше аллокаций:** нормализация в один проход в `String::with_capacity` (без промежуточного `Vec<&str>` и `join`).
- **Release-профиль:** в Cargo.toml заданы `[profile.release]` с `opt-level=3`, `lto="thin"`, `codegen-units=1` (мировые практики: Rust Performance Book).
- **Юнит-тесты в Rust:** пустая строка, пробелы, нижний регистр, консистентность хэша, MD5 пустой строки (d41d8cd98f00b204e9800998ecf8427e). Запуск: `PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 cargo test` (при Python 3.14 в venv).
- **Python 3.14:** PyO3 0.23 поддерживает до 3.13; при сборке под Python 3.14 задать `PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1`. В Docker (Python 3.11) переменная не нужна.
- **Hex-кодирование MD5 (мировая практика):** вместо `format!("{:x}", digest)` используется крейт **faster-hex** (SIMD, ~10× быстрее стандартного hex) — результат совпадает с Python hashlib.hexdigest(). В батче — `Vec::with_capacity(texts.len())` для предвыделения.

### Как собрать и установить (опционально)

Требуется: Rust (rustup), Python 3.9+, maturin.

```bash
# Установка Rust (если ещё нет)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Установка maturin (в venv knowledge_os)
knowledge_os/.venv/bin/pip install maturin

# Сборка и установка модуля в текущее окружение
cd knowledge_os/cache_normalizer_rs
PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 knowledge_os/.venv/bin/maturin develop --release
# При Python 3.11 (Docker) переменная PYO3_USE_ABI3_FORWARD_COMPATIBILITY не нужна
```

После установки при следующем запуске приложения (Victoria, воркер, API) embedding_optimizer и semantic_cache будут использовать Rust для нормализации и хэша. Без установки всё работает на чистом Python (fallback).

### Как откатиться на чистый Python

Удалить установленный пакет: `pip uninstall cache_normalizer`. Или не устанавливать его — тогда везде используется Python-реализация.

### Замеры (Фаза 3.4)

До/после: замерить время обработки батча запросов к кэшу (например 1000 текстов) с включённым и выключенным Rust-модулем.

**Скрипт:** [knowledge_os/scripts/benchmark_cache_normalizer.py](knowledge_os/scripts/benchmark_cache_normalizer.py) — вызывает `embedding_optimizer._get_text_hash` в цикле (по умолчанию 1000 текстов), выводит суммарное время и статус (Rust / Python fallback).

```bash
cd knowledge_os
# С установленным cache_normalizer (Rust):
.venv/bin/python scripts/benchmark_cache_normalizer.py
# Затем: .venv/bin/pip uninstall cache_normalizer
# Без Rust (fallback):
.venv/bin/python scripts/benchmark_cache_normalizer.py
```

Сравнить «Total» и «per call» между двумя запусками.

---

## 5. Docker: Rust-модуль в контейнерах (мировая практика)

**Вопрос:** как в контейнерах Victoria/воркер использовать Rust-модуль — собирать wheel на хосте и ставить в образ или собирать внутри Docker?

**Подход:** сборка **внутри Docker** (multi-stage), без зависимости от хоста.

- **Почему не wheel с хоста:** wheel, собранный на Mac, подходит только для macOS. Образ агентов — Linux (`python:3.11-slim`), поэтому wheel должен быть собран под Linux. Вариант «собрать на хосте» имел бы смысл только при CI на Linux (артефакт wheel → COPY в образ).
- **Почему multi-stage:** в первом этапе (builder) ставится Rust и maturin, собирается wheel. Во втором этапе (runtime) в образ копируется только wheel и ставится через pip. В финальном образе нет ни компилятора, ни исходников Rust — меньше размер и поверхность атаки. Так делают для нативных расширений (cryptography, orjson, и т.п.).
- **Реализация:** [infrastructure/docker/agents/Dockerfile](infrastructure/docker/agents/Dockerfile) — stage `cache_normalizer_builder` собирает wheel, stage по умолчанию копирует его и выполняет `pip install`. При `docker-compose build victoria-agent` (или `knowledge_os_worker`) образ уже содержит `cache_normalizer`.

---

## 6. Порядок перевода модулей на Rust (дорожная карта)

При постепенной миграции на Rust важно сохранять тонкие обёртки в Python и переводить только узкие места. Ниже — рекомендуемый порядок и контракты для замены.

### Принципы

- **Один контракт — одна замена:** модуль Python вызывает `get_pool()`, `get_embedding()`, `normalize_and_hash()` и т.д.; при переходе на Rust меняется только реализация за обёрткой (например `db_pool.py` → Rust-пул с тем же API).
- **Сначала инфраструктура, потом горячие пути:** пул БД, сериализация, нормализация уже имеют точки замены; дальше — CPU-bound участки по профилю.
- **Не трогать первыми:** оркестрация (Victoria, ai_core), вызовы LLM, сложная бизнес-логика — I/O bound, выигрыш от Rust мал.

### Очередность (приоритет)

| № | Модуль / слой | Что заменить на Rust | Контракт (оставить в Python) | Заметки |
|---|----------------|----------------------|------------------------------|---------|
| 1 | **cache_normalizer** | Нормализация текста + MD5 для кэша | `normalize_and_hash(text)`, `normalize_text(text)` | ✅ Уже есть PyO3; при полном переходе — вынести в отдельный crate. |
| 2 | **db_pool** | Пул подключений к PostgreSQL | `get_pool()` → объект с `acquire()` (async context manager) | Замена asyncpg на rust-postgres / deadpool в отдельном сервисе или PyO3-обёртке. |
| 3 | **Эмбеддинги (батч)** | Батч-запросы к Ollama / векторная арифметика | `get_embedding(text)`, опционально `get_embeddings_batch(texts)` | Сначала параллельные вызовы (asyncio.gather, уже в context_analyzer); при росте нагрузки — Rust-прокси с пулом и батчингом. |
| 4 | **Векторная близость** | cosine_similarity, поиск по векторам в памяти | Функция `similarity(vec1, vec2)` или модуль с batch-поиском | Имеет смысл, если появится in-memory индекс (тысячи векторов) до pgvector. |
| 5 | **Скрипты массовой обработки** | Импорт/экспорт, парсинг логов, ETL | CLI или HTTP API | Отдельные бинарники на Rust; вызывать из Python через subprocess или как сервис. |
| 6 | **JSON (горячие пути)** | Сериализация/десериализация в горячих местах | `orjson.loads` / `orjson.dumps` в коде; при полном переходе — Rust-сервис с JSON API | Уже можно использовать orjson в Python без Rust; при миграции сервисов на Rust — нативно. |

### Где уже готово к подстановке Rust

- **db_pool.py** — один вызов `asyncpg.create_pool`; при миграции заменить на создание пула из Rust (через PyO3 или отдельный процесс с HTTP).
- **rest_api.py**, **collective_memory.py**, **context_analyzer.py** — используют `get_pool()` из `db_pool`; замена пула подставит Rust без правок в этих файлах.
- **embedding_optimizer.py**, **semantic_cache.py** — используют `cache_normalizer` при наличии; контракт нормализации не меняется.

### Следующие шаги (после текущих оптимизаций)

1. Замерить профиль под нагрузкой (py-spy, cProfile) и подтвердить очередность по таблице.
2. Для пула БД: спроектировать API обёртки (например `async with pool.acquire() as conn`) и реализовать его на Rust (deadpool + tokio-postgres) или оставить asyncpg и оптимизировать только размер пула и таймауты.
3. Документировать каждый новый Rust-модуль в этом файле (как сделано для cache_normalizer) с контрактом и способом отката на Python.
