# Передача контекста в новый чат Cursor (24.02.2026)

**Зачем:** текущий чат заполнился; чтобы продолжить без потери логики — открой новый чат и используй этот документ.

---

## Текущее состояние системы (Эра Мудрости)

- **Victoria Agent:** Мозг (MLX, порт 11435) + Руки (Ollama, **victoria-wisdom-v3.5**). Оба уровня активны. Актуальное состояние — docs/MASTER_REFERENCE.md (Wisdom Era Status).
- **Дефибриллятор:** `scripts/host_recovery_listener.py` слушает порт 9099; при POST /recover запускает `scripts/system_auto_recovery.sh` (в т.ч. поднимает MLX). Запускать вручную: `nohup python3 scripts/host_recovery_listener.py &`
- **Совет Директоров:** Последняя директива — 21.02 20:32; два дня тишины. Причина: застрявшие сессии дебатов (HAN, active), последняя запись ушла в обсуждение орфографии. Нужно: закрыть висящие strategy_sessions, запустить новый run_board_meeting.
- **Проверка восстановления:** `./scripts/verify_full_recovery_readiness.sh`

---

## Что делать в новом чате

1. **Прочитай этот файл:** `@docs/SESSION_HANDOFF_2026_02_24.md`
2. **Прочитай библию:** `@docs/MASTER_REFERENCE.md` (актуальное состояние проекта).
3. **Продолжить по Совету Директоров:** «Реанимировать Совет Директоров: закрыть висящие strategy_sessions (active), запустить board-scheduler или run_board_meeting, сформировать новую стратегическую директиву Эры Мудрости. Использовать экспертов и знания гигантов.»
4. **Экономия токенов:** задачи по возможности ставить Виктории (AuditAgent, Expert Council, Victoria API), не дублировать анализ в чате.

---

## Ключевые файлы

| Назначение                               | Путь                                                                         |
| ---------------------------------------- | ---------------------------------------------------------------------------- |
| Автовосстановление                       | `scripts/system_auto_recovery.sh`                                            |
| Проверка готовности к перезагрузке       | `scripts/verify_full_recovery_readiness.sh`                                  |
| Слушатель восстановления (дефибриллятор) | `scripts/host_recovery_listener.py`                                          |
| Запуск MLX (мозг)                        | `scripts/start_mlx_api_server.sh`                                            |
| Совет экспертов                          | `knowledge_os/app/expert_council_discussion.py`                              |
| Совет директоров / доска                 | `knowledge_os/app/strategic_board.py`, `knowledge_os/app/board_scheduler.py` |

---

## Выполнено в этой сессии (24.02.2026)

- Закрыты висящие strategy_sessions (170 шт.).
- Запущен один прогон Совета Директоров (run_board_meeting) — директива пишется в board_decisions и на дашборд.
- RECOVERY_WEBHOOK_URL проверен: задан в docker-compose для knowledge_os_orchestrator, enhanced_orchestrator вызывает trigger_recovery_webhook при недоступности MLX/Ollama.
- Обновлены MASTER_REFERENCE и CHANGES_FROM_OTHER_CHATS (§0.5b).

## Открытые задачи (на следующий чат при необходимости)

- Проверить на дашборде (8501 → Стратегия) появление новой директивы после завершения фонового run_board_meeting.
- Держать host_recovery_listener запущенным после перезагрузки (или добавить в Login Items / launchd с разрешениями).
