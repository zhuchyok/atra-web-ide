# Предотвращение повторения: «задачи не создаются, обучение не идёт, оркестратор 137»

**Назначение:** единая точка истины — корневые причины, что сделано и что проверять, чтобы ситуация не повторялась.

---

## 1. Корневые причины (что было)

| № | Причина | Следствие |
|---|---------|-----------|
| 1 | **Остановленные контейнеры не поднимались** | В скриптах восстановления использовался `docker-compose restart`. Он **не поднимает** уже остановленные контейнеры — только перезапускает запущенные. В итоге knowledge_nightly и knowledge_os_orchestrator после остановки оставались выключенными. |
| 2 | **Нет явной проверки критичных сервисов** | В system_auto_recovery и check_and_start_containers не было явного «поднять knowledge_nightly и knowledge_os_orchestrator, если они не запущены». |
| 3 | **Ollama на хосте не запущен** | Демон Ollama (порт 11434) не работал (только ollama-mcp в процессах). Оркестратор из контейнера обращался к host.docker.internal:11434 → «All connection attempts failed». |
| 4 | **Оркестратор не следил за Ollama/MLX** | В начале каждого цикла вызывался update_all_agents_knowledge → много get_embedding к Ollama. При недоступном Ollama — таймауты и тяжёлая загрузка памяти. |
| 5 | **OOM (137) при старте оркестратора** | Тяжёлый импорт (app.main для get_embedding) + множество неуспешных запросов к Ollama при старте → выход за лимит памяти → Docker OOM Kill → exit 137. |
| 6 | **Никто не инициировал восстановление** | Оркестратор не проверял здоровье LLM и не вызывал скрипт восстановления на хосте; восстановление было только по расписанию (launchd каждые 300 с) или вручную. |

---

## 2. Что сделано (фиксы)

- **Скрипты восстановления:** при остановленных контейнерах — **up -d** (не restart). Явная проверка и подъём **knowledge_nightly** и **knowledge_os_orchestrator** по имени. См. system_auto_recovery.sh, check_and_start_containers.sh.
- **Оркестратор — «живой организм»:** в начале цикла **check_llm_services_health()** (Ollama + MLX). При недоступном Ollama **не вызывается** update_all_agents_knowledge. При сбое — **POST на RECOVERY_WEBHOOK_URL** (host_recovery_listener на порту 9099 запускает system_auto_recovery.sh). В режиме continuous — фоновый **health monitor** раз в N минут (ORCHESTRATOR_HEALTH_MONITOR_INTERVAL=300).
- **Снижение OOM:** в corporation_knowledge_system сначала импорт semantic_cache.get_embedding (легче, чем app.main). При недоступном Ollama оркестратор не нагружает себя эмбеддингами.
- **Docker-compose (knowledge_os_orchestrator):** OLLAMA_BASE_URL, MLX_API_URL, extra_hosts (host.docker.internal), RECOVERY_WEBHOOK_URL, ORCHESTRATOR_HEALTH_MONITOR_INTERVAL.
- **host_recovery_listener.py:** HTTP-сервер на хосте (9099); POST /recover → запуск system_auto_recovery.sh. После setup_system_auto_recovery рекомендуется запускать вручную или держать в фоне.
- **Документация:** VERIFICATION_CHECKLIST_OPTIMIZATIONS §3 (причина «Задачи не создаются, обучение не идёт»), §5 (пункт «Чтобы в будущем не повторялось»); ORCHESTRATOR_137_AND_OLLAMA.md; WHY_NO_LEARNING_DEBATES_HYPOTHESES_TASKS.md §0.

---

## 3. Что проверять (чтобы не повторялось)

### Перед изменениями в recovery / compose / оркестраторе

1. Открыть **VERIFICATION_CHECKLIST_OPTIMIZATIONS** §5 — пункт «Чтобы в будущем не повторялось «задачи не создаются…»» и §3 (причина «Задачи не создаются, обучение не идёт»).
2. Убедиться, что скрипты восстановления по-прежнему используют **up -d** и явно поднимают knowledge_nightly и knowledge_os_orchestrator.
3. При правках в enhanced_orchestrator: не убирать проверку Ollama/MLX в начале цикла и не вызывать update_all_agents_knowledge при недоступном Ollama; сохранять вызов trigger_recovery_webhook и health_monitor_loop в continuous.

### После изменений

1. Запустить **scripts/verify_mac_studio_self_recovery.sh** — проверка контейнеров, Ollama, MLX, listener.
2. Проверить launchd: `launchctl list | grep -E "auto-recovery|mlx-monitor"`.
3. Если используется webhook: на хосте должен быть запущен **host_recovery_listener** (порт 9099); после setup_system_auto_recovery об этом напоминает вывод скрипта.

### При новом сбое «задачи не создаются» или «оркестратор 137»

1. **Контейнеры:** `docker ps -a` — knowledge_nightly и knowledge_os_orchestrator в статусе Up? Если Exited — запустить `docker compose -f knowledge_os/docker-compose.yml up -d` и проверить скрипты (up -d, явный подъём).
2. **Ollama:** `curl -s http://localhost:11434/api/tags` — отвечает? Если нет — `ollama serve` от пользователя с моделями (не brew services от другого пользователя). См. ORCHESTRATOR_137_AND_OLLAMA §2.1.
3. **137:** `docker events` — искать container oom → die exitCode=137. См. ORCHESTRATOR_137_AND_OLLAMA §1, §3. Убедиться, что оркестратор при недоступном Ollama не вызывает update_all_agents_knowledge.
4. **Recovery:** выполнить вручную `bash scripts/system_auto_recovery.sh`; при необходимости запустить `python3 scripts/host_recovery_listener.py`.

---

## 4. Ссылки

- [ORCHESTRATOR_137_AND_OLLAMA.md](ORCHESTRATOR_137_AND_OLLAMA.md) — 137, Ollama, живой организм, что делать на хосте.
- [WHY_NO_LEARNING_DEBATES_HYPOTHESES_TASKS.md](WHY_NO_LEARNING_DEBATES_HYPOTHESES_TASKS.md) — почему задачи/обучение не шли (§0).
- [VERIFICATION_CHECKLIST_OPTIMIZATIONS.md](VERIFICATION_CHECKLIST_OPTIMIZATIONS.md) — §3 (причины сбоев), §5 (при следующих изменениях).
- [CHANGES_FROM_OTHER_CHATS.md](CHANGES_FROM_OTHER_CHATS.md) — §0.4k, §0.4l, §0.4m.
