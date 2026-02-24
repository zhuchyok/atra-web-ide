# Полная проверка системы: что есть, что должно работать, связи, /expert и /brainstorm

**Дата:** 2026-02-23  
**Контекст:** подключение экспертов (Docker, узлы знаний, знания гигантов), скилл brainstorming, единая картина работы.

---

## 1. Источники для /expert (три столпа)

| Источник               | Где находится                                                                                                                                                                                                                             | Как используется                                                                                                                                                                                       |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Эксперты из Docker** | БД `knowledge_os.experts` (контейнер `knowledge_postgres`), синхронизация из `configs/experts/employees.json` через `scripts/sync_employees.py`. Роли и стиль: `configs/experts/team.md`, `.cursor/rules/`, `docs/TEAM_PERSONALITIES.md`. | В Cursor: team.md + README правил; в рантайме: бэкенд `GET /api/experts` (читает БД; при недоступности БД — fallback список 9 экспертов). Оркестратор, Victoria, воркеры — через БД и expert_services. |
| **Узлы знаний**        | Таблица `knowledge_nodes` в Knowledge OS; «библия»: `docs/MASTER_REFERENCE.md`, `docs/CHANGES_FROM_OTHER_CHATS.md`, `ARCHITECTURE_FULL`, `VERIFICATION_CHECKLIST_OPTIMIZATIONS`.                                                          | Victoria/Veronica подставляют релевантный контекст при USE_KNOWLEDGE_OS=true; в Cursor агент опирается на библию и docs/.                                                                              |
| **Знания гигантов**    | RAG: `knowledge_os/knowledge_base/ai_research/`, индексация в knowledge_nodes; документы: `docs/COGNITIVE_CODE.md`, `docs/OPENWEBUI_RAG_SETUP.md`, эталоны в `docs/curator_reports/standards/`.                                           | В Cursor явно подключать MASTER_REFERENCE, COGNITIVE_CODE; при проектировании — 12-Factor, first principles, runbook’и.                                                                                |

**Правило:** при запросе /expert или «подключи экспертов» агент обязан опираться на все три источника и явно указывать их (см. `.cursor/rules/expert_and_brainstorm.mdc`).

---

## 2. Режим /brainstorm (обязательный скилл)

**Когда:** /brainstorm или креативная задача (фичи, новые компоненты, смена поведения).

**Шаги (без перехода к коду до одобрения):**

1. Изучить контекст (файлы, доки, последние изменения).
2. Задавать уточняющие вопросы **по одному** (цель, ограничения, критерии успеха).
3. Предложить **2–3 подхода** с плюсами/минусами и рекомендацией.
4. Представить **дизайн по секциям**, после каждой — одобрение.
5. Записать дизайн в `docs/plans/YYYY-MM-DD-<topic>-design.md`.
6. Следующий шаг — **writing-plans** (план внедрения), не код.

**Скилл в рантайме:** `knowledge_os/app/skills/collective-brainstorming/SKILL.md` — автономное обсуждение (Игорь, Анна, Елена под руководством Виктории); триггеры в ai_core: brainstorm, обсуди с экспертами, спроектируй.

---

## 3. Что должно работать и связи (проверено 2026-02-23)

### 3.1 Ядро (мозг + руки + координация)

| Компонент             | Ожидание                                  | Статус проверки                                                  | Связи                                                                        |
| --------------------- | ----------------------------------------- | ---------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| **MLX API (мозг)**    | Порт 11435, health OK, модели в кэше.     | ✅ healthy, models_cached: 1 (victoria-wisdom-30b), memory ~50%. | Victoria, оркестратор, local_router обращаются к host.docker.internal:11435. |
| **Ollama (руки)**     | Порт 11434, victoria-wisdom-30b в списке. | ✅ api/tags отвечает, victoria-wisdom-30b:latest в списке.       | Victoria, Open WebUI, воркеры — host.docker.internal:11434.                  |
| **Victoria Agent**    | Порт 8010, /health ok.                    | ✅ status ok, agent Виктория.                                    | Бэкенд 8080 → Victoria 8010; Open WebUI ask_victoria → бэкенд → Victoria.    |
| **Backend (Web IDE)** | Порт 8080, /health, зависимости healthy.  | ✅ healthy, victoria/ollama/mlx в health — healthy.              | Frontend 3000, GET /api/experts, POST /api/chat/stream, ask-victoria.        |

### 3.2 Данные и оркестрация

| Компонент                     | Ожидание                                   | Статус проверки                                                   | Связи                                                                            |
| ----------------------------- | ------------------------------------------ | ----------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| **PostgreSQL (knowledge_os)** | Контейнер knowledge_postgres, БД доступна. | ✅ verify_full_recovery_readiness: PostgreSQL доступна и здорова. | Оркестратор, Victoria, бэкенд, воркеры, дашборд — DATABASE_URL.                  |
| **Redis (knowledge_os)**      | Контейнер knowledge_os_redis.              | ✅ healthy (в списке Docker).                                     | Очереди, кэш, бэкенд REDIS_URL.                                                  |
| **Оркестратор**               | knowledge_os_orchestrator запущен.         | ✅ Up.                                                            | Циклы оркестрации, health monitor → RECOVERY_WEBHOOK_URL при падении MLX/Ollama. |

