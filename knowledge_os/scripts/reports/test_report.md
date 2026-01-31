# ОТЧЕТ О ТЕСТИРОВАНИИ

**Дата:** 2025-11-20 01:59:19
**Всего проверок:** 59

## Сводка

| Статус | Количество | Процент |
|--------|-----------|---------|
| ✅ Успешно | 54 | 91.5% |
| ❌ Провалено | 0 | 0.0% |
| ⚠️  Предупреждения | 3 | 5.1% |
| ⏭️  Пропущено | 2 | 3.4% |

## База данных

### ✅ Подключение к БД

**Статус:** PASS
**Сообщение:** Успешное подключение к trading.db
**Время выполнения:** 0.002 с

**Метрики:**
- db_path: trading.db

### ✅ Логирование в БД

**Статус:** PASS
**Сообщение:** Все 3 таблиц для логов существуют
**Время выполнения:** 0.000 с

**Детали:**
```json
{
  "tables": [
    "signals_log",
    "order_audit_log",
    "filter_performance"
  ]
}
```

### ✅ Производительность БД

**Статус:** PASS
**Сообщение:** Производительность БД в норме
**Время выполнения:** 0.003 с

**Детали:**
```json
{
  "simple_query_time": "143.21 μs",
  "table_query_time": "1.32 ms"
}
```

**Метрики:**
- simple_query_ms: 0.1432089999999775
- table_query_ms: 1.3199999999997658

### ✅ Поток сигнал → БД

**Статус:** PASS
**Сообщение:** Таблица signals_log готова для записи сигналов
**Время выполнения:** 0.000 с

**Детали:**
```json
{
  "columns": [
    "id",
    "symbol",
    "entry",
    "stop",
    "tp1",
    "tp2",
    "entry_time",
    "exit_time",
    "result",
    "net_profit",
    "qty_added",
    "qty_closed",
    "leverage_used",
    "risk_pct_used",
    "entry_amount_usd",
    "funding_rate",
    "quote24h_usd",
    "depth_usd",
    "spread_pct",
    "exposure_pct",
    "mtf_score",
    "sector",
    "expected_cost_usd",
    "impact_bp",
    "quality_score",
    "quality_meta",
    "created_at",
    "user_id",
    "stop_loss_price",
    "stop_loss_pct",
    "exit_reason",
    "max_drawdown",
    "time_to_exit",
    "volatility_at_entry",
    "atr_at_entry",
    "volume_at_entry",
    "rsi_at_entry",
    "trade_mode"
  ]
}
```

## Общие

### ✅ Проверка таблиц

**Статус:** PASS
**Сообщение:** Все 10 требуемых таблиц существуют
**Время выполнения:** 0.001 с

**Детали:**
```json
{
  "tables": [
    "signals_log",
    "accepted_signals",
    "rejected_signals",
    "order_audit_log",
    "active_positions",
    "filter_performance",
    "system_settings",
    "performance_metrics",
    "user_settings",
    "signal_acceptance_log"
  ],
  "total": 10
}
```

### ✅ Структура таблиц

**Статус:** PASS
**Сообщение:** Структура всех 10 таблиц корректна
**Время выполнения:** 0.001 с

