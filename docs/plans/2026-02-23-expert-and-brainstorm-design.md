# Дизайн: команды /expert и /brainstorm в Cursor

**Дата:** 2026-02-23  
**Цель:** корректно подключать экспертов из Docker, узлы знаний (knowledge_nodes) и «знания гигантов» при работе в Cursor; гарантировать применение скилла brainstorming при креативных задачах.

---

## 1. Контекст

**Архитектура Виктории (полноценный режим):** Мозг (MLX, порт 11435, модель Victoria) + Руки (Ollama, victoria-wisdom-30b, KEEP_ALIVE=-1). Решение зафиксировано в MASTER_REFERENCE, SESSION_HANDOFF. Чтобы мозг Виктории был в MLX: при запуске MLX задать `VICTORIA_MLX_BRAIN=true` (тогда предзагрузка victoria-wisdom-30b в MLX); руки — Ollama с той же моделью. При /expert и настройке окружения учитывать эту связку.

- **Эксперты:** живут в БД (Docker, `knowledge_postgres`), синхронизация из `configs/experts/employees.json`; бэкенд отдаёт список через `GET /api/experts`; роли и стиль — `.cursor/rules/`, `configs/experts/team.md`, `docs/TEAM_PERSONALITIES.md`.
- **Узлы знаний:** таблица `knowledge_nodes` в Knowledge OS; Victoria/Veronica при `USE_KNOWLEDGE_OS=true` подставляют релевантный контекст; в Cursor агент опирается на «библию» и документы из `docs/`.
- **Знания гигантов:** RAG-контент из `knowledge_os/knowledge_base/ai_research/`, индексируется в `knowledge_nodes`; для Cursor — явно указать источники: `docs/MASTER_REFERENCE.md`, `docs/COGNITIVE_CODE.md`, при необходимости `OPENWEBUI_RAG_SETUP.md` и эталоны из `docs/curator_reports/standards/`.

---

## 2. Режим /expert

**Назначение:** при запросе с /expert или «подключи экспертов» агент обязан опираться на три источника.

| Источник               | Как подключить в Cursor                                                                                                                                                                                                                                         |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Эксперты из Docker** | Читать `configs/experts/team.md`, `.cursor/rules/README.md`; при доступном бэкенде — упоминать `GET /api/experts`; в ответах использовать роли и имена из team.md и правил (Игорь, Дмитрий, Анна и т.д.) и стиль из TEAM_PERSONALITIES.                         |
| **Узлы знаний**        | Использовать «библию»: `docs/MASTER_REFERENCE.md`, `docs/CHANGES_FROM_OTHER_CHATS.md`, при необходимости `ARCHITECTURE_FULL`, `VERIFICATION_CHECKLIST_OPTIMIZATIONS`; при реализации в коде — следовать логике Knowledge OS (knowledge_nodes, expert_services). |
| **Знания гигантов**    | Указывать в контексте: `docs/COGNITIVE_CODE.md`, `docs/OPENWEBUI_RAG_SETUP.md`; при проектировании и аудите — мировые практики (12-Factor, first principles, runbook’и из docs).                                                                                |

**Правило:** один источник истины. Эксперты — `employees.json` → team.md + .cursor/rules; знания — MASTER_REFERENCE и связка; гиганты — COGNITIVE_CODE + ai_research в БД (в Cursor — через документы).

---

## 3. Режим /brainstorm

**Назначение:** при запросе с /brainstorm или перед креативной работой (фичи, новые компоненты, смена поведения) агент обязан следовать скиллу **brainstorming**.

**Обязательные шаги (по скиллу):**

1. Изучить контекст проекта (файлы, доки, последние изменения).
2. Задавать уточняющие вопросы по одному (цель, ограничения, критерии успеха).
3. Предложить 2–3 подхода с плюсами/минусами и рекомендацией.
4. Представить дизайн по секциям и получить одобрение по каждой.
5. Записать дизайн в `docs/plans/YYYY-MM-DD-<topic>-design.md`.
6. Перейти к плану внедрения (writing-plans), без перехода сразу к коду.

**Жёсткий запрет:** не переходить к реализации до одобрения дизайна и создания плана.

---

## 4. Реализация

- **Правило Cursor:** `.cursor/rules/expert_and_brainstorm.mdc` с `alwaysApply: true` — текст, описывающий режимы /expert и /brainstorm и обязательные источники/шаги.
- **Команды:** в Cursor Command Palette команды задаются через настройки; правило достаточно, чтобы при вводе пользователем «/expert» или «/brainstorm» (или «подключи экспертов», «сделай брейншторм») агент интерпретировал контекст и вёл себя согласно дизайну.
- **Связь с библией:** в MASTER_REFERENCE или CHANGES_FROM_OTHER_CHATS добавить ссылку на этот дизайн и на правило.

---

## 5. Критерии приёмки

- [ ] При запросе с /expert агент явно опирается на team.md/правила, библию и COGNITIVE_CODE/знания гигантов.
- [ ] При запросе с /brainstorm агент не пишет код до дизайна и одобрения; задаёт вопросы по одному; предлагает подходы; пишет дизайн в docs/plans/ и переходит к writing-plans.
- [ ] Правило expert_and_brainstorm.mdc присутствует и подключено (alwaysApply).

---

_Связь: EXPERT_CONNECTION_ARCHITECTURE, KNOWLEDGE_BASE_WHO_USES, OPENWEBUI_RAG_SETUP, brainstorming skill._