### 3.3 Дефибриллятор и восстановление

| Компонент             | Ожидание                                            | Статус проверки                         | Связи                                                                           |
| --------------------- | --------------------------------------------------- | --------------------------------------- | ------------------------------------------------------------------------------- |
| **Recovery listener** | Порт 9099, POST /recover → system_auto_recovery.sh. | ✅ Порт 9099 занят (слушатель запущен). | Оркестратор шлёт webhook при недоступности MLX/Ollama.                          |
| **OLLAMA_KEEP_ALIVE** | -1 в .env (модель не выгружается).                  | ✅ В проверке: OLLAMA_KEEP_ALIVE=-1.    | Стабильная работа victoria-wisdom-30b в Ollama.                                 |
| **MLX LaunchAgent**   | com.atra.mlx-api-server.plist.                      | ✅ Найден (verify script).              | Автоперезапуск wrapper при падении; монитор mlx-monitor — проверка каждые 30 с. |

### 3.4 Интерфейсы

| Компонент              | Ожидание                                                  | Статус проверки                          | Связи                                                                                   |
| ---------------------- | --------------------------------------------------------- | ---------------------------------------- | --------------------------------------------------------------------------------------- |
| **Open WebUI**         | Порт 3005, модели от Ollama, Victoria/Enhanced по ссылке. | ✅ Up healthy.                           | OLLAMA_BASE_URL=host.docker.internal:11434; OPENAI_API_BASE_URL=victoria-agent:8000/v1. |
| **Frontend (Web IDE)** | Порт 3000.                                                | В списке Docker (atra-web-ide-frontend). | Backend 8080.                                                                           |

### 3.5 API экспертов

| Компонент            | Ожидание                      | Статус проверки                                                                                                          | Связи                                             |
| -------------------- | ----------------------------- | ------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------- |
| **GET /api/experts** | Список экспертов из БД (86+). | ⚠️ Зависит от доступности бэкенда к knowledge_postgres (сеть atra-network). При недоступности БД — fallback 9 экспертов. | Backend → KnowledgeOSClient → PostgreSQL experts. |

**Рекомендация:** убедиться, что бэкенд и knowledge_postgres в одной сети (atra-network); при запуске только docker-compose корня — поднять также knowledge_os (или общую сеть).

---

## 4. Сводная схема связей

```
Пользователь / Cursor
    │
    ├─ /expert → team.md, .cursor/rules, TEAM_PERSONALITIES, MASTER_REFERENCE, COGNITIVE_CODE, (GET /api/experts)
    ├─ /brainstorm → скилл: вопросы по одному, 2–3 подхода, дизайн по секциям → docs/plans/*.md → writing-plans
    │
Frontend (3000) ──► Backend (8080) ──► Victoria (8010) ──► MLX (11435) + Ollama (11434)
                          │                    │
                          ├─ GET /api/experts ─► knowledge_postgres (experts)
                          ├─ POST /api/chat/stream, ask-victoria
                          └─ REDIS_URL, KNOWLEDGE_OS_API_URL

Open WebUI (3005) ──► Ollama (11434) для моделей; Victoria (8000/v1) для Victoria/Enhanced

Оркестратор (Docker) ──► check Ollama/MLX каждые 300 с ──► при down: POST host:9099/recover ──► host_recovery_listener ──► system_auto_recovery.sh
```

---

## 5. Критерии приёмки (из дизайна /expert и /brainstorm)

- [x] При /expert агент опирается на team.md/правила, библию, COGNITIVE_CODE/гиганты (правило expert_and_brainstorm.mdc, alwaysApply).
- [x] При /brainstorm агент не пишет код до дизайна и одобрения; вопросы по одному; подходы; дизайн в docs/plans/; затем writing-plans.
- [x] Правило expert_and_brainstorm.mdc подключено (alwaysApply).
- [ ] GET /api/experts возвращает полный список при доступной БД (проверить сеть и DATABASE_URL бэкенда при необходимости).

---

## 6. Рекомендации

1. **Эксперты в рантайме:** для полного списка 86+ экспертов бэкенд должен достучаться до knowledge_postgres (общая сеть atra-network при запуске knowledge_os и Web IDE).
2. **После перезагрузки хоста:** запустить вручную `nohup python3 scripts/host_recovery_listener.py &` (или добавить в Login Items), затем при необходимости `bash scripts/setup_mlx_autostart.sh` и `bash scripts/setup_system_auto_recovery.sh`.
3. **Проверка целостности:** раз в смену контекста или после деплоя запускать `./scripts/verify_full_recovery_readiness.sh` и при необходимости `./scripts/verify_openwebui_ollama.sh`.

---

_Связь: docs/plans/2026-02-23-expert-and-brainstorm-design.md, docs/EXPERT_CONNECTION_ARCHITECTURE.md, docs/MASTER_REFERENCE.md, .cursor/rules/expert_and_brainstorm.mdc._