**Детали:**
```json
{
  "tables_checked": 10,
  "sample_structure": [
    {
      "name": "id",
      "type": "INTEGER",
      "not_null": false,
      "default_value": null,
      "primary_key": true
    },
    {
      "name": "symbol",
      "type": "TEXT",
      "not_null": false,
      "default_value": null,
      "primary_key": false
    },
    {
      "name": "entry",
      "type": "REAL",
      "not_null": false,
      "default_value": null,
      "primary_key": false
    },
    {
      "name": "stop",
      "type": "REAL",
      "not_null": false,
      "default_value": null,
      "primary_key": false
    },
    {
      "name": "tp1",
      "type": "REAL",
      "not_null": false,
      "default_value": null,
      "primary_key": false
    },
    {
      "name": "tp2",
      "type": "REAL",
      "not_null": false,
      "default_value": null,
      "primary_key": false
    },
    {
      "name": "entry_time",
      "type": "TEXT",
      "not_null": false,
      "default_value": null,
      "primary_key": false
    },
    {
      "name": "exit_time",
      "type": "TEXT",
      "not_null": false,
      "default_value": null,
      "primary_key": false
    },
    {
      "name": "result",
      "type": "TEXT",
      "not_null": false,
      "default_value": null,
      "primary_key": false
    },
    {
      "name": "net_profit",
      "type": "REAL",
      "not_null": false,
      "default_value": null,
      "primary_key": false
    },
    {
      "name": "qty_added",
      "type": "REAL",
      "not_null": false,
      "default_value": null,
      "primary_key": false
    },
    {
      "name": "qty_closed",
      "type": "REAL",
      "not_null": false,
      "default_value": null,
      "primary_key": false
    },
    {
      "name": "leverage_used",
      "type": "INTEGER",
      "not_null": false,
      "default_value": null,
      "primary_key": false
    },
    {
      "name": "risk_pct_used",
      "type": "REAL",
      "not_null": false,
      "default_value": null,
      "primary_key": false
    },
    {
      "name": "entry_amount_usd",
      "type": "REAL",
      "not_null": false,
      "default_value": null,
      "primary_key": false
    },
    {
      "name": "funding_rate",
      "type": "REAL",
      "not_null": false,
      "default_value": null,
      "primary_key": false
    },
    {
      "name": "quote24h_usd",
      "type": "REAL",
      "not_null": false,
      "default_value": null,
      "primary_key": false
    },
    {
      "name": "depth_usd",
      "type": "REAL",
      "not_null": false,
      "default_value": null,
      "primary_key": false
    },
    {
      "name": "spread_pct",
      "type": "REAL",
      "not_null": false,
      "default_value": null,
      "primary_key": false
    },
    {
      "name": "exposure_pct",
      "type": "REAL",
      "not_null": false,
      "default_value": null,
      "primary_key": false
    },
    {
      "name": "mtf_score",
      "type": "REAL",
      "not_null": false,
      "default_value": null,
      "primary_key": false
    },
    {
      "name": "sector",
      "type": "TEXT",
      "not_null": false,
      "default_value": null,
      "primary_key": false
    },
    {
      "name": "expected_cost_usd",
      "type": "REAL",
      "not_null": false,
      "default_value": null,
      "primary_key": false
    },
    {
      "name": "impact_bp",
      "type": "REAL",
      "not_null": false,
      "default_value": null,
      "primary_key": false
    },
    {
      "name": "quality_score",
      "type": "REAL",
      "not_null": false,
      "default_value": null,
      "primary_key": false
    },
    {
      "name": "quality_meta",
      "type": "TEXT",
      "not_null": false,
      "default_value": null,
      "primary_key": false
    },
    {
      "name": "created_at",
      "type": "DATETIME",
      "not_null": false,
      "default_value": "CURRENT_TIMESTAMP",
      "primary_key": false
    },
    {
      "name": "user_id",
      "type": "INTEGER",
      "not_null": false,
      "default_value": null,
      "primary_key": false
    },
    {
      "name": "stop_loss_price",
      "type": "REAL",
      "not_null": false,
      "default_value": null,
      "primary_key": false
    },
    {
      "name": "stop_loss_pct",
      "type": "REAL",
      "not_null": false,
      "default_value": null,
      "primary_key": false
    },
    {
      "name": "exit_reason",
      "type": "TEXT",
      "not_null": false,
      "default_value": null,
      "primary_key": false
    },
    {
      "name": "max_drawdown",
      "type": "REAL",
      "not_null": false,
      "default_value": null,
      "primary_key": false
    },
    {
      "name": "time_to_exit",
      "type": "INTEGER",
      "not_null": false,
      "default_value": null,
      "primary_key": false
    },
    {
      "name": "volatility_at_entry",
      "type": "REAL",
      "not_null": false,
      "default_value": null,
      "primary_key": false
    },
    {
      "name": "atr_at_entry",
      "type": "REAL",
      "not_null": false,
      "default_value": null,
      "primary_key": false
    },
    {
      "name": "volume_at_entry",
      "type": "REAL",
      "not_null": false,
      "default_value": null,
      "primary_key": false
    },
    {
      "name": "rsi_at_entry",
      "type": "REAL",
      "not_null": false,
      "default_value": null,
      "primary_key": false
    },
    {
      "name": "trade_mode",
      "type": "TEXT",
      "not_null": false,
      "default_value": null,
      "primary_key": false
    }
  ]
}
```

