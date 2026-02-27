# ATRA Web IDE

![Lint & Security](https://github.com/bikos/atra-web-ide/actions/workflows/lint-security.yml/badge.svg)
![Coverage](https://github.com/bikos/atra-web-ide/actions/workflows/coverage.yml/badge.svg)
![Tests](https://github.com/bikos/atra-web-ide/actions/workflows/pytest-knowledge-os.yml/badge.svg)
[![codecov](https://codecov.io/gh/bikos/atra-web-ide/branch/main/graph/badge.svg)](https://codecov.io/gh/bikos/atra-web-ide)

Браузерная оболочка для работы с AI-агентами корпорации ATRA.

**Архитектура проекта (структура, порты, запуск, API, метрики, Cursor, команда):** **`docs/PROJECT_ARCHITECTURE_AND_GUIDE.md`**.  
**Участие в разработке:** **`CONTRIBUTING.md`** — тесты, методология, E2E (Playwright), TODO backlog.

**Здесь же — всё по Mac Studio:** серверы, Victoria, Veronica, MCP, миграция, эксперты.  
→ **Индекс:** `docs/MAC_STUDIO_INDEX.md` · **Что скопировано:** `docs/COPY_FROM_ATRA_COMPLETE.md`

**Quick links (онбординг и поиск):** [Библия](docs/MASTER_REFERENCE.md) · [Правки из чатов](docs/CHANGES_FROM_OTHER_CHATS.md) · [Верификация](docs/VERIFICATION_CHECKLIST_OPTIMIZATIONS.md) · [Куратор runbook](docs/CURATOR_RUNBOOK.md) · [Участие](CONTRIBUTING.md) · [FAQ](docs/FAQ.md) · [Как что сделать](docs/HOW_TO_INDEX.md)

## 🎯 Функционал

- 💬 **AI Чат** — общение с Victoria и командой агентов
- 📝 **Редактор кода** — CodeMirror 6 с подсветкой синтаксиса
- 📁 **Файловый менеджер** — просмотр и редактирование файлов
- 🌐 **Live Preview** — предпросмотр веб-страниц
- 🔗 **MCP интеграция** — подключение к VictoriaATRA, Ollama

## 🤖 Модели на Mac Studio (MLX Server - 8 моделей)

| #   | Модель                          | Размер | Назначение                      |
| --- | ------------------------------- | ------ | ------------------------------- |
| 1   | `command-r-plus:104b`           | 104B   | **Архитектор** - сложная логика |
| 2   | `deepseek-r1-distill-llama:70b` | 70B    | Глубокий аудит/Reasoning        |
| 3   | `llama3.3:70b`                  | 70B    | Универсальная                   |
| 4   | `phi3.5:3.8b`                   | 3.8B   | Быстрые задачи                  |
| 5   | `phi3:mini-4k`                  | ~3B    | Лёгкая                          |
| 6   | `qwen2.5-coder:32b`             | 32B    | **Вероника PRO** - код          |
| 7   | `qwen2.5:3b`                    | 3B     | Быстрые задачи                  |
| 8   | `tinyllama:1.1b-chat`           | 1.1B   | Очень быстрая                   |

**Распределение по задачам:**

- 🏗️ Архитектура → `command-r-plus:104b`
- 🔍 Аудит/Reasoning → `deepseek-r1-distill-llama:70b`
- 💻 Код → `qwen2.5-coder:32b` (Вероника)
- ⚡ Быстрые → `qwen2.5:3b`, `phi3.5:3.8b`

**Victoria** при первом запросе сканирует Ollama (и MLX) и выбирает **лучшую доступную** модель (104b → 70b → 32b → …). Список актуален; если модели поменяли — подставится новый лучший вариант. Явно: `VICTORIA_MODEL=имя`. Подробнее: `docs/VICTORIA_PROCESS_FULL.md`.

## 🏗 Технологии

| Компонент | Технология            |
| --------- | --------------------- |
| Frontend  | Svelte + Tailwind CSS |
| Backend   | FastAPI (Python)      |
| Редактор  | CodeMirror 6          |
| AI        | Ollama (Mac Studio)   |
| Стриминг  | Server-Sent Events    |

## 🚀 Быстрый старт

### Установка

```bash
# Клонирование и настройка
cp .env.example .env   # шаблон в корне (без секретов); отредактируйте .env, не коммитьте пароли и токены
```

### Knowledge OS (Victoria, Veronica, оркестратор)

Один раз выполнить установку зависимостей и при наличии БД — миграцию:

```bash
# Из корня репо
bash knowledge_os/scripts/setup_knowledge_os.sh
```

Скрипт создаёт `knowledge_os/.venv` и ставит зависимости из `knowledge_os/requirements.txt`: **asyncpg** (БД), **moondream** (vision), **watchdog** (hot-reload skills) и др. Зависимости устанавливаются один раз при setup, не в рантайме (12-Factor). Если БД недоступна — миграцию можно применить позже: `cd knowledge_os && .venv/bin/python scripts/apply_organizational_columns_migration.py` или один раз запустить Enhanced Orchestrator (Phase 0.5 применит все миграции).

**Работа с картинками (Pillow):** Vision через Moondream Station API работает без Pillow. Кто запускает локальную обработку изображений — один раз выполнить: `bash knowledge_os/scripts/install_pillow.sh`. На macOS при ошибке сборки Pillow нужен libjpeg: при необходимости сначала исправить права — `sudo chown -R $(whoami) /opt/homebrew`, затем `brew install jpeg`.

### Запуск (Docker)

```bash
docker-compose up -d
```

### Запуск (без Docker)

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (в новом терминале)
cd frontend
npm install
npm run dev
```

### Открыть в браузере

http://localhost:5173

## 🔗 MCP Серверы

| Сервер       | URL                       | Описание                |
| ------------ | ------------------------- | ----------------------- |
| Ollama       | http://192.168.1.43:11434 | AI модели на Mac Studio |
| VictoriaATRA | http://localhost:8012/sse | Team Lead агент         |
| Filesystem   | MCP                       | Доступ к файлам         |

## 📁 Структура проекта

```
atra-web-ide/
├── frontend/           # Svelte приложение
│   ├── src/
│   │   ├── components/ # UI компоненты
│   │   ├── stores/     # Состояние
│   │   └── App.svelte
│   └── package.json
│
├── backend/            # FastAPI
│   ├── app/
│   │   ├── main.py
│   │   ├── routers/    # API endpoints
│   │   └── services/   # Бизнес-логика
│   └── requirements.txt
│
├── docker-compose.yml
├── .env
├── .cursorrules
├── PLAN.md
└── README.md
```

## 🤝 Команда ATRA

- **Victoria** — Team Lead & Dispatcher
- **Вероника** (`qwen2.5-coder:32b`) — Ведущий разработчик
- **Архитектор** (`command-r-plus:104b`) — Сложная логика
- **Аналитик** (`deepseek-r1-distill-llama:70b`) — Глубокий аудит
- **Универсал** (`llama3.3:70b`) — Общие задачи

## 📄 Лицензия

MIT
