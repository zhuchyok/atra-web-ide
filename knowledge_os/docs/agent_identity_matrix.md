## Матрица идентичностей агентов

| Агент            | Описание                                           | Владелец        | Ключевые разрешения                                     | Секреты (env)                                               | Rate limits                     |
| ---------------- | -------------------------------------------------- | --------------- | ------------------------------------------------------- | ----------------------------------------------------------- | -------------------------------- |
| `signal_live`    | Генерация торговых сигналов и отправка Telegram    | Signal Team     | `telegram:send`, `db:read.signals`, `db:write.signals`, `guidance:read`, `observability:trace` | `TELEGRAM_TOKEN`, `TELEGRAM_TOKEN_DEV`, `TELEGRAM_CHAT_IDS` | `telegram:send` — 30/min         |
| `auto_execution` | Автоисполнение ордеров Bitget, постановка SL/TP    | Execution Team  | `exchange:trade`, `db:read.acceptance`, `db:write.positions`, `guidance:read`, `observability:trace` | `BITGET_API_KEY`, `BITGET_API_SECRET`, `BITGET_API_PASSPHRASE` | `exchange:trade` — 10/min        |
| `risk_monitor`   | Мониторинг защиты Bitget, автофикс и метрики       | Risk Team       | `exchange:read`, `telegram:send`, `db:read.positions`, `db:write.metrics`, `guidance:read`, `observability:trace` | `BITGET_API_KEY`, `BITGET_API_SECRET`, `BITGET_API_PASSPHRASE`, `TELEGRAM_TOKEN` | `exchange:read` — 60/min         |

### Хранение конфигурации
- Файл `configs/agent_identity.json` — центральный реестр разрешений, владельцев и ограничений.
- Загружается классом `observability.agent_identity.AgentIdentityRegistry`.
- При изменении файла можно вызвать `observability.refresh_registry()` для горяче[й] перезагрузки.

### Использование в коде
- Функция `authorize_agent_action(agent, permission, context)` проверяет право выполнения действия.
- Интегрировано в:
  - `signal_live.send_signal()` — контроль `telegram:send`.
  - `auto_execution.execute_and_open()` — контроль `exchange:trade` и `db:read.acceptance`.
  - `scripts/run_risk_monitor.main()` / `send_telegram_stoploss_alert()` — контроль `exchange:read`, `db:write.metrics`, `telegram:send`.
- При отсутствии разрешения выбрасывается `PermissionError`, событие логируется.

### Расширение
- Добавляйте новых агентов в `configs/agent_identity.json`.
- Разрешение `*` даёт общий доступ (не рекомендуется).
- Для чувствительных действий явно указывайте необходимые переменные окружения в `secrets`.


