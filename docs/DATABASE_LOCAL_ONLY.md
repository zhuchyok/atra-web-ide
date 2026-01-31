# Локальная база данных (Mac Studio)

В проекте везде используется **только локальная БД** на Mac Studio.

## Дефолты подключения

- **В коде (скрипты, knowledge_os/app):**  
  `DATABASE_URL` или `postgresql://admin:secret@localhost:5432/knowledge_os`
- **В Docker (контейнеры Victoria/Veronica):**  
  в `docker-compose` задаётся `DATABASE_URL=postgresql://admin:secret@knowledge_postgres:5432/knowledge_os` — контейнеры подключаются к сервису `knowledge_postgres` по имени.
- **На хосте (без Docker):**  
  задайте `DATABASE_URL=postgresql://admin:secret@localhost:5432/knowledge_os` (или с вашим пользователем/паролем), если PostgreSQL запущен локально.

## Что сделано

- Удалён дефолтный удалённый хост `185.177.216.15` из `semantic_cache` и других модулей.
- Все дефолты с `zhuchyok@localhost` заменены на `admin:secret@localhost:5432/knowledge_os`.
- Условия вида `if USER_NAME == 'zhuchyok'` убраны; используется общий дефолт или `DATABASE_URL`.
- В коде (Victoria/Veronica bridge и др.) дефолт — `localhost:5432`; в контейнерах `DATABASE_URL` задаётся через compose (`knowledge_postgres`).
- В `.env` — единый локальный URL: `DATABASE_URL=postgresql://admin:secret@localhost:5432/knowledge_os`.

## Где задать DATABASE_URL

- **Docker:** в `knowledge_os/docker-compose.yml` для сервисов уже прописан `DATABASE_URL`.
- **Локальный запуск:** в `.env` или при запуске:  
  `export DATABASE_URL=postgresql://admin:secret@localhost:5432/knowledge_os`