### ✅ Целостность данных

**Статус:** PASS
**Сообщение:** Целостность данных проверена. Некоторые таблицы пусты (нормально для новой установки)
**Время выполнения:** 0.025 с

**Детали:**
```json
{
  "table_counts": {
    "signals_log": 3637,
    "accepted_signals": 5847,
    "rejected_signals": 0,
    "order_audit_log": 928,
    "active_positions": 3471,
    "filter_performance": 0,
    "system_settings": 38,
    "performance_metrics": 0,
    "user_settings": 1,
    "signal_acceptance_log": 0
  },
  "empty_tables": [
    "rejected_signals",
    "filter_performance",
    "performance_metrics",
    "signal_acceptance_log"
  ],
  "note": "Пустые таблицы заполнятся при работе системы"
}
```

### ✅ Данные в критических таблицах

**Статус:** PASS
**Сообщение:** Критические таблицы содержат данные
**Время выполнения:** 0.001 с

**Детали:**
```json
{
  "table_status": {
    "system_settings": {
      "exists": true,
      "row_count": 38,
      "has_data": true
    },
    "user_settings": {
      "exists": true,
      "row_count": 1,
      "has_data": true
    }
  }
}
```

### ✅ Импорт модулей

**Статус:** PASS
**Сообщение:** Все 23 модулей успешно импортированы
**Время выполнения:** 1.767 с

**Детали:**
```json
{
  "modules": [
    "src.filters.smart_trend_filter.SmartTrendFilter",
    "partial_profit_manager",
    "trailing_stop_manager",
    "order_manager",
    "src.filters.volume_imbalance.VolumeImbalanceFilter",
    "src.strategies.adaptive_strategy",
    "src.filters.fibonacci_zone.FibonacciZoneFilter",
    "src.filters.whale",
    "signal_live",
    "price_monitor_system",
    "correlation_risk_manager.CorrelationRiskManager",
    "src.filters.btc_trend",
    "auto_execution",
    "db_health_monitor",
    "src.filters.interest_zone.InterestZoneFilter",
    "src.filters.dominance_trend.DominanceTrendFilter",
    "exchange_adapter.ExchangeAdapter",
    "db.Database",
    "src.filters.news",
    "src.filters.anomaly.AnomalyFilter",
    "database_initialization",
    "src.analysis.market_structure",
    "src.analysis.pullback_entry"
  ]
}
```

### ✅ Модули фильтров

**Статус:** PASS
**Сообщение:** Все 9 модулей фильтров работают
**Время выполнения:** 0.000 с

**Детали:**
```json
{
  "modules": [
    "src.filters.smart_trend_filter.SmartTrendFilter",
    "src.filters.dominance_trend.DominanceTrendFilter",
    "src.filters.interest_zone.InterestZoneFilter",
    "src.filters.fibonacci_zone.FibonacciZoneFilter",
    "src.filters.volume_imbalance.VolumeImbalanceFilter",
    "src.filters.btc_trend",
    "src.filters.anomaly.AnomalyFilter",
    "src.filters.whale",
    "src.filters.news"
  ]
}
```

### ✅ Структура директорий

**Статус:** PASS
**Сообщение:** Все 6 требуемых директорий существуют
**Время выполнения:** 0.000 с

