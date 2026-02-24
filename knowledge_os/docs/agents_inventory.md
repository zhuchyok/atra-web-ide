## Реестр агентных подсистем ATRA

| Агент / подсистема                                   | Назначение                                                                       | Основные подсказки / инструкции                                                                                     | Инструменты и API                                                                                                                                                             | Хранилища / память                                                                                      | Владельцы          | Примечания                                                  |
| ---------------------------------------------------- | -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- | ------------------ | ----------------------------------------------------------- |
| `signal_live` (генератор сигналов)                   | Формирование торговых сигналов 1h, анализ индикаторов, маршрутизация уведомлений | ✅ **Промпт в `configs/agents/signal_live.yaml`** (v1.0) - системные инструкции, контекст, примеры                  | - Биржевые данные (`data_sources_manager`, `improved_price_api`, Binance REST) <br> - AI оптимизаторы (TP/SL, volume/volatility) <br> - Correlation manager, MTF confirmation | - Временная память сессии (df, risk history) <br> - БД `trading.db` (`signals_log`, `accepted_signals`) | Тим лид сигналинга | ✅ Промпт централизован, загружается через `prompt_manager` |
| `auto_execution`                                     | Автооткрытие позиций, постановка SL/TP, логирование                              | ✅ **Промпт в `configs/agents/auto_execution.yaml`** (v1.0) - системные инструкции, правила безопасности, примеры   | - Bitget через `exchange_adapter` <br> - Order audit, acceptance DB                                                                                                           | - `trading.db` (`active_positions`) <br> - `order_audit_log`                                            | Торговая команда   | ✅ Промпт централизован, включает правила auto-fix          |
| `scripts/run_risk_monitor.py`                        | Мониторинг защитных ордеров, автофиксер SL/TP, Prometheus-метрики                | ✅ **Промпт в `configs/agents/risk_monitor.yaml`** (v1.0) - системные инструкции, правила мониторинга, пороги риска | - Bitget API (plan/currentPlan/historyPlan) <br> - Prometheus файлы <br> - Telegram alerts                                                                                    | - `order_audit_log` (логирование plan SL/TP) <br> - `metrics/*.prom`                                    | Риск-отдел         | ✅ Промпт централизован, включает Think/Act/Observe логику  |
| `alert_notifications` / Telegram боты                | Алерты об ошибках исполнения, статусах, manual HITL                              | Текстовые шаблоны в Python, без LM                                                                                  | - Telegram Bot API                                                                                                                                                            | - Логи `system.log`, таблица `alerts` (при наличии)                                                     | Support            | Кандидат на интеграцию HITL фидбека (кнопки «верно/ошибка») |
| `monitoring_system` / `price_monitor_system`         | Здоровье инфраструктуры, сбор данных, напоминания                                | Не использует LM, процедурная логика                                                                                | - Prometheus / Grafana <br> - Вспомогательные API                                                                                                                             | - Логи мониторинга                                                                                      | DevOps             | Прописать владельцев и регламент обновлений                 |
| Backtesting (`backtrader_adapter`, `forward_tester`) | Оценка стратегий                                                                 | Нет подсказок, чисто процедурный код                                                                                | - Historical OHLC (Binance/архивы)                                                                                                                                            | - JSON файловые отчёты, `tests/`                                                                        | Quant team         | Требуется включить в стандарт Agent Ops для симуляций       |
| `ai_*` (AI оптимизаторы)                             | TP/SL, position sizing, фильтры                                                  | Промпты в Python (Gemini, etc.)                                                                                     | - Gemini API (через ai_integration)                                                                                                                                           | - `ai_*_data` каталоги, JSON                                                                            | AI команда         | Нужно вынести подсказки в централизованный каталог          |

### Что отсутствует и требует фиксации

1. ✅ **Системные инструкции и подсказки** - **ВЫПОЛНЕНО**: вынесены в `configs/agents/<agent>.yaml`
2. **Память / lessons learned** хранится разрозненно (SQLite, JSON). Нет единого слоя.
3. **Владельцы и контакты** — требуется подтверждение и публикация в Confluence/Notion.
4. ✅ Нет централизованного описания разрешений и API-доступов для агентов - **ЧАСТИЧНО**: есть `agent_identity.json`
5. Для многих процедурных сервисов стоит описать, как они станут агентами (добавить слой рассуждений).

### Следующие шаги

1. Подтвердить владельцев и актуализировать поля таблицы.
2. ✅ Вынести подсказки/промпты в `configs/agents/<agent>.yaml` - **ВЫПОЛНЕНО**
3. Определить, какие подсистемы переводим в полноценные агенты (какие добавляют LM).
4. ✅ Подготовить шаблон Think/Act/Observe для каждой строки - **ВЫПОЛНЕНО**: промпты включают Think/Act/Observe логику

## Наблюдаемость

- Введён единый трейс-лог `logs/agent_traces.log`, записи пишутся через `observability.tracing.get_tracer()`.
- Инструментированы ключевые агенты (`signal_live`, `auto_execution`, `run_risk_monitor`) по этапам Think/Act/Observe.
- ✅ **Промпты централизованы**: `configs/agents/<agent>.yaml` - загружаются через `observability.prompt_manager`, логируются в trace (`prompt_loaded`).
- Скрипт `scripts/process_feedback.py` агрегирует события и формирует файл `observability/lessons.json` на основе трассировки и `order_audit_log`. Флаг `--apply-guidance` автоматически обновляет `configs/guidance/<agent>.json`.
- Агенты при старте подгружают guidance (top-3 урока) и промпты, фиксируют их в трейсах и логах.
- Подключён rule-based LM-Judge (`observability/lm_judge.py`), вердикты фиксируются в трейсе и отображаются в Telegram-сигнале.
- Добавлен HITL-контур: кнопки `👍/👎/🛠 Комментарий` в Telegram, feedback сохраняется в `signal_feedback` и попадает в lessons.
- Guidance автоматически выгружается в `configs/prompts/<agent>.yaml` и `docs/guidance/<agent>.md` после каждого обновления lessons.
- Контроль доступа реализован через `configs/agent_identity.json` + `observability.agent_identity`: критичные действия проверяются `authorize_agent_action(...)`, матрица прав зафиксирована в `docs/agent_identity_matrix.md`.
- Следующий шаг: расширить HITL на `auto_execution`/`risk_monitor` и вынести метрики в дашборды Prometheus.

## Agent Gym / симуляции

- Сценарии определены в `agent_gym/scenarios.py` и конфигурируются через JSON (`agent_gym/configs/*.json`).
- Запуск: `python3 scripts/run_agent_gym.py --scenarios ...` → отчёт в `agent_gym/reports/`.
- По умолчанию включены проверки по сигналам, исполнению ордеров и защите позиций за заданный период времени.
