# Инвентаризация возможностей Виктории (по чату)

**Дата:** 2026-03-05  
**Цель:** Проверить, что всё, что делали в чатах (автономия, самообучение, знания гигантов, Initiative, Recovery, OTEL, проекты, Git-порядок), по-прежнему есть в коде и при необходимости включено после обновления Victoria.

---

## 1. Техническая инвентаризация (System Domain)

| Что                                    | Статус                                                                                                                                                       | Где                                                                                                                                                                                                        |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Домен **System** в БД                  | ✅ Код есть                                                                                                                                                  | `knowledge_os/scripts/full_init.py` — создаёт домены System, Management при инициализации. **Не** выполняется автоматически при каждом старте; запуск вручную: `python knowledge_os/scripts/full_init.py`. |
| «Виктория агент делала» инвентаризацию | ⚠️ Отдельного «технического инвентаризационного» скилла/задачи в коде нет. Домен System создаётся скриптом; наполнение узлами — по мере миграций и скриптов. |

**Рекомендация:** Если нужна регулярная техническая инвентаризация (сканирование сервисов/портов/проектов в отчёт), оформить как отдельную задачу куратора или скрипт и писать результаты в knowledge_nodes (домен System) или в отчёт.

---

## 2. Автоподхват проектов и контекст «перейди в проект X»

