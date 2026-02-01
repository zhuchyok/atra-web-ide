# Clawdbot Chat — Архитектура чата

Сводка по архитектуре чата Web IDE, интеграции с Victoria и паттернами Clawdbot.

---

## 1. Общая схема потока

```
┌───────────────────────────────────────────────────────────────────────────┐
│  Frontend (Svelte)                                                         │
│  Chat.svelte + stores/chat.js                                              │
└───────────────────────────────────────────────────────────────────────────┘
         │  POST /api/chat/stream
         │  { content, expert_name, use_victoria, mode: "agent"|"plan"|"ask" }
         ▼
┌───────────────────────────────────────────────────────────────────────────┐
│  Backend (FastAPI)                                                         │
│  backend/app/routers/chat.py                                               │
│  sse_generator() → VictoriaClient.run() или MLX/Ollama                     │
└───────────────────────────────────────────────────────────────────────────┘
         │  POST http://victoria-agent:8010/run
         │  { goal, max_steps, project_context }
         ▼
┌───────────────────────────────────────────────────────────────────────────┐
│  Victoria Agent (victoria_server.py или victoria-agent контейнер)          │
│  POST /run → VictoriaEnhanced или Base Agent                               │
└───────────────────────────────────────────────────────────────────────────┘
         │
         ├─► Victoria Enhanced: ReActAgent + Skill Registry + Event Bus
         │   (knowledge_os/app/victoria_enhanced.py)
         │
         └─► Base: OllamaExecutor (только read, run_terminal_cmd, ssh, list)
```

---

## 2. Режимы чата (mode)

| Режим | Описание | Маршрут |
|-------|----------|---------|
| **agent** | Сложные задачи, агент | Victoria Enhanced → ReActAgent + Skills |
| **plan** | Только план | Victoria `/plan` → один вызов LLM, без инструментов |
| **ask** | Простые вопросы | Шаблоны → MLX → Ollama → (fallback) Victoria |

---

## 3. Ask-путь (простой чат)

```
Классификация classify_query()
    │
    ├─ simple (привет, спасибо) → шаблонный ответ (без LLM)
    │
    └─ не simple → MLX API → Ollama → Victoria (fallback)
```

- **Backend:** `backend/app/routers/chat.py` — `classify_query`, `_generate_via_mlx_or_ollama`
- **Victoria fallback:** когда MLX/Ollama не отвечают или недоступны

---

## 4. Agent-путь (Victoria + Clawdbot)

### 4.1 Victoria Enhanced

- **Файл:** `knowledge_os/app/victoria_enhanced.py`
- **Компоненты:**
  - ReActAgent — цикл Think → Act → Observe → Reflect
  - Skill Registry — реестр skills из `knowledge_os/app/skills/`
  - Skill Loader — загрузка SKILL.md, hot-reload
  - Event Bus — события (SKILL_NEEDED и др.)
  - TaskDelegator — делегирование Veronica и другим агентам

### 4.2 Skill Registry (Clawdbot-паттерн)

- **Файл:** `knowledge_os/app/skill_registry.py`
- **Источники skills:**
  1. Bundled: `knowledge_os/app/skills/` (≈50 skills)
  2. Managed: `~/.atra/skills/`
  3. Workspace: `<workspace>/skills/`
- **Формат:** SKILL.md с YAML frontmatter (name, description, metadata.clawdbot)
- **Пример:** `code-review`, `pdf`, `extended-thinking`, `doc-coauthoring` и т.д.

### 4.3 ReActAgent + Skills

- **Файл:** `knowledge_os/app/react_agent.py`
- **Tools:**
  - Из Skill Registry: `user_invocable` skills
  - Статические: `read_file`, `run_terminal_cmd`, `list_directory`, `create_file`, `write_file`, `search_knowledge`, `finish`
- **Запись файлов:** SafeFileWriter (бэкап + проверка пути)

### 4.4 Skill Discovery

- **Файл:** `knowledge_os/app/skill_discovery.py`
- Событие `SKILL_NEEDED` → поиск библиотек/API → генерация SKILL.md → регистрация в реестре

---

## 5. Стриминг SSE

- **Endpoint:** `POST /api/chat/stream`
- **Формат событий:**
  - `step` — шаги агента (exploration, action, clarification)
  - `chunk` — текст ответа
  - `error` — ошибка
  - `end` — конец стрима
- **Frontend:** `chat.js` → `EventSource`/fetch + ReadableStream, парсинг `data: {...}`

---

## 6. API Victoria

| Endpoint | Описание |
|----------|----------|
| `POST /run` | Выполнить задачу (sync или async_mode=true) |
| `GET /run/status/{task_id}` | Статус асинхронной задачи |
| `POST /plan` | Только план |
| `GET /health` | Health check |
| `GET /status` | Статус (skills_count, skill_registry_available и т.д.) |

---

## 7. Clawdbot-паттерны в проекте

| Компонент | Описание |
|-----------|----------|
| Skill Registry | Реестр skills (Agent Skills Framework + Clawdbot) |
| Skill Loader | Загрузка SKILL.md, watcher для hot-reload |
| SafeFileWriter | Бэкап перед записью, проверка пути |
| Event Bus | События (SKILL_NEEDED, FILE_CHANGED и др.) |
| ReActAgent | Think → Act → Observe → Reflect |
| Skill Discovery | Поиск и создание новых skills |

---

## 8. Каналы ввода (как в Clawdbot)

| Канал | Маршрут | Инструменты |
|-------|---------|-------------|
| Web IDE Chat | Victoria (agent/ask) | ReAct + skills, create_file, write_file |
| Telegram | Victoria `/run` | То же |
| Terminal | `v "задача"` → `/api/terminal/ask` → Victoria | То же |

---

## 9. Конфигурация

- **Victoria URL:** `VICTORIA_URL` (по умолчанию http://victoria-agent:8010)
- **USE_VICTORIA_ENHANCED:** включение Victoria Enhanced
- **MLX_API_URL:** для Ask-пути (localhost:11435)
- **Knowledge OS API:** логирование в interaction_logs
