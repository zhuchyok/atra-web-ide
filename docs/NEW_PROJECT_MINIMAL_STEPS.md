# Новый проект: минимальные шаги подключения к корпорации

Краткий чеклист, чтобы новый проект начал работать с Victoria, Veronica, оркестратором и знаниями корпорации.

## 0. Автоматизация (чтобы не забыть при следующих деплоях)

Добавить новый проект в репозиторий в **двух местах** — тогда при применении миграций и при fallback реестра проект уже будет в списке:

1. **Сидер миграции** `knowledge_os/db/migrations/add_projects_table.sql`: в блок `INSERT INTO projects ... VALUES` добавить строку вида  
   `('slug', 'Name', 'Описание', '/workspace/slug', true)` (перед `ON CONFLICT (slug) DO NOTHING`).
2. **Fallback реестра** `src/agents/bridge/project_registry.py`: в `DEFAULT_PROJECT_CONFIGS` добавить запись для slug; в строке `os.getenv("ALLOWED_PROJECTS", "atra-web-ide,atra,...")` добавить новый slug через запятую.

После этого выполнить шаг 1 (регистрация в БД), если таблица `projects` уже существует и нужно, чтобы текущий инстанс увидел проект сразу.

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
