# Runbook: Bitget Stop-Loss Incident (обновлено 11.11.2025)

## 1. Цель
Обеспечить быстрый анализ и восстановление защитных stop-loss ордеров на Bitget USDT-Futures в случае их отсутствия или некорректного выставления.

## 2. Симптомы инцидента
- В `logs/test_results.log` появляется запись `❌ run_risk_monitor check` или `❌ test_bitget_stop_orders`.
- Флаг `bitget_stoploss_missing` в таблице `risk_flags` активен (`value=1`).
- Telegram-уведомление: «🚨 Bitget stop-loss отсутствует ...».
- На бирже отсутствует плановый ордер типа `pos_loss` для открытой позиции.

## 3. Проверка состояния
1. Убедиться в статусе флагов:
   ```bash
   sqlite3 trading.db "SELECT * FROM risk_flags WHERE flag='bitget_stoploss_missing';"
   ```
2. Запуск проверки вручную:
   ```bash
   .venv/bin/python scripts/run_risk_monitor.py --check-bitget-stoploss
   ```
   - Если вывод `stoploss_missing=[]`, флаг сброшен.
3. Проверить лог nightly-скрипта:
   ```bash
   tail -n 50 logs/test_results.log
   ```
4. Убедиться, что nightly-скрипт исполняется (cron/CI):
   ```bash
   grep run_nightly_bitget_checks /etc/crontab
   ```
5. Проверить наличие плановых ордеров на бирже (CLI или UI):
   ```bash
   .venv/bin/python scripts/test_bitget_stop_orders.py --symbol DASHUSDT --direction SHORT --dry-run
   ```

## 4. Восстановление stop-loss
1. Определить позицию:
   ```bash
   .venv/bin/python scripts/check_positions.py --user 556251171 --exchange bitget
   ```
2. Выставить stop-loss через `ExchangeAdapter`:
   ```python
   import asyncio
   from exchange_adapter import ExchangeAdapter

   async def main():
       adapter = ExchangeAdapter("bitget", keys={...}, sandbox=False, trade_mode="futures")
       await adapter.place_stop_loss_order("DASHUSDT", "SHORT", position_amount=0.21, stop_price=70.43)

   asyncio.run(main())
   ```
3. Проверить, что плановый ордер появился (`privateMixGetV2MixOrderOrdersPlanPending`).
4. Перезапустить монитор:
   ```bash
   .venv/bin/python scripts/run_risk_monitor.py --check-bitget-stoploss
   ```

## 5. Если stop-loss не создаётся
- Проверить наличие ошибок Bitget API (коды `400172`, `40812`):
  - `400172`: уточнить `orderType` и `planType` (`pos_loss`, `orderType=market`).
  - `40812`: отсутствуют активные позиции или некорректный `planType`; убедиться в параметрах запроса.
- Проверить ключи в `user_exchange_keys`:
  ```bash
  sqlite3 trading.db "SELECT user_id, exchange_name, is_active FROM user_exchange_keys WHERE exchange_name='bitget';"
  ```
  и при необходимости `reset_bitget_keys.py`.

## 6. После инцидента
- Убедиться, что `metrics/bitget_stoploss_missing.prom` показывает `0`.
- Проверить Telegram-канал на наличие сообщения о восстановлении.
- Создать запись в `docs/incident_log.md` (если требуется).
- Обновить `docs/INFRA_HEALTH_2025Q4.md` статусом.

## 7. Контакты и эскалация
- DevOps on-call: @devops (Telegram / Slack, 24/7).
- Trading lead: @trading-lead (для подтверждения ручных закрытий).
- При повторных ошибках — открыть тикет в JIRA `INFRA-STOPLOSS`.

---
Файл поддерживается командой DevOps. Обновлять при изменениях API Bitget или логики стопов.

