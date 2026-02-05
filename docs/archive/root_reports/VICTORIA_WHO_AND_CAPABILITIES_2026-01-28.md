# Victoria / Виктория — кто она и все возможности (актуально на 28.01.2026)

**Источники:** все упоминания Victoria/Виктория в проекте, кроме PLAN.md; **все чаты** (текущие + бэкап).  
**Дата сводки:** 2026-01-28.

---

## 1. Кто такая Victoria

**Victoria (Виктория)** — один агент, **Team Lead** и главный координатор корпорации ATRA (Singularity 9.0).

- **Роль:** главный координатор и Team Lead; управляет командой экспертов, распределяет задачи, координирует работу системы.
- **Экземпляр:** один агент на порту **8010**; веб-чат и Telegram подключаются к одному и тому же Victoria.
- **Код:** `knowledge_os/app/victoria_enhanced.py` — класс `VictoriaEnhanced`.
- **Конфиг:** `.cursorrules` — Victoria Agent, порт 8010, общий для всех проектов (atra-web-ide, atra).

### Доступ

| Куда | Как |
|------|-----|
| Локально | `http://localhost:8010` |
| Web IDE | Frontend (3002) → Backend (8080) → Victoria (8010) |
| Telegram | Telegram Bot → напрямую Victoria (8010) |
| Удалённо | `http://185.177.216.15:8010` (atra), `8020` (atra-web-ide) |
| Docker | контейнер `victoria-agent` из `knowledge_os/docker-compose.yml` |

---

## 2. Все возможности Victoria

### 2.1 Victoria Enhanced — компоненты (по отчёту 28.01.2026)

На 28.01 активны **18 компонентов**:

- **ReActAgent** — Think → Act → Observe → Reflect, вызов инструментов.
- **ExtendedThinkingEngine** — глубокое рассуждение для reasoning-задач.
- **SwarmIntelligence** — параллельная работа команды экспертов.
- **ConsensusAgent** — согласование решений.
- **TaskDelegator** — делегирование задач Veronica и другим агентам.
- **Event Bus** — событийная шина.
- **Skill Registry** — регистр скиллов (24+ skills).
- **Department Heads System** — отделы (Frontend, Backend, ML/AI и др.), координация через Department Head.
- **HierarchicalOrchestrator** — иерархическая оркестрация (root_agent="Victoria").
- **Collective Memory** — коллективная память.
- **Metacognitive Learner** — метакогнитивное обучение (agent_name="Victoria").
- **Agent Evolver** — самоэволюция агента.
- **Victoria Event Handlers** — обработчики событий, state machines.
- И ещё 5+ компонентов (Observability, Cache, Model Router и т.д.).

### 2.2 Инструменты (ReAct)

Victoria может выполнять действия, а не только отвечать текстом:

| Инструмент | Назначение |
|------------|------------|
| **read_file** | Чтение файлов (`file_path`) |
| **run_terminal_cmd** | Выполнение команд в терминале |
| **list_directory** | Список файлов в директории |
| **create_file** | Создание файла (`file_path`, `content`) |
| **write_file** | Запись/перезапись файла |
| **search_knowledge** | Поиск в базе знаний |
| **finish** | Завершение задачи с результатом |

### 2.3 Выбор метода (автоматический)

- **Simple** — быстрые ответы, без инструментов (MLX в приоритете).
- **ReAct** — задачи с действиями («создай», «выполни», «прочитай», «напиши код»); используются инструменты выше.
- **Extended Thinking** — глубокое рассуждение; без инструментов.
- **Department Heads** — задача попадает в отдел (по ключевым словам); координация через Department Head и экспертов; для задач создания файлов/сайтов может принудительно выбираться ReAct.
- **Делегирование** — передача задачи **Veronica** (порт 8011) через TaskDelegator.

### 2.4 Модели и окружение

- **Приоритет:** MLX API Server (порт 11435), fallback Ollama (11434).
- **В Docker:** `host.docker.internal` для доступа к MLX/Ollama с хоста.
- **Rate limit / ошибки:** при 429 и 5xx от MLX — fallback на Ollama (в т.ч. в Extended Thinking и ReAct).

### 2.5 База знаний и эксперты

- **58+ экспертов** в Knowledge OS (БД PostgreSQL + pgvector).
- **Department Heads** — отделы с ключевыми словами (Frontend, Backend, ML/AI, Security, QA, Marketing и др.).
- **Поиск:** `search_knowledge` в ReAct; контекст из БД для ответов.

### 2.6 Документация и контекст

- **VICTORIA.md** — роль, правила, приоритеты, инструменты, частые задачи.
- **VERONICA.md** — контекст для Veronica (исполнитель, получает задачи от Victoria).
- **configs/experts/team.md** — команда экспертов.

---