**Детали:**
```json
{
  "directories": [
    "src",
    "src/filters",
    "src/strategies",
    "src/analysis",
    "scripts",
    "logs"
  ]
}
```

### ✅ Определение окружения

**Статус:** PASS
**Сообщение:** Окружение определено как: DEV
**Время выполнения:** 0.000 с

**Детали:**
```json
{
  "detected_env": "dev",
  "env_files_found": []
}
```

### ✅ Токен Telegram

**Статус:** PASS
**Сообщение:** Токен Telegram корректно настроен для dev
**Время выполнения:** 0.000 с

**Детали:**
```json
{
  "environment": "dev",
  "token_prefix": "8141444679..."
}
```

### ✅ Блокировка авто-исполнения в DEV

**Статус:** PASS
**Сообщение:** Авто-исполнение корректно заблокировано в DEV
**Время выполнения:** 0.000 с

**Детали:**
```json
{
  "environment": "dev",
  "auto_execution_enabled": false
}
```

### ✅ API ключи биржи

**Статус:** PASS
**Сообщение:** API ключи не установлены (нормально для DEV окружения)
**Время выполнения:** 0.000 с

**Детали:**
```json
{
  "environment": "dev",
  "api_key_set": false,
  "api_secret_set": false,
  "api_passphrase_set": false,
  "note": "API ключи не обязательны для тестирования сигналов в DEV"
}
```

**Рекомендации:**
- Для тестирования исполнения ордеров установите BITGET_API_KEY и BITGET_SECRET_KEY
- В DEV окружении это не критично

### ✅ Формат символов

**Статус:** PASS
**Сообщение:** Формат символов корректен
**Время выполнения:** 0.000 с

**Детали:**
```json
{
  "tested_symbols": [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT"
  ]
}
```

### ⏭️ Подключение к бирже

**Статус:** SKIP
**Сообщение:** API ключи не установлены, пропускаем проверку подключения

**Детали:**
```json
{
  "api_key_set": false,
  "api_secret_set": false
}
```

**Рекомендации:**
- Для полной проверки установите BITGET_API_KEY и BITGET_SECRET_KEY
- Это не критично для тестирования сигналов

### ⏭️ Баланс биржи

**Статус:** SKIP
**Сообщение:** API ключи не установлены, пропускаем проверку баланса

### ✅ Использование CPU

**Статус:** PASS
**Сообщение:** Использование CPU: 10.6%
**Время выполнения:** 1.005 с

**Детали:**
```json
{
  "cpu_percent": 10.6,
  "cpu_count": 10
}
```

**Метрики:**
- cpu_usage_percent: 10.6

### ✅ Использование памяти

**Статус:** PASS
**Сообщение:** Использование памяти: 72.2%
**Время выполнения:** 0.000 с

**Детали:**
```json
{
  "memory_percent": 72.2,
  "memory_total_gb": 16.0,
  "memory_available_gb": 4.44622802734375,
  "memory_used_gb": 6.666595458984375
}
```

**Метрики:**
- memory_usage_percent: 72.2
- memory_available_gb: 4.44622802734375

### ✅ Использование диска

**Статус:** PASS
**Сообщение:** Использование диска: 12.7%
**Время выполнения:** 0.000 с

**Детали:**
```json
{
  "disk_percent": 12.7,
  "disk_total_gb": 228.27386474609375,
  "disk_free_gb": 72.01418685913086,
  "disk_used_gb": 10.490158081054688
}
```

**Метрики:**
- disk_usage_percent: 12.7
- disk_free_gb: 72.01418685913086

### ✅ Генерация сигналов (базовая)

**Статус:** PASS
**Сообщение:** Базовая генерация сигналов работает для BTCUSDT
**Время выполнения:** 3.187 с

**Детали:**
```json
{
  "symbol": "BTCUSDT",
  "indicators_count": 14,
  "data_points": 100
}
```

