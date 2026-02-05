# Новый проект: минимальные шаги подключения к корпорации

Краткий чеклист, чтобы новый проект начал работать с Victoria, Veronica, оркестратором и знаниями корпорации.

## 1. Регистрация проекта (один раз)

Выполнить **одно** из двух:

- **Скрипт** (из репо atra-web-ide или knowledge_os, с настроенным `DATABASE_URL`):
  ```bash
  python scripts/register_project.py my-project "My Project Name" --description "Описание"
  ```
- **API** (Knowledge OS REST API, порт 8002):
  ```bash
  curl -X POST http://localhost:8002/api/projects/register \
    -H "X-API-Key: <API_KEY>" \
    -H "Content-Type: application/json" \
    -d '{"slug": "my-project", "name": "My Project Name", "description": "Описание"}'
  ```

После регистрации перезапустить Victoria и Veronica (или дождаться обновления кэша реестра), если они уже запущены.

## 2. В репо нового проекта

### Переменные окружения (.env)

Скопировать из примера [.env.client.example](../.env.client.example) или задать вручную:

- `PROJECT_CONTEXT=my-project` — slug, указанный при регистрации.
- `VICTORIA_URL=http://localhost:8010` (или адрес хоста/контейнера корпорации).
- `VERONICA_URL=http://localhost:8011` — при прямых вызовах Veronica.
- `KNOWLEDGE_OS_API_URL=http://localhost:8002` — при логировании, board/consult и т.п.
- `BACKEND_URL=…` — если у проекта свой backend, который проксирует запросы к Victoria.

### Передача project_context в запросах

Во всех запросах к Victoria/backend передавать в теле (или по контракту API) поле `project_context` со значением slug проекта (например `my-project`).

## 3. Опционально

- Скопировать [.cursorrules](.cursorrules) или [knowledge_os/docs/STEP_BY_STEP_NEW_PROJECT_SETUP.md](knowledge_os/docs/STEP_BY_STEP_NEW_PROJECT_SETUP.md) для настройки Cursor и команды экспертов в новом проекте.

Подробнее: [MASTER_REFERENCE.md](MASTER_REFERENCE.md) §1а, §1б, §1в.
