# Верификация автономности ATRA Web IDE

Документ описывает, как проверить работу системы **без доступа к внешним API** (режим «цифровой крепости»): только локальные сервисы (Rust Gateway, Ollama, PostgreSQL, Knowledge OS).

## Условия автономности

- **Нет интернета** или интернет отключён для приложения (firewall / airplane).
- **Нет облачных LLM**: не используются OpenAI, Anthropic, и т.п.
- Используются только: **Rust API Gateway (8081)**, **Ollama (11434)**, **PostgreSQL (5432)** с Knowledge OS, при необходимости **Victoria/Veronica** в Docker (8010, 8011) — но для базового чата через `atra` достаточно Gateway + Ollama + БД.

## Что должно быть запущено

1. **PostgreSQL** с базой `knowledge_os` (и при необходимости pgvector).
2. **Ollama** с хотя бы одной моделью (например `victoria-wisdom-30b:latest` или `tinyllama:1.1b-chat`).
3. **Rust API Gateway** на порту 8081:
   ```bash
   WORKSPACE_ROOT=/path/to/atra-web-ide RUST_LOG=info /path/to/atra-web-ide/target/release/gateway
   ```

Переменная `DATABASE_URL` должна указывать на локальную БД (например `postgres://postgres:postgres@localhost:5432/knowledge_os`).

## Проверка автономности через atra chat

### 1. Простой запрос (дымовой тест)

```bash
atra chat "Привет! Ответь одним предложением на русском."
```

Ожидание: ответ на русском от локальной модели через Gateway без ошибок 5xx/таймаутов.

### 2. Сложная задача без внешних API

Примеры запросов, которые должны обрабатываться **полностью локально** (RAG + Ollama):

```bash
# Вопрос по коду с контекстом файла (путь от корня репозитория)
atra chat "Объясни, что делает этот код и предложи улучшение @rust_core/gateway/src/main.rs"

# Запрос, использующий базу знаний (RAG)
atra chat "Как в нашем проекте устроена работа с экспертами и доменами?"

# Задача на планирование (логика Victoria в Gateway)
atra chat "Составь план из 3 шагов по рефакторингу API файлов."
```

Критерии успеха:

- Ответ приходит на русском.
- Нет ошибок вида `503 Service Unavailable` / `All models failed` (при стабильно работающем Ollama).
- При наличии индексированных узлов в `knowledge_nodes` ответ может опираться на RAG-контекст.

### 3. Проверка полного контура (Victoria Agent)

Если `USE_VICTORIA_AGENT=true` (по умолчанию), Gateway пробует вызвать Victoria Agent (порт 8010).

```bash
# Запрос, который должен уйти в Victoria (мозг MLX + руки Ollama)
atra chat "Проанализируй структуру проекта и предложи 3 улучшения для безопасности."
```

Критерии успеха:
- В логах Gateway: `Victoria Agent responded successfully (full brain+hands)`.
- Ответ содержательный, на русском, учитывает контекст проекта.
- При выключенной Victoria (порт 8010 недоступен) запрос автоматически уходит в Ollama (fallback), в логах: `Victoria Agent unavailable or failed (...), falling back to Ollama`.

## 4. Что проверить при сбоях

| Симптом | Возможная причина | Действие |
|--------|--------------------|----------|
| `connection refused` к 8081 | Gateway не запущен | Запустить Gateway (см. выше). |
| `503 All models failed` | Ollama не отвечает или нет модели | Проверить `ollama list`, перезапустить `ollama serve`. |
| Ошибка БД при RAG | Нет БД или нет таблицы `knowledge_nodes` | Проверить `DATABASE_URL`, миграции Knowledge OS. |
| `atra: command not found` | PATH или alias | Выполнить `source ~/.zshrc` или использовать полный путь к `atra`. |

## Минимальный сценарий «только Rust + Ollama»

Для проверки **без PostgreSQL** (без RAG) можно временно отключить использование БД в Gateway (в коде) или убедиться, что при недоступной БД чат всё равно идёт в Ollama (если логика это допускает). В текущей реализации Gateway ожидает работающую БД для RAG и для `/api/experts`, `/api/domains`. Поэтому для полной автономности БД должна быть доступна.

## Итог

- **Автономность** в смысле «сложная задача через atra chat без внешних API» считается успешной, если запросы из пунктов 1–2 выполняются без обращения к облаку и с корректным ответом на русском.
- **CLI Расширение:** Новые команды `status`, `cleanup`, `describe`, `plan` позволяют полностью управлять системой из терминала.

---

### 4. Проверка новых CLI-команд (Rust)

Для проверки расширенных возможностей CLI:

1.  **Проверка статуса системы:**
    ```bash
    ./target/release/atra status
    ```
    *Ожидаемый результат:* Вывод CPU, RAM, Disk и статистики Knowledge Base.

2.  **Проверка очистки данных (Data Retention):**
    ```bash
    ./target/release/atra cleanup --dry-run
    ```
    *Ожидаемый результат:* Отчет о количестве записей, подлежащих удалению в `real_time_metrics` и `semantic_ai_cache`.

3.  **Проверка мультимодальности (Vision):**
    ```bash
    ./target/release/atra describe path/to/image.png
    ```
    *Ожидаемый результат:* Текстовое описание изображения от Victoria (через Moondream или Ollama fallback).

4.  **Проверка планирования:**
    ```bash
    ./target/release/atra plan "Добавь поддержку темной темы в frontend"
    ```
    *Ожидаемый результат:* Подробный план действий от Victoria.

---

### 5. Автономность: Зеркало Crates.io и Scout

1.  **Проверка Scout (Rust Docs):**
    Проверьте логи терминала, где запущен `scout --rust-docs`. Он должен индексировать главы Rust Book.
    Убедитесь, что в `knowledge_nodes` появляются записи с `source_type = 'rust_doc'`.

2.  **Проверка Panamax (Crates Mirror):**
    Убедитесь, что `panamax sync` продолжается.
    После завершения (или частично), попробуйте собрать любой проект с использованием зеркала:
    ```bash
    # Убедитесь, что ~/.cargo/config.toml настроен на localhost:8081
    cargo build
    ```