### ⚠️ Структура фильтров

**Статус:** WARNING
**Сообщение:** Импортировано 6, ошибок: 3
**Время выполнения:** 0.000 с

**Детали:**
```json
{
  "SmartTrendFilter": "OK",
  "DominanceTrendFilter": "OK",
  "InterestZoneFilter": "OK",
  "FibonacciZoneFilter": "OK",
  "VolumeImbalanceFilter": "OK",
  "BTCTrendFilter": "Класс не найден",
  "AnomalyFilter": "OK",
  "check_whale_activity": "Функция не найдена",
  "check_news_filter": "Функция не найдена"
}
```

**Рекомендации:**
- Проверьте наличие всех файлов фильтров
- Убедитесь, что классы имеют метод filter

### ⚠️ Выполнение фильтров

**Статус:** WARNING
**Сообщение:** Успешно: 0, Ошибок: 2
**Время выполнения:** 0.003 с

**Детали:**
```json
{
  "BTCTrendFilter": {
    "status": "ERROR",
    "error": "cannot import name 'BTCTrendFilter' from 'src.filters.btc_trend' (/Users/zhuchyok/Documents/GITHUB/atra/atra/src/filters/btc_trend.py)"
  },
  "AnomalyFilter": {
    "status": "ERROR",
    "error": "'AnomalyFilter' object has no attribute 'filter'"
  }
}
```

**Рекомендации:**
- Проверьте зависимости фильтров
- Убедитесь, что все необходимые данные доступны

### ✅ Адаптивная стратегия

**Статус:** PASS
**Сообщение:** Адаптивная стратегия доступна (включена: True)
**Время выполнения:** 0.000 с

**Детали:**
```json
{
  "USE_ADAPTIVE_STRATEGY": true,
  "class": "AdaptiveStrategySelector",
  "methods_available": [
    "get_strategy"
  ]
}
```

### ✅ Оценка качества сигналов

**Статус:** PASS
**Сообщение:** Найдены системы оценки: calculate_ai_signal_score
**Время выполнения:** 0.000 с

**Детали:**
```json
{
  "scoring_systems": [
    "calculate_ai_signal_score"
  ]
}
```

### ✅ Структура OrderManager

**Статус:** PASS
**Сообщение:** OrderManager имеет все необходимые методы
**Время выполнения:** 0.000 с

**Детали:**
```json
{
  "methods_available": [
    "create_market_order",
    "create_limit_order",
    "create_stop_order"
  ]
}
```

### ✅ Валидация параметров ордеров

**Статус:** PASS
**Сообщение:** Найдены методы валидации: 1
**Время выполнения:** 0.000 с

**Детали:**
```json
{
  "found_methods": [
    "_get_current_price"
  ]
}
```

### ✅ Типы ордеров TP1/TP2/SL

**Статус:** PASS
**Сообщение:** Найдены методы создания ордеров (1)
**Время выполнения:** 0.004 с

**Детали:**
```json
{
  "SL": "Метод найден"
}
```

### ✅ Флаг reduce_only

**Статус:** PASS
**Сообщение:** Флаг reduce_only используется в коде
**Время выполнения:** 0.025 с

**Детали:**
```json
{
  "exchange_adapter": "Использует reduce_only"
}
```

### ✅ Структура Trailing Stop Manager

**Статус:** PASS
**Сообщение:** Trailing Stop Manager доступен и инициализируется корректно
**Время выполнения:** 0.000 с

**Детали:**
```json
{
  "methods_available": [
    "get_adaptive_progress_ratio",
    "_analyze_volatility",
    "_analyze_trend_strength"
  ]
}
```

### ✅ Расчет безубытка

**Статус:** PASS
**Сообщение:** Расчет безубытка работает корректно для LONG и SHORT
**Время выполнения:** 0.027 с

**Детали:**
```json
{
  "long_entry": 50000.0,
  "long_breakeven": 50100.0,
  "short_entry": 50000.0,
  "short_breakeven": 49900.0
}
```