## 3. Последние изменения и статус на 28 января 2026 (без PLAN.md)

### 3.1 Отчёт о состоянии корпорации (28.01.2026)

**Файл:** `CORPORATION_STATUS_REPORT_2026-01-28.md`.

- **Victoria Agent:** работает (порт 8010).
- **Victoria Enhanced:** все 18 компонентов активны.
- **TaskDelegation:** Victoria может делегировать задачи Veronica.
- **Event-Driven:** Event Bus и Skill Registry работают.
- **Проблемы:** нет новых задач за 24 ч, Nightly Learner — 404 по моделям Ollama, Cross-Domain Linker не создаёт гипотезы; Enhanced Orchestrator не создаёт задачи.

### 3.2 Что по Victoria сделано к 28.01 (из чатов и доков)

- Подключение Victoria к корпорации (все компоненты инициализированы).
- Одна Victoria для веб и Telegram (архитектура в `VICTORIA_ARCHITECTURE_EXPLAINED.md`).
- Инструменты ReAct интегрированы (не заглушки): read_file, run_terminal_cmd, create_file, write_file, list_directory, search_knowledge.
- MLX в приоритете, fallback на Ollama; обработка 429/5xx в Extended Thinking и ReAct.
- Department Heads: проверка «создание файла/сайта» до определения отдела; для таких задач — ReAct, а не department_heads.
- Telegram: меньше лишних сообщений (одно стартовое на операцию, реже прогресс).
- Скрипты/утилиты: централизованные `scripts.utils.environment` и `scripts.utils.path_setup`; в тестах — корректный DATABASE_URL и пути.

### 3.3 Автозапуск и восстановление

- **Victoria** поднимается из `knowledge_os/docker-compose.yml` (контейнер `victoria-agent`).
- **Автовосстановление:** `scripts/system_auto_recovery.sh` (при настроенном launchd — раз в 5 мин); при падении health Victoria контейнер перезапускается.
- **Запуск вручную:**  
  `docker-compose -f knowledge_os/docker-compose.yml up -d`  
  затем при необходимости корневой `docker-compose up -d`.

---

## 4. Выжимка из всех чатов

**Просканировано:** 7 текущих транскриптов (`agent-transcripts/`) + 34 транскрипта в бэкапе (`.cursor_chats_backup/agent-transcripts/`).  
**Упоминаний Victoria/Виктория:** 7086 (в 27 чатах).

### 4.1 Кто она (по чатам)

- **Victoria Agent — Team Lead (port 8010).** В чатах явно: «Victoria - это Team Lead агент в корпорации ATRA», «Victoria Enhanced имеет множество возможностей».
- **Один агент:** одна Victoria на 8010; веб и Telegram подключаются к одному экземпляру. В чатах: проверки конфигурации Victoria и Veronica, порты 8010/8011, `victoria-agent` из `knowledge_os/docker-compose.yml`.
- **По умолчанию:** «Если префикса нет — Виктория по умолчанию», «По умолчанию Виктория координирует все».
- **Роль в команде:** «Виктория (Team Lead)», «эксперты обсуждают, Виктория подводит итог», «Veronica консультируется с экспертами и локальными LLM; Victoria координирует». Для запросов про безопасность/доступ в чатах вызывают «Алексей (Security), Игорь (Backend), Виктория (Team Lead)».
- **Системный промпт (из кода в чатах):** «ТЫ — ВИКТОРИЯ, TEAM LEAD ATRA. ТВОЯ ЗАДАЧА — ВЫПОЛНЯТЬ ДЕЙСТВИЯ.»

### 4.2 Возможности (по чатам)

- **Victoria Enhanced:** в чатах многократно — «интеграция в Victoria Enhanced выполнена», «все компоненты интегрированы в Victoria Enhanced», «Victoria Enhanced — включает все компоненты супер-корпорации», «Victoria как Team Lead использует самую мощную модель».
- **Компоненты:** ReActAgent, Extended Thinking, Swarm, Consensus, TaskDelegator, Event Bus, Skill Registry, Department Heads, Hierarchical Orchestrator; в чатах — проверки импорта `VictoriaEnhanced`, настройка `VICTORIA_URL=http://host.docker.internal:8010`, проверка health на 8010.
- **Инструменты:** в чатах — интеграция реальных инструментов (не заглушки): read_file, run_terminal_cmd, create_file, write_file, list_directory, search_knowledge.
- **Делегирование:** Victoria делегирует Veronica; в чатах — «Victoria может делегировать задачи», конфигурация Victoria и Veronica (порты 8010, 8011), контейнеры `victoria-agent`, `veronica-agent`.

### 4.3 Последние изменения (по чатам)

