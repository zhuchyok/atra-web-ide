# Источники готовых скиллов для ATRA / Victoria

Краткий обзор внешних репозиториев и маркетплейсов скиллов в формате SKILL.md (Agent Skills). Наш реестр (`knowledge_os/app/skill_registry.py`) поддерживает этот формат.

---

## Список необходимых нам скиллов

**Уже есть у нас (не трогать):**  
anomaly-detection, circuit-breaker, claude-code-integration, code-analysis, code-documentation, code-refactoring, code-review, code-smell-predictor, collective-memory, consensus-agent, context-compression, disaster-recovery, docx, emotion-detection, event-driven, example-skill, extended-thinking, guardrails, hierarchical-orchestration, hitl, mcp-builder, ml-router, model-ensemble, observability, ollama-cloud, parallel-processing, pdf, react-reasoning, recap-framework, self-correction, self-learning, semantic-cache, state-machine, streaming, swarm-intelligence, tacit-knowledge, tree-of-thoughts, vision-processing, xlsx.

**Нужно добавить (в порядке приоритета):**

| № | Скилл | Источник | Зачем |
|---|--------|----------|--------|
| 1 | ask-questions-if-underspecified | Ai-Agent-Skills | Уточнять требования до реализации (стыкуется с HITL и уточняющими вопросами Victoria) |
| 2 | file-organizer | Ai-Agent-Skills / ComposioHQ | Упорядочивание файлов, поиск дубликатов в workspace |
| 3 | pptx | Ai-Agent-Skills / Anthropic | Презентации (дополнение к pdf, docx, xlsx) |
| 4 | skill-creator | Ai-Agent-Skills / Anthropic | Гайд по созданию новых скиллов |
| 5 | webapp-testing | Ai-Agent-Skills / Anthropic | Тестирование веб-приложений (Playwright и т.п.) |
| 6 | backend-development | Ai-Agent-Skills | Паттерны API, БД, серверная архитектура |
| 7 | python-development | Ai-Agent-Skills | Современный Python 3.12+ для агента |
| 8 | changelog-generator | Ai-Agent-Skills | Генерация changelog из коммитов |
| 9 | llm-application-dev | Ai-Agent-Skills | Проектирование LLM-приложений |
| 10 | frontend-design | Anthropic / Ai-Agent-Skills | UI-компоненты и вёрстка |
| 11 | doc-coauthoring | Anthropic / Ai-Agent-Skills | Соавторство доков и спецификаций |
| 12 | internal-comms | Anthropic | Статусы и коммуникация в команде |
| 13 | jira-issues | Ai-Agent-Skills / OpenClaw | Создание/поиск тикетов Jira (если используете) |
| 14 | code-documentation | уже есть | — |
| 15 | content-research-writer | ComposioHQ | Исследование и тексты с цитатами |

**Опционально (по задаче):**  
notion-skill, google-calendar, linear-issues, telegram-* (из OpenClaw), memory/context-* (если нужны доп. варианты).

---

## 1. SkillCreator.ai / Ai-Agent-Skills (уже подключено)

- **Репозиторий:** https://github.com/skillcreatorai/Ai-Agent-Skills  
- **Установка:** `npx ai-agent-skills install <skill-name>` или копирование из `skills/` в `knowledge_os/app/skills/`.
- **У нас уже скопированы:** pdf, docx, xlsx, code-review, code-refactoring, code-documentation, mcp-builder.
- **Ещё полезно взять:** ask-questions-if-underspecified, file-organizer, backend-development, python-development, webapp-testing, changelog-generator, llm-application-dev, skill-creator.

---

## 2. Anthropic (официальный репозиторий)

