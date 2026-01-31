# Guidance — auto_execution

_Generated at 2025-11-12T19:03:08.927160_

- **market_failed** (#168): Пересмотреть параметры лимитного исполнения, таймауты и fallback на маркет.
  - {"symbol": "FILUSDT", "side": "sell", "error": null, "created_at": "2025-11-03 19:34:04"}
  - {"symbol": "WLFIUSDT", "side": "sell", "error": null, "created_at": "2025-11-03 19:26:15"}
  - {"symbol": "BCHUSDT", "side": "sell", "error": null, "created_at": "2025-11-03 19:20:19"}
- **final_failed** (#166): Проверить ликвидность инструмента, регулировать время ожидания fill и размер позиции.
  - {"symbol": "FILUSDT", "side": "sell", "error": "Все попытки исполнения провалились", "created_at": "2025-11-03 19:34:04"}
  - {"symbol": "WLFIUSDT", "side": "sell", "error": "Все попытки исполнения провалились", "created_at": "2025-11-03 19:26:15"}
  - {"symbol": "BCHUSDT", "side": "sell", "error": "Все попытки исполнения провалились", "created_at": "2025-11-03 19:20:19"}
- **limit_timeout** (#56): Проверить ликвидность инструмента, регулировать время ожидания fill и размер позиции.
  - {"symbol": "PUMPUSDT", "side": "sell", "error": null, "created_at": "2025-11-08 22:01:25"}
  - {"symbol": "MMTUSDT", "side": "sell", "error": null, "created_at": "2025-11-08 16:41:08"}
  - {"symbol": "MMTUSDT", "side": "sell", "error": null, "created_at": "2025-11-08 15:07:46"}
- **auto_plan_tp_failed** (#10): Проверить плановые ордера Bitget, логи auto-fix, сопоставить с expected_targets.
  - {"symbol": "ASTERUSDT", "side": "sell", "error": "auto_fix_tp_failed", "created_at": "2025-11-12 14:04:36"}
  - {"symbol": "CFXUSDT", "side": "sell", "error": "auto_fix_tp_failed", "created_at": "2025-11-12 14:04:35"}
  - {"symbol": "BNBUSDT", "side": "sell", "error": "auto_fix_tp_failed", "created_at": "2025-11-12 14:04:34"}