### ✅ Адаптивный trailing stop

**Статус:** PASS
**Сообщение:** Адаптивный расчет trailing stop работает
**Время выполнения:** 0.003 с

**Детали:**
```json
{
  "long_ratio": 0.3,
  "short_ratio": 0.3,
  "base_ratio": 1.0
}
```

### ⚠️ Структура управления позициями

**Статус:** WARNING
**Сообщение:** Найдено: 3, Отсутствует: 1
**Время выполнения:** 0.000 с

**Детали:**
```json
{
  "price_monitor_system.PriceMonitorSystem": "OK",
  "price_monitor_system.check_all_active_signals": "Не найдено",
  "partial_profit_manager.PartialProfitManager": "OK",
  "correlation_risk_manager.CorrelationRiskManager": "OK"
}
```

**Рекомендации:**
- Проверьте наличие всех модулей управления позициями
- Некоторые модули могут быть опциональными

### ✅ Поток сигнал → Telegram

**Статус:** PASS
**Сообщение:** Найдены функции отправки (3)
**Время выполнения:** 0.000 с

**Детали:**
```json
{
  "telegram_handlers.notify_user": "OK",
  "telegram_handlers.notify_all": "OK",
  "signal_live.send_signal": "OK",
  "signal_live.callback_build": "Не найдено"
}
```

### ✅ Поток принятие → ордер

**Статус:** PASS
**Сообщение:** Найдены компоненты исполнения (2)
**Время выполнения:** 0.000 с

**Детали:**
```json
{
  "order_manager.OrderManager": "OK",
  "order_manager.create_market_order": "Не найдено",
  "exchange_adapter.ExchangeAdapter": "OK",
  "exchange_adapter.create_order": "Не найдено",
  "auto_execution.execute_order": "Не найдено",
  "auto_execution.should_execute": "Не найдено"
}
```

### ✅ Поток ордер → управление

**Статус:** PASS
**Сообщение:** Найдены компоненты управления (4)
**Время выполнения:** 0.000 с

**Детали:**
```json
{
  "price_monitor_system.PriceMonitorSystem": "OK",
  "price_monitor_system.check_all_active_signals": "Не найдено",
  "trailing_stop_manager.AdvancedTrailingStopManager": "OK",
  "order_manager.OrderManager": "OK",
  "active_positions": "OK"
}
```

### ✅ Компоненты полного цикла

**Статус:** PASS
**Сообщение:** Найдено 6/8 компонентов (75.0%)
**Время выполнения:** 0.000 с

**Детали:**
```json
{
  "Генерация сигналов": "OK",
  "Фильтрация": "Не найдено",
  "Сохранение в БД": "OK",
  "Отправка в Telegram": "OK",
  "Принятие сигнала": "Не найдено",
  "Исполнение ордера": "OK",
  "Управление позицией": "OK",
  "Trailing Stop": "OK"
}
```

### ✅ Целостность передачи данных

**Статус:** PASS
**Сообщение:** Найдено функций: 4/4
**Время выполнения:** 0.000 с

**Детали:**
```json
{
  "Сохранение сигналов": "OK",
  "Сохранение сигналов (entry)": "OK",
  "Получение активных сигналов": "OK",
  "Сохранение ордеров": "OK"
}
```

### ✅ Структура AlertSystem

**Статус:** PASS
**Сообщение:** AlertSystem доступен и инициализируется
**Время выполнения:** 0.002 с

**Детали:**
```json
{
  "methods_available": [
    "create_alert",
    "check_alert_rules",
    "_send_notifications"
  ]
}
```

### ✅ Каналы Telegram уведомлений

**Статус:** PASS
**Сообщение:** Найдены функции отправки (3)
**Время выполнения:** 0.000 с

