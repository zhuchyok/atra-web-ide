# Выявленные проблемы и решения с привлечением экспертов

**Назначение:** сводка проблем (оркестратор 137, Ollama/MLX, тесты), рекомендации экспертов и статус решений. При появлении новых проблем — дополнять таблицу и § «Что делать дальше».

**Обновлено:** 2026-02-08

---

## 1. Сводка по проблемам и экспертам

| № | Проблема | Эксперты | Статус | Решение / где смотреть |
|---|----------|----------|--------|------------------------|
| 1 | **knowledge_os_orchestrator** уходит в Restarting (exit 137, OOM) | Игорь (Backend), Елена (SRE) | Решено | Проверка Ollama/MLX в начале цикла; при недоступном Ollama **не вызывать** update_all_agents_knowledge; лёгкий импорт (semantic_cache.get_embedding). При повторном OOM — увеличить память Docker или лимит контейнера. См. [ORCHESTRATOR_137_AND_OLLAMA.md](ORCHESTRATOR_137_AND_OLLAMA.md), VERIFICATION_CHECKLIST §3. |
| 2 | **Ollama на хосте не отвечает** (11434), «All connection attempts failed» | Сергей (DevOps), Елена (SRE) | Решено | На хосте запустить `ollama serve` от пользователя с моделями (не `brew services` от другого пользователя). Recovery по расписанию (system_auto_recovery каждые 300 с) и host_recovery_listener (порт 9099) по webhook от оркестратора. См. ORCHESTRATOR_137_AND_OLLAMA §2.1, §6. |
| 3 | **MLX возвращает 404** с контейнера (GET host.docker.internal:11435) | Дмитрий (ML), Сергей (DevOps) | Документировано | Сеть до хоста есть (ответ 404, не connection refused). 404 = эндпоинт или конфиг MLX: проверять путь (/v1/models или /api/tags), что MLX API Server запущен и слушает 11435. Оркестратор проверяет оба пути в check_llm_services_health. См. VERIFICATION_CHECKLIST §3 (MLX). |
| 4 | **Оркестратор не следил за Ollama/MLX и не инициировал восстановление** | Елена (SRE), Виктория (координация) | Решено | В начале цикла **check_llm_services_health()**; при сбое **trigger_recovery_webhook()** (POST на RECOVERY_WEBHOOK_URL). В continuous — фоновый health monitor (ORCHESTRATOR_HEALTH_MONITOR_INTERVAL). На хосте — host_recovery_listener.py и system_auto_recovery по расписанию. См. [LIVING_ORGANISM_PREVENTION.md](LIVING_ORGANISM_PREVENTION.md), CHANGES §0.4m. |
| 5 | **Остановленные контейнеры (orchestrator, nightly) не поднимались** | Сергей (DevOps) | Решено | В system_auto_recovery и check_and_start_containers при остановленных — **up -d** (не restart). Явная проверка и подъём knowledge_nightly и knowledge_os_orchestrator. См. CHANGES §0.4k, LIVING_ORGANISM_PREVENTION §1. |
| 6 | **Тесты Knowledge OS падают** (service_monitor API, LinkType, Redis/БД/Victoria) | Анна (QA), Игорь (Backend) | Частично решено | ServiceMonitor: добавлен **is_running()** (контракт с тестами). test_load: импорт **LinkType, uuid**. test_service_monitor: доступ к services как к dict (по имени). Интеграционные тесты (Redis, БД, Victoria) требуют поднятой инфраструктуры или CI. См. CHANGES §0.4z. |
| 7 | **Задачи не создаются, обучение не идёт** (следствие 1–5) | Роман (БД), Елена (SRE) | Решено | Устранение причин 1–5; чеклист §5 «Чтобы в будущем не повторялось» и runbook LIVING_ORGANISM_PREVENTION. При новом сбое — раздел 3 чеклиста и runbook §3. |

---

## 2. Рекомендации экспертов (кратко)

- **Игорь (Backend):** один пул БД, один HTTP-клиент; lifespan вместо on_event; после правок — pytest по затронутым модулям; при изменениях в оркестраторе не убирать check_llm_services_health и не вызывать update_all_agents_knowledge при недоступном Ollama.
- **Сергей (DevOps):** порядок запуска (сначала knowledge_os compose, затем Web IDE); up -d для остановленных контейнеров; на хосте — host_recovery_listener и ollama serve от нужного пользователя.
- **Елена (SRE):** recovery по расписанию (setup_system_auto_recovery.sh); мониторинг deferred_to_human и метрик; при 137 — docker events (container oom), увеличение памяти или лимита контейнера.
- **Дмитрий (ML):** Ollama/MLX — URL из env; при 404 MLX проверять эндпоинт и запуск MLX API Server; снижать MLX_MAX_CONCURRENT при Metal OOM.
- **Роман (БД):** один пул на процесс; миграции в db/migrations/; при изменениях схемы проверять оркестратор, воркер, дашборд.
- **Анна (QA):** тесты ожидают 401 без токена; после правок — прогон тестов; интеграционные тесты в CI или при поднятой инфраструктуре.

---

## 3. Что сделано в этой итерации (2026-02-08)

1. **ServiceMonitor:** добавлен метод **is_running()** для соответствия тестам и контракту с FileWatcher/другими мониторами.
2. **test_load.py:** добавлены импорты **LinkType** и **uuid** (исправление NameError).
3. **test_service_monitor.py:** проверка сервиса по имени в dict — `monitor.services["test_service"]` вместо `monitor.services[0]`.
4. **enhanced_orchestrator.py:** в trigger_recovery_webhook заменён **datetime.utcnow()** на **datetime.now(timezone.utc)** (чеклист §5, мировые практики).
5. **Документ:** создан PROBLEMS_AND_EXPERT_SOLUTIONS.md (этот файл) — единая точка для проблем и решений с привязкой к экспертам.

---

## 4. Что делать дальше

- **При повторном 137:** проверить `docker events` (container oom); убедиться, что Ollama доступен на хосте; при необходимости задать лимит памяти контейнеру в docker-compose (deploy.resources.limits.memory).
- **При падении тестов в CI:** убедиться, что в workflow учтены зависимости (Redis, PostgreSQL для интеграционных тестов) или тесты помечены как требующие инфраструктуры; исправить API-дрейф (как с ServiceMonitor.is_running()).
- **При новом типе сбоя:** зафиксировать в VERIFICATION_CHECKLIST_OPTIMIZATIONS §3 (причина + решение) и при необходимости в §5; обновить этот документ (таблица §1).

---

## 5. Ссылки

- [ORCHESTRATOR_137_AND_OLLAMA.md](ORCHESTRATOR_137_AND_OLLAMA.md) — 137, Ollama, живой организм
- [LIVING_ORGANISM_PREVENTION.md](LIVING_ORGANISM_PREVENTION.md) — runbook, что проверять
- [VERIFICATION_CHECKLIST_OPTIMIZATIONS.md](VERIFICATION_CHECKLIST_OPTIMIZATIONS.md) — §3 причины сбоев, §5 при следующих изменениях
- [CHANGES_FROM_OTHER_CHATS.md](CHANGES_FROM_OTHER_CHATS.md) — §0.4k, §0.4l, §0.4m, §0.4z
- [configs/experts/team.md](../configs/experts/team.md) — команда и роли