- **Репозиторий:** https://github.com/anthropics/skills  
- **Звёзды:** ~60k. Официальные примеры и документ-скиллы (pdf, docx, pptx, xlsx) — source-available.
- **Структура:** плоская, `skills/<skill-name>/` с SKILL.md.
- **Что полезно:**
  - **Документы:** pdf, docx, pptx, xlsx (референсные реализации, могут отличаться лицензией).
  - **Разработка:** frontend-design, web-artifacts-builder, webapp-testing, mcp-builder, skill-creator.
  - **Креатив/бизнес:** brand-guidelines, internal-comms, doc-coauthoring, canvas-design, theme-factory.
- **Как взять:**  
  `git clone https://github.com/anthropics/skills.git` → копировать нужные папки из `skills/` в `knowledge_os/app/skills/`.

---

## 3. OpenClaw / ClawdHub (архив скиллов Clawbot)

- **Репозиторий:** https://github.com/openclaw/skills  
- **Сайт маркетплейса:** https://clawdhub.com  
- **Установка через CLI:** `npx clawhub@latest install <skill-name>`.
- **Особенность:** в GitHub скиллы лежат в виде `skills/<author>/<skill-name>/` (например `skills/apatki1996/gita-sotd/`). Чтобы подключать к нам — копировать нужные `<skill-name>` в нашу папку (при конфликте имён можно переименовать в `skill-name-author`).
- **Что полезно:** сотни community-скиллов (Jira, Notion, Google Calendar, трейдинг, память, поиск и т.д.). Выбирать по названию на clawdhub.com, затем брать из репо по пути `skills/<author>/<skill-name>/`.

---

## 4. ComposioHQ Awesome Claude Skills

- **Репозиторий:** https://github.com/ComposioHQ/awesome-claude-skills  
- **Звёзды:** ~28k. Курированный набор из 32 скиллов.
- **Структура:** плоская, папка на скилл с SKILL.md.
- **Популярные:** content-research-writer, file-organizer, youtube-downloader, tailored-resume-generator, code-reviewer, skill-creator.
- **Как взять:** клонировать репо и копировать нужные папки в `knowledge_os/app/skills/`.

---

## 5. Спецификация и маркетплейсы

- **Спека Agent Skills:** https://agentskills.io (формат SKILL.md, name, description, scripts/, references/).
- **SkillsMP:** https://skillsmp.com — маркетплейс с большим количеством скиллов в формате Agent Skills (поиск по категориям и семантике).
- **SkillCreator Explore:** https://skillcreator.ai/explore — каталог с установкой в один клик (целевые папки — под Cursor/Claude; нам нужно копировать в наш каталог).

---

## Как подключать к нам

1. **Единый каталог:** все скиллы лежат в `knowledge_os/app/skills/` (или дополнительно в `managed_skills_dir`). Один скилл = одна папка с `SKILL.md` и при необходимости `scripts/`, `references/`, `assets/`.
2. **Копирование:** склонировать нужный репозиторий и скопировать папки скиллов в `knowledge_os/app/skills/`. При дублировании имён — переименовать (например `code-review-composio`).
3. **OpenClaw:** при копировании из `openclaw/skills` брать содержимое `skills/<author>/<skill-name>/` в папку с уникальным именем, например `knowledge_os/app/skills/<skill-name>-openclaw`.
4. **Перезагрузка:** перезапуск Victoria (`docker restart victoria-agent`) или включённый SkillLoader watcher подхватят новые скиллы.

---

## Рекомендуемый порядок

1. **Уже есть:** Ai-Agent-Skills (pdf, docx, xlsx, code-review, code-refactoring, code-documentation, mcp-builder).
2. **Добавить при необходимости:** из Anthropic — webapp-testing, frontend-design, skill-creator; из ComposioHQ — file-organizer, ask-questions-if-underspecified (если ещё нет).
3. **Массово из сообщества:** OpenClaw/clawdhub — по мере надобности, выборочно (Jira, Notion, календари и т.д.).
4. **Поиск по темам:** SkillsMP и skillcreator.ai/explore — для поиска по категориям, затем установка/копирование в наш каталог.
