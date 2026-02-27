# Gateway и подъём стека — как правильно

## 1. Dockerfile (образ Gateway)

В **`infrastructure/docker/gateway/Dockerfile`** база должна быть:

```dockerfile
FROM rust:1-slim-bookworm AS builder
```

**Неверно:** `rust:1.76-bookworm-slim` или `rust:1.82-bookworm-slim` — таких тегов на Docker Hub нет (официальный тег — **slim-bookworm**, не bookworm-slim).

---

## 2. Порядок подъёма (эксперты, узлы знаний, знания гигантов)

Чтобы **atra chat** ходил в Victoria (эксперты из Docker, узлы знаний, знания гигантов), нужны оба слоя:

1. **Knowledge OS** (Victoria, Veronica, БД, эксперты, knowledge_nodes):

   ```bash
   docker compose -f knowledge_os/docker-compose.yml up -d
   ```

   Или скрипт: `bash scripts/check_and_start_containers.sh`

2. **Web IDE + Gateway** (порт 8081 для atra chat):
   ```bash
   docker compose up -d
   ```
   Поднимет gateway, frontend, backend. Сеть `atra-network` должна существовать (создаётся при первом запуске knowledge_os или `docker network create atra-network`).

---

## 3. Проверка

- Gateway: `curl -s http://localhost:8081/health`
- Чат: `atra chat "привет"` (идёт в Gateway 8081 → Victoria 8010 или Ollama)

---

## 4. /brainstorm и /expert (Cursor)

- **/expert** — агент подключает: экспертов из Docker (team.md, .cursor/rules), узлы знаний (MASTER_REFERENCE, CHANGES), знания гигантов (COGNITIVE_CODE, ai_research). Дизайн: `docs/plans/2026-02-23-expert-and-brainstorm-design.md`.
- **/brainstorm** — перед креативной работой: вопросы по одному, 2–3 подхода, дизайн в `docs/plans/`, одобрение, затем writing-plans (без перехода к коду до одобрения).

Правило: `.cursor/rules/expert_and_brainstorm.mdc` (alwaysApply).

---

## 5. Все проекты (существующие и новые)

В контейнерах Victoria/Veronica смонтировано:

- `..` → `/workspace/atra-web-ide` (главный проект)
- `../../dev` → `/workspace/dev` (все проекты из dev/ — **автоматически**)

Один запущенный стек (Knowledge OS + Gateway) обслуживает все проекты. Контекст задаётся при вызове:

- По умолчанию: `project_context = "atra-web-ide"` (из `~/.config/atra/config.toml` или env `PROJECT_CONTEXT`).
- Для проекта из dev/ — имя папки:
  ```bash
  export PROJECT_CONTEXT=setki-21
  atra chat "задача по сеткам"
  ```
  или в `~/.config/atra/config.toml`: `project_context = "setki-21"` (или `"atra"`).

**Новые проекты — автоматически.** Достаточно создать папку в `dev/` (например, `dev/my-new-app`). При следующем запросе к Victoria реестр проектов подхватит её (сканирование `/workspace/dev`). Правка docker-compose не нужна. Использование: `PROJECT_CONTEXT=my-new-app atra chat "..."` или запись в конфиге.

Gateway и Victoria общие для всех проектов. Переключение проекта: через `project_context` в конфиге/env **или** прямо в сообщении — фразы «перейди в проект setki-21», «в проекте atra», «открой проект my-app» автоматически задают контекст для этого запроса. Имя проекта = имя папки в `dev/` (только буквы, цифры, дефис).