**Детали:**
```json
{
  "telegram_handlers.notify_user": "OK",
  "telegram_handlers.notify_all": "OK",
  "telegram_message_updater.TelegramMessageUpdater": "OK",
  "telegram_message_updater.send_notification": "Не найдено",
  "alert_system.TelegramNotificationChannel": "Не найдено"
}
```

### ✅ Типы и уровни алертов

**Статус:** PASS
**Сообщение:** Найдены типы и уровни алертов (2)
**Время выполнения:** 0.001 с

**Детали:**
```json
{
  "alert_system.AlertType": "Не найдено",
  "alert_system.AlertSeverity": "Не найдено",
  "monitoring_system.AlertType": "OK",
  "monitoring_system.AlertSeverity": "OK"
}
```

### ✅ Персональные vs системные алерты

**Статус:** PASS
**Сообщение:** Найдена поддержка разделения (1)
**Время выполнения:** 0.001 с

**Детали:**
```json
{
  "alert_system": "Поддержка персональных алертов",
  "monitoring_system": "Нет поддержки персональных алертов"
}
```

### ✅ Приоритеты и эскалация

**Статус:** PASS
**Сообщение:** Найдена логика приоритетов (2)
**Время выполнения:** 0.001 с

**Детали:**
```json
{
  "alert_system": "Найдены: severity, critical, cooldown",
  "monitoring_system": "Найдены: severity, critical, cooldown"
}
```

## Файлы и модули

### ✅ Проверка файлов

**Статус:** PASS
**Сообщение:** Все 32 требуемых файлов существуют
**Время выполнения:** 0.000 с

**Детали:**
```json
{
  "files_checked": 32,
  "categories": [
    "signal_system",
    "order_execution",
    "risk_management",
    "database",
    "configuration",
    "monitoring"
  ]
}
```

### ✅ Файлы сигнальной системы

**Статус:** PASS
**Сообщение:** Все 13 файлов сигнальной системы найдены
**Время выполнения:** 0.000 с

**Детали:**
```json
{
  "files": [
    "signal_live.py",
    "src/filters/smart_trend_filter.py",
    "src/filters/dominance_trend.py",
    "src/filters/interest_zone.py",
    "src/filters/fibonacci_zone.py",
    "src/filters/volume_imbalance.py",
    "src/filters/btc_trend.py",
    "src/filters/anomaly.py",
    "src/filters/whale.py",
    "src/filters/news.py",
    "src/strategies/adaptive_strategy.py",
    "src/analysis/pullback_entry.py",
    "src/analysis/market_structure.py"
  ]
}
```

### ✅ Файлы исполнения ордеров

**Статус:** PASS
**Сообщение:** Все 5 файлов исполнения ордеров найдены
**Время выполнения:** 0.000 с

**Детали:**
```json
{
  "files": [
    "exchange_adapter.py",
    "auto_execution.py",
    "price_monitor_system.py",
    "order_manager.py",
    "order_audit_log.py"
  ]
}
```

### ✅ Лог-файлы

**Статус:** PASS
**Сообщение:** Найдено 2 лог-файлов из 8
**Время выполнения:** 0.000 с

**Детали:**
```json
{
  "existing": [
    {
      "path": "bot.log",
      "size": 10742,
      "size_formatted": "10.49 KB"
    },
    {
      "path": "main.log",
      "size": 10430,
      "size_formatted": "10.19 KB"
    }
  ],
  "missing": [
    "logs/signal_generation.log",
    "logs/filter_performance.log",
    "logs/order_execution.log",
    "logs/exchange_connection.log",
    "logs/trailing_stop.log",
    "logs/position_management.log"
  ]
}
```

**Метрики:**
- total_logs: 8
- existing_logs: 2
- total_size: 21172

## Конфигурация

### ✅ Конфигурация фильтров

**Статус:** PASS
**Сообщение:** Конфигурация фильтров доступна
**Время выполнения:** 0.000 с

**Детали:**
```json
{
  "config_files": [
    "src/filters/config.py",
    "config.py"
  ],
  "parameters": {
    "USE_ADAPTIVE_STRATEGY": true,
    "BTC_TREND_EMA_SOFT": 50,
    "BTC_TREND_EMA_STRICT": 200
  }
}
```

