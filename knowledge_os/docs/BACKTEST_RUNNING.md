# 🚀 БЭКТЕСТЫ ПАРАМЕТРОВ ЗАПУЩЕНЫ

**Дата запуска:** 2025-12-14 01:27:32

## Статус

✅ **Бэктесты запущены в фоновом режиме**

## Команда запуска

```bash
source venv/bin/activate
python scripts/backtest_filter_parameters.py --threads 15 --period 90
```

## Параметры

- **Потоков:** 15
- **Период:** 90 дней (3 месяца)
- **Символы:** Топ-20 монет из intelligent_filter_system
- **Параметры для тестирования:**
  1. min_confidence_for_short: 0.40, 0.50, 0.60, 0.70
  2. min_quality_threshold_long: 0.33, 0.40, 0.45
  3. min_quality_for_short: 0.45, 0.50, 0.55
  4. market_adjustment: -0.10, -0.05, 0.0
  5. min_h4_confidence: 0.4, 0.5, 0.6

## Мониторинг

### Проверить статус процесса:

```bash
ps aux | grep backtest_filter_parameters
```

### Просмотреть логи:

```bash
tail -f backtest_all_params.log
```

### Проверить результаты:

```bash
ls -la backtest_results/filter_parameters/
```

## Ожидаемое время выполнения

- **Один параметр (4 значения, 20 монет):** ~2-4 часа
- **Все 5 параметров:** ~10-20 часов

## Следующие шаги после завершения

1. **Проанализировать результаты:**

   ```bash
   source venv/bin/activate
   python scripts/analyze_filter_parameters_results.py
   ```

2. **Просмотреть отчет:**

   ```bash
   cat docs/FILTER_PARAMETERS_OPTIMIZATION_RESULTS.md
   ```

3. **Обновить параметры в коде** на основе результатов

4. **Убрать "ВРЕМЕННО"** из комментариев

5. **Добавить комментарии с обоснованием**

## Файлы результатов

- **Логи:** `backtest_all_params.log`
- **Результаты:** `backtest_results/filter_parameters/{param_name}_results.json`
- **Сводка:** `backtest_results/filter_parameters/optimal_values_summary.json`
- **Отчет:** `docs/FILTER_PARAMETERS_OPTIMIZATION_RESULTS.md` (после анализа)

---

_Бэктесты запущены. Проверьте логи для отслеживания прогресса._