- **Конфигурация:** выравнивание портов 8010/8011 в обоих docker-compose; `victoria-agent` из knowledge_os; проверки health, зависимостей, .env.
- **Интеграция:** новые компоненты (Metacognitive, Agent Evolver и др.) интегрированы в Victoria Enhanced; импорты и инициализация в `victoria_enhanced.py`.
- **Telegram/веб:** одна Victoria для обоих каналов; в бэкапе чатов — авто-роутинг в Telegram (отправка в MAS или в ai_core/Виктория), шаблоны роли «Виктория» в Query Orchestrator.
- **Оркестрация:** «Промпт собран через шаблон роли: роль=Виктория»; выбор 2–3 экспертов с обязательным включением Виктории как лидера.

### 4.4 Чаты без упоминаний Victoria

- Один текущий транскрипт (`943dfdd1-...`) и 13 транскриптов в бэкапе не содержат слов Victoria/Виктория — в сводке не использованы.

---

## 5. Где искать упоминания Victoria/Виктория (кроме PLAN.md)

- **Роль и правила:** `VICTORIA.md`
- **Возможности и инструменты:** `VICTORIA_CAPABILITIES.md`, `VICTORIA_IS_NOT_JUST_CHAT.md`
- **Архитектура (веб vs Telegram):** `VICTORIA_ARCHITECTURE_EXPLAINED.md`
- **Статус на 28.01:** `CORPORATION_STATUS_REPORT_2026-01-28.md`
- **Почему может быть офлайн и автопроверки:** `docs/WHY_VICTORIA_OFFLINE_AND_AUTOCHECKS.md`
- **Код:** `knowledge_os/app/victoria_enhanced.py`, `knowledge_os/app/react_agent.py`
- **Конфиг проекта:** `.cursorrules`
- **Чаты:** `agent-transcripts/` (7 файлов), `.cursor_chats_backup/agent-transcripts/` (34 файла)

---

## 6. Краткий итог

**Victoria** — единый Team Lead и оркестратор на порту 8010. Она планирует задачи, выбирает метод (ReAct, Department Heads, делегирование Veronica, Extended Thinking, Swarm), координирует 58+ экспертов, использует 7 инструментов ReAct (файлы, команды, база знаний), работает с MLX и Ollama, доступна из веб-чата и Telegram. На 28.01.2026 все 18 компонентов Victoria Enhanced активны; ограничения касаются общей активности корпорации (создание задач, обучение, гипотезы), а не самой Victoria.

---

## 7. В итоге: что должно работать — Victoria Initiative, Victoria Agent, Victoria Enhanced

Это **не три разных сервиса**, а **один процесс** с разными уровнями:

| Что | Что это | Где живёт |
|-----|---------|-----------|
| **Victoria Agent** | Контейнер/сервис, который **должен работать**. Запускает `victoria_server` (HTTP API на порту 8010). | `knowledge_os/docker-compose.yml` → сервис `victoria-agent`, команда `python -m src.agents.bridge.victoria_server` |
| **Victoria Enhanced** | Режим/код **внутри** Victoria Agent: класс `VictoriaEnhanced`, 18 компонентов (ReAct, Extended Thinking, Swarm, Department Heads, делегирование и т.д.). | Включается переменной **`USE_VICTORIA_ENHANCED=true`** в контейнере `victoria-agent`. Код: `knowledge_os/app/victoria_enhanced.py` |
| **Victoria Initiative** | Набор проактивных/событийных возможностей **внутри** того же контейнера: Event-Driven, мониторинг, file watcher, deadline tracker, skills watcher. | Включается переменными в `victoria-agent`: `ENABLE_EVENT_MONITORING`, `FILE_WATCHER_ENABLED`, `SERVICE_MONITOR_ENABLED`, `DEADLINE_TRACKER_ENABLED`, `SKILLS_WATCHER_ENABLED` (в docker-compose уже заданы) |

**Итого что должно работать у вас:**

1. **Один запущенный процесс:** **Victoria Agent** (контейнер `victoria-agent`, порт 8010).
2. **Внутри него:** **Victoria Enhanced** включён (`USE_VICTORIA_ENHANCED=true` в docker-compose) — запросы обрабатываются через `VictoriaEnhanced.solve()`.
3. **Плюс:** **Victoria Initiative** — те же флаги мониторинга/событий в docker-compose включены; при старте вызывается `victoria_enhanced_instance.start()`, поднимаются event bus, file watcher, service monitor и т.д.

**Проверка:**
```bash
# Контейнер (Victoria Agent) запущен?
docker ps | grep victoria-agent

# Health
curl http://localhost:8010/health

# Статус Victoria Enhanced (должен быть enabled)
curl http://localhost:8010/status
```

**Вывод:** Должна работать **одна** сущность — **Victoria Agent**. В ней по конфигу уже включены **Victoria Enhanced** и **Victoria Initiative**; отдельно их запускать не нужно.