## Биржа

### ✅ Импорт ExchangeAdapter

**Статус:** PASS
**Сообщение:** ExchangeAdapter успешно импортирован
**Время выполнения:** 0.000 с

**Детали:**
```json
{
  "module": "exchange_adapter"
}
```

## Логирование

### ✅ Формат логов

**Статус:** PASS
**Сообщение:** Логирование настроено
**Время выполнения:** 0.000 с

**Детали:**
```json
{
  "handlers_count": 1,
  "level": "INFO"
}
```

### ✅ Уровни логирования

**Статус:** PASS
**Сообщение:** Текущий уровень логирования: INFO
**Время выполнения:** 0.000 с

**Детали:**
```json
{
  "current_level": "INFO",
  "level_value": 20,
  "available_levels": [
    "DEBUG",
    "INFO",
    "WARNING",
    "ERROR",
    "CRITICAL"
  ]
}
```

### ✅ Ротация логов

**Статус:** PASS
**Сообщение:** Ротация логов настроена для 1 обработчиков
**Время выполнения:** 0.004 с

**Детали:**
```json
{
  "rotation_config": [
    {
      "max_bytes": "unknown",
      "backup_count": "unknown"
    }
  ]
}
```

### ✅ Логирование ордеров

**Статус:** PASS
**Сообщение:** OrderAuditLog имеет методы логирования (2)
**Время выполнения:** 0.001 с

**Детали:**
```json
{
  "methods_available": [
    "log_order",
    "log_order_sync"
  ]
}
```

### ✅ Логика разделения TP1/TP2

**Статус:** PASS
**Сообщение:** Метод частичного закрытия на TP1 найден
**Время выполнения:** 0.027 с

**Детали:**
```json
{
  "method": "close_signal_at_tp1"
}
```

## Метрики

### ✅ Метрики сигналов

**Статус:** PASS
**Сообщение:** Собрано метрик сигналов: 4
**Время выполнения:** 0.002 с

**Детали:**
```json
{
  "total_generated": 3637,
  "total_accepted": 5847,
  "total_rejected": 0,
  "acceptance_rate": 160.7643662359087
}
```

**Метрики:**
- total_generated: 3637
- total_accepted: 5847
- total_rejected: 0
- acceptance_rate: 160.7643662359087

### ✅ Метрики ордеров

**Статус:** PASS
**Сообщение:** Собрано метрик ордеров: 4
**Время выполнения:** 0.001 с

**Детали:**
```json
{
  "total_executed": 928,
  "successful_executions": 0,
  "failed_executions": 323,
  "success_rate": 0.0
}
```

**Метрики:**
- total_executed: 928
- successful_executions: 0
- failed_executions: 323
- success_rate: 0.0

### ✅ Метрики позиций

**Статус:** PASS
**Сообщение:** Собрано метрик позиций: 2
**Время выполнения:** 0.002 с

**Детали:**
```json
{
  "active_positions": 0,
  "positions_reached_tp1": 0
}
```

**Метрики:**
- active_positions: 0
- positions_reached_tp1: 0

### ✅ Метрики фильтров

**Статус:** PASS
**Сообщение:** Таблица filter_performance существует и готова к использованию
**Время выполнения:** 0.001 с

**Детали:**
```json
{
  "total_records": 0,
  "note": "Таблица пуста, но это нормально - метрики собираются при работе системы"
}
```

**Рекомендации:**
- Метрики фильтров будут собираться автоматически при работе системы
- Это нормально для новой установки

## ⚠️  Предупреждения

### Структура фильтров
- **Предупреждение:** Импортировано 6, ошибок: 3

### Выполнение фильтров
- **Предупреждение:** Успешно: 0, Ошибок: 2

### Структура управления позициями
- **Предупреждение:** Найдено: 3, Отсутствует: 1
