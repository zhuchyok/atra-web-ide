# Auto-Optimizer — проактивная оптимизация

Автоматический цикл: сбор метрик → анализ → применение стратегий.

## Включение

```bash
# .env
AUTO_OPTIMIZER_ENABLED=true
AUTO_OPTIMIZER_INTERVAL_SEC=300  # цикл каждые 5 минут
```

## Стратегии

| Стратегия | Триггер | Действие |
|-----------|---------|----------|
| **Cache TTL** | P95 > 150ms или hit rate < 50% | Увеличение TTL кэша |
| **Preload patterns** | Hit rate < 50% | Предзагрузка из `data/frequent_queries.json` |

## API

- `GET /api/auto-optimizer/status` — статус
- `GET /api/auto-optimizer/dashboard` — данные дашборда

## Дашборд

```bash
# Генерация HTML (использует backend/auto_optimizer_report.json)
PYTHONPATH=backend:. python scripts/create_auto_optimizer_dashboard.py
# Открыть: auto_optimizer_dashboard.html
```

## Файлы

- `backend/app/services/optimization/auto_optimizer.py` — основной движок
- `backend/auto_optimizer_report.json` — отчёт последнего цикла