| Что                                      | Статус                   | Где                                                                                                                                                                                                                                                             |
| ---------------------------------------- | ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Реестр проектов из БД + **dev/**         | ✅ Работает              | `src/agents/bridge/project_registry.py`: загрузка из таблицы `projects`, fallback на `DEFAULT_PROJECT_CONFIGS` (atra-web-ide, atra, setki-21). **Сканирование `/workspace/dev`** — подпапки добавляются в реестр как проекты (без перезагрузки; кэш TTL 300 с). |
| Валидация **project_context** в Victoria | ✅ Работает              | `victoria_server.py`: при запросе вызывается `get_projects_registry()`, `project_context` проверяется по `allowed_list`; при неверном — подставляется `main_project`.                                                                                           |
| «Перейди в проект X» в фразах            | ⚠️ Детекции по фразе нет | Определение контекста проекта идёт по полю запроса `project_context`, а не по разбору фразы «перейди в проект setki-21». Клиент (frontend, MCP, Telegram) должен передавать `project_context` явно.                                                             |

**Итог:** Новые проекты в `dev/` подхватываются реестром при следующем запросе (после TTL). Явная передача `project_context` в API обязательна.

---

## 3. Единый API для Сетки 21 (moskit-api)

| Что                                        | Статус                | Где                                                                                                                                                                                                                  |
| ------------------------------------------ | --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| moskit-api, SEO, микроразметка, robots.txt | 📁 Другой репозиторий | Проект setki-21 и moskit-api — в своих репозиториях (не в atra-web-ide). В этом репо только: реестр проектов с slug `setki-21`, workspace `/workspace/dev/setki-21`, передача `project_context=setki-21` в Victoria. |

**Итог:** Функциональность Сетки 21 и SEO не «пропала» — она в репо setki-21/moskit. Victoria может работать с контекстом `setki-21`, если передан в запросе.

---

## 4. Проактивность (Initiative): Event Bus, File Watcher, Service Monitor, RAG preload

| Что                             | Статус                   | Где                                                                                                                                                                                                                                             |
| ------------------------------- | ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **ENABLE_EVENT_MONITORING**     | ✅ По умолчанию **true** | `knowledge_os/docker-compose.yml` (victoria-agent): `ENABLE_EVENT_MONITORING: ${ENABLE_EVENT_MONITORING:-true}`. При true в `victoria_enhanced.start()` запускаются Event Bus, File Watcher, Service Monitor, Deadline Tracker, Skills Watcher. |
| **FILE_WATCHER_ENABLED**        | ✅ По умолчанию true     | docker-compose: `FILE_WATCHER_ENABLED:-true`.                                                                                                                                                                                                   |
| **SERVICE_MONITOR_ENABLED**     | ✅ По умолчанию true     | docker-compose: `SERVICE_MONITOR_ENABLED:-true`.                                                                                                                                                                                                |
| **RAG_PRELOAD_TYPICAL_QUERIES** | ✅ По умолчанию true     | docker-compose: `RAG_PRELOAD_TYPICAL_QUERIES:-true`. В `victoria_server.py` lifespan при старте вызывается `_preload_rag_cache()` (типовые запросы: статус, список файлов и т.д.).                                                              |

**Важно:** В CHANGES упоминался «лёгкий старт» с false из-за OOM. В **текущем** docker-compose дефолты снова **true**. Если контейнер падает по памяти — в .env задать `ENABLE_EVENT_MONITORING=false`, `SERVICE_MONITOR_ENABLED=false`, `RAG_PRELOAD_TYPICAL_QUERIES=false` (см. VICTORIA_RESTARTS_CAUSE, MAC_STUDIO_LOAD_AND_VICTORIA).

---

## 5. Трассировка (OpenTelemetry / OTEL)

| Что                               | Статус                       | Где                                                                                                                               |
| --------------------------------- | ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Код OTEL                          | ✅ Есть                      | `knowledge_os/app/observability.py`: OpenTelemetry, TracerProvider, OTLP exporter. Включение: **ENABLE_OTEL=true**.               |
| В docker-compose                  | ✅ По умолчанию **true**     | `ENABLE_OTEL: ${ENABLE_OTEL:-"true"}`, `OTLP_ENDPOINT`, `OTLP_INSECURE`.                                                          |
| Использование в Victoria Enhanced | ✅ Есть                      | `victoria_enhanced.py`: трассировка шагов (get_tracer, span).                                                                     |
| Grafana/collector                 | ⚠️ Зависит от инфраструктуры | OTLP шлёт на `OTLP_ENDPOINT` (в compose по умолчанию `http://atra-prometheus:9090` — нужен OTLP-приёмник в Prometheus/collector). |

**Итог:** Трассировка в коде включена; визуализация в Grafana возможна при настроенном приёмнике OTLP.

---

## 6. Самовосстановление (Recovery Listener, дефибриллятор)

| Что                                        | Статус              | Где                                                                                                                                                                                                                                                                                   |
| ------------------------------------------ | ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **RECOVERY_WEBHOOK_URL** в оркестраторе    | ✅ Задан            | `knowledge_os/docker-compose.yml` (orchestrator): `RECOVERY_WEBHOOK_URL: ${RECOVERY_WEBHOOK_URL:-http://host.docker.internal:9099/recover}`.                                                                                                                                          |
| Вызов webhook при падении MLX/Ollama       | ✅ В коде           | `knowledge_os/app/enhanced_orchestrator.py`: `check_llm_services_health()`, при недоступности — `trigger_recovery_webhook()`.                                                                                                                                                         |
| **Recovery Listener** на хосте (порт 9099) | ⚠️ Зависит от хоста | `scripts/host_recovery_listener.py` — слушает 9099, по POST /recover запускает `system_auto_recovery.sh`. Автозапуск: `bash scripts/setup_system_auto_recovery.sh` (LaunchAgent com.atra.recovery-listener). Если listener не запущен на Mac — webhook от контейнера не обработается. |

**Проверка:** `curl -s http://localhost:9099/recover` — ответ 200 и `{"status":"ok",...}` значит listener работает. POST с хоста: `curl -s -X POST http://localhost:9099/recover -H "Content-Type: application/json" -d '{}'` — должен вернуть `{"status":"recovery_initiated"}`.

---

## 7. Git-порядок (Too many active changes, коммиты группами)

| Что                              | Статус             | Где                                                                                                      |
| -------------------------------- | ------------------ | -------------------------------------------------------------------------------------------------------- |
| Игнорирование тяжёлых артефактов | ✅ В репо          | `.gitignore`: fused_model/, mirror/, training_data/, rust_core/gateway.log, frontend/test-results/ и др. |
| Регламент коммитов               | ✅ Документировано | `docs/CURSOR_TOO_MANY_CHANGES.md`: коммитить группами, при необходимости git stash.                      |

**Итог:** Правила и доки на месте; поведение Cursor не меняется кодом, только уменьшением числа активных изменений.

---

## 8. Знания гигантов (AI Research, COGNITIVE_CODE, самообучение)

| Что                                                            | Статус                     | Где                                                                                                                                                                                                                       |
| -------------------------------------------------------------- | -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| RAG по **AI Research** и корпоративным доменам                 | ✅ Работает                | `ai_core.py`: `_get_knowledge_context_impl` — выборка по доменам в т.ч. AI Research, victoria_tasks. Все вызовы через `run_smart_agent_async` получают блок «KNOWLEDGE CONTEXT (AI Research & Corp)».                     |
| Явный блок **AI Research** по ключевым словам                  | ✅ В Victoria Enhanced     | `victoria_enhanced.py`: `_get_ai_research_context(goal)` — при словах вроде openai, research и т.д.; домен AI Research и source external_docs_indexer.                                                                    |
| Индексация в БД                                                | ⚠️ Запуск вручную/по крону | `index_external_docs.py`, `index_cognitive_code.py` — пишут в knowledge_nodes (домен AI Research). Периодическая индексация: `scripts/setup_indexing_launchd.sh` (воскресенье 3:00).                                      |
| **Самообучение Victoria Tasks**                                | ✅ Включено и починено     | Домен `victoria_tasks` создан в БД; `_learn_from_task` в victoria_server.py пишет результат задач в этот домен; ai_core и victoria_enhanced подтягивают узлы из victoria_tasks в RAG и при планировании. См. CHANGES §40. |
| Nightly Learner, knowledge_applicator, CorporationSelfLearning | ✅ Код есть                | Соответствующие модули в knowledge_os; участие «гигантов» через уже проиндексированные узлы в БД.                                                                                                                         |

**Итог:** Знания гигантов и самообучение работают при наличии домена victoria_tasks и индексации доков в AI Research.

---

## 9. Навыки «новой Виктории» (v3.5) — всё ли осталось

| Навык                                                   | В коде / Конфиг                                                                                                      |
| ------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| ReAct, Extended Thinking, Swarm, Consensus              | ✅ victoria_enhanced, ai_core (run_smart_agent_async, collective_brainstorming, expert_council, multi_agent_debate). |
| Оркестрация, 86 экспертов, PREFER_EXPERTS_FIRST         | ✅ docker-compose, task_detector, enhanced_router, execute_assignments.                                              |
| Долгосрочная память (LTM) по user_key + project_context | ✅ LONG_TERM_MEMORY_ENABLED, long_term_memory.py, вызовы в victoria_server.                                          |
| Стратегия ответа (quick_answer / deep_analysis и т.д.)  | ✅ VICTORIA_STRATEGY_ENABLED, PLAN_REASONING_LOGIC_VICTORIA.                                                         |
| Рефлексия и пересмотр плана (ReCAP)                     | ✅ VICTORIA_REFLECTION_ENABLED, VICTORIA_MAX_PLAN_REVISIONS.                                                         |
| Локальные модели (MLX/Ollama) для диалогов экспертов    | ✅ LocalAIRouter, run_smart_agent_async → локальные модели; Expert Council / Brainstorming / Debate через ai_core.   |
| Куратор, эталоны, curator_standards                     | ✅ Скрипты куратора, runbook, эталоны в RAG.                                                                         |

**Итог:** Перечисленные навыки присутствуют в коде и конфиге; уровень «новой Виктории» не урезан.

---

## 10. Что проверить на окружении (без изменения кода)

1. **Docker:** контейнеры `victoria-agent`, `knowledge_os_orchestrator` и при необходимости остальные — `up -d`; лимит памяти Docker достаточный (см. VICTORIA_RESTARTS_CAUSE при OOM).
2. **.env (или переменные compose):** при падениях Victoria — попробовать лёгкий старт: `ENABLE_EVENT_MONITORING=false`, `RAG_PRELOAD_TYPICAL_QUERIES=false`, `SERVICE_MONITOR_ENABLED=false`.
3. **Recovery Listener на хосте:** `curl -s http://localhost:9099/recover`; при необходимости запустить `scripts/host_recovery_listener.py` или выполнить `scripts/setup_system_auto_recovery.sh`.
4. **Домен victoria_tasks:** уже создан и привязан к узлам (см. предыдущий чат); при новом инстансе — применить `knowledge_os/db/migrations/add_victoria_tasks_domain.sql`.
5. **Реестр проектов:** при добавлении проектов в БД (таблица `projects`) или в `/workspace/dev` — через до 300 с они появятся в реестре; клиенты должны передавать `project_context` в запросах к Victoria.

---

## Краткий вывод

- **Не «похерилось»:** автоподхват проектов (dev/), реестр и project_context, Initiative (Event Bus, File Watcher, Service Monitor, RAG preload), Recovery webhook в оркестраторе, OTEL, знания гигантов (RAG + AI Research), самообучение Victoria Tasks, Git-регламент и .gitignore — всё есть в коде и в конфиге; дефолты в docker-compose для Victoria — «полные» (true).
- **Зависит от окружения:** Recovery Listener на хосте (9099), лимит памяти Docker, приёмник OTLP для Grafana, индексация AI Research по расписанию.
- **В других репо:** Сетки 21, moskit-api, SEO — не в atra-web-ide; Victoria поддерживает контекст `setki-21` через project_context.
- **Техническая инвентаризация (System Domain):** домен создаётся скриптом full_init; автоматизированного «сканирования и отчёта» в коде нет — при необходимости оформить отдельной задачей/скриптом.

После обновления Виктории перечисленные возможности сохраняются; при сбоях в первую очередь проверить пункты из §10.

---

## 11. Чеклист самовосстановления MLX (проверка что всё норм)

| Шаг | Действие                          | Ожидание                                                                                                                                                                                                                                                     |
| --- | --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | Контейнер оркестратора            | `docker ps \| grep knowledge_os_orchestrator` — контейнер Up. В нём задано `RECOVERY_WEBHOOK_URL=http://host.docker.internal:9099/recover`.                                                                                                                  |
| 2   | Listener на хосте                 | `curl -s http://localhost:9099/recover` — ответ 200, JSON с `"status":"ok"`. Если connection refused — запустить `nohup python3 scripts/host_recovery_listener.py &` или выполнить `bash scripts/setup_system_auto_recovery.sh` (п. 4 — Recovery Listener).  |
| 3   | LaunchAgent listener (автозапуск) | `launchctl list \| grep recovery-listener` — строка с com.atra.recovery-listener. Если нет — `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.atra.recovery-listener.plist` (после setup_system_auto_recovery.sh).                               |
| 4   | Ручной вызов восстановления       | `curl -s -X POST http://localhost:9099/recover -H "Content-Type: application/json" -d '{}'` — ответ `{"status":"recovery_initiated"}`. В логе `~/Library/Logs/atra-recovery-listener.log` — запись о запуске system_auto_recovery.sh.                        |
| 5   | Скрипт восстановления и MLX       | В `scripts/system_auto_recovery.sh` блок [5/10] проверяет MLX на 11435 и при необходимости запускает через launchd или `scripts/start_mlx_api_server.sh`. После POST на /recover через 1–2 мин MLX должен отвечать: `curl -s http://localhost:11435/health`. |

**Итог:** Оркестратор раз в 300 с проверяет Ollama/MLX; при недоступности шлёт POST на host:9099/recover. Listener запускает system_auto_recovery.sh → поднимается Docker, MLX, при необходимости Ollama. Цепочка исправна, если пройдены шаги 1–5.
