- `risk_flags` активируются автоматически (`run_risk_monitor.py`); перед запуском live важно убедиться, что `emergency_stop` и `weak_setup_stop` сброшены.
---
## 1. Сводка
- На 10 ноября 2025 г. live-сигналы всё ещё отсутствуют (`signals_log` не содержит записей `trade_mode = 'live'`).  
- Пользователь `958930260` пополнен до `5000 USDT`, оставлен в `trade_mode = "spot"`, `filter_mode = "strict"`, `risk_pct = 2`.  
- Пользователь `556251171` удерживается в `trade_mode = "futures"` и `filter_mode = "soft"` (для short-наборов) с обновлённым депозитом `2000.0 USDT` (баланс синхронизирован с БД; позиционный лимит 15 % теперь = 300 USDT).  
- `risk_flags` (`emergency_stop`, `maxdd_warning`, `weak_setup_stop`) вручную сброшены 10 ноября 2025 (скрипт `manage_risk_flag.py`).  
- Основная система запускается через `main.py` (lock-файл `atra.lock`, единый процесс), standalone-запуск `signal_live.py` отключён; lazy-импорты устранены → предупреждения о циклическом импорте `send_signal` больше не возникают.  
- Для soft-пользователей (сейчас это `556251171`) direction-confidence разрешает 2/4 подтверждения вместо 3/4, чтобы при EMA+RSI проходили сетапы с пограничным MACD; strict остаётся при пороге 3/4.  
- Текущий запуск `main.py` выполняется из `.venv`; лог фиксирует фильтрацию сигналов (пример: ETHUSDT), но direction confidence по-прежнему блокирует первые сетапы.

## 2. Статус пользователей (из `users_data`)
| user_id | deposit (USDT) | free_deposit | trade_mode | filter_mode | leverage | setup_step |
| --- | --- | --- | --- | --- | --- | --- |
| 556251171 | 2000.0 | 2000.0 | futures | soft | 7 | completed |
| 958930260 | 5000.0 | 5000.0 | spot | strict | 1 | completed |

> SQL / JSON:  
> `SELECT user_id, data FROM users_data;`  
> `user_id=958930260` → `{"deposit": 0.0, ... "setup_step": "deposit"}`.

## 3. Журнал сигналов (`signals_log`)
- Последние 20 записей: всё ещё `user_id = backfill_patterns`, `trade_mode = backfill`, `entry_amount_usd = 1000` (пока без live).  
- Количество live-записей: `0`.  
- Последний live-сигнал отсутствует (`SELECT ... WHERE trade_mode='live'` → `None`).

## 4. События адаптивного сайзинга (`position_sizing_events`)
- После обновления депозитов новые события должны перестать возвращать `final_amount_usd = 0`; требуется контроль следующего окна (см. чек-лист).

## 5. Блокирующие проблемы
1. **Live-сигналы по-прежнему отсутствуют** → `signals_stalled = 1` (обновлено `run_risk_monitor.py`).  
2. **Основной пользователь `556251171` остаётся в `futures/soft`**; фьючерсные метрики исторически отрицательные (Sharpe −6.47), требуется подтверждение live-серии перед масштабированием.  
3. **`PortfolioRiskManager` блокировал первые сигналы как `POSITION_SIZE_TOO_LARGE`** — устранено обновлением депозита до 2000 USDT; мониторим следующие события.  
4. **`signals_log` содержит только backfill** → KPI и ежедневные отчёты отражают synthetic-данные.

## 6. Рекомендуемые действия (контрольный чек-лист)
1. ✅ **Пополнить депозит `958930260`** — выполнено (5000 USDT, spot/strict).  
2. ✅ **Переключить `556251171` в spot-режим** — временно выполнено; 10 ноября возвращён `futures/soft` по запросу трейдера (для поддержки short-сетапов).  
3. ✅ **Сбросить risk_flags и перезапустить пайплайн** — выполнено (`manage_risk_flag.py --clear`, `python main.py`).  
4. ✅ **Перегрузить PortfolioRiskManager** — состояние теперь хранится per-user; drawdown/дневные лимиты не наследуются между `spot` и `futures` контурами (блокировки `MAX_DRAWDOWN_EXCEEDED` исчезли после рестарта 18:52 UTC).  
5. ⏳ **Отследить появление первой live-записи** — мониторить `signals_log` и Telegram (ожидаемые пользователи: `556251171`, `958930260`); после обновления депозита и ликвидностных фильтров ожидаем появление soft short/long сетапов.  
6. ⏳ **Проверить adaptive sizing** после первых live-событий (`scripts/analyze_position_sizing.py --hours 24`).  
7. ⏳ **Контроль метрик**: `daily_quality_report` уже пишет `sources_metrics`; нужно дополнить отчёт проверкой наличия live-записей.  
8. ⏳ **Алёрты**: сформировать оповещение при `>24h` без live или >10 событий `final_amount_usd = 0`.

## 7. Использованные запросы/скрипты
- `SELECT user_id, data FROM users_data;`
- `SELECT ... FROM signals_log ORDER BY datetime(entry_time) DESC LIMIT 20;`
- `SELECT ... FROM position_sizing_events ORDER BY datetime(created_at) DESC LIMIT 20;`
- `SELECT COUNT(*) FROM signals_log WHERE trade_mode = 'live';`
- Bash: `scripts/run_daily_quality_report.sh` (с экспортом `performance_live_vs_backfill.json`).

## 8. Следующий контроль
- Следующий контроль: через 24 часа убедиться, что `signals_log` содержит ≥1 live-событие, `position_sizing_events` перестали возвращать `WEAK_SETUP`.  
- Зафиксировать первую live-запись (символ, пользователи) и добавить в журнал, обновить чек-лист (отметить п.4–6).

---

