# Руководство по бэктестированию параметров фильтров

## Обзор

Система бэктестирования параметров фильтров позволяет тестировать различные значения критичных параметров и определять оптимальные на основе метрик производительности.

## Структура

### Скрипты

1. **`scripts/backtest_filter_parameters.py`** - Основной скрипт для запуска бэктестов
2. **`scripts/analyze_filter_parameters_results.py`** - Скрипт для анализа результатов

### Параметры для тестирования

1. **min_confidence_for_short** (Приоритет 1 - КРИТИЧНО)
   - Текущее: 0.40
   - Тестировать: 0.40, 0.50, 0.60, 0.70

2. **min_quality_threshold_long** (Приоритет 1 - КРИТИЧНО)
   - Текущее: max(0.33, base + adjustment)
   - Тестировать: 0.33, 0.40, 0.45

3. **min_quality_for_short** (Приоритет 2 - ВАЖНО)
   - Текущее: 0.45
   - Тестировать: 0.45, 0.50, 0.55

4. **market_adjustment** (Приоритет 2 - ВАЖНО)
   - Текущее: -0.10
   - Тестировать: -0.10, -0.05, 0.0

5. **min_h4_confidence** (Приоритет 3 - ЖЕЛАТЕЛЬНО)
   - Текущее: 0.4
   - Тестировать: 0.4, 0.5, 0.6

## Использование

### Запуск бэктестов

#### Все параметры (рекомендуется)

```bash
python3 scripts/backtest_filter_parameters.py --threads 15 --period 90
```

#### Один параметр

```bash
# Тестирование min_confidence_for_short
python3 scripts/backtest_filter_parameters.py --threads 15 --period 90 --param min_confidence_for_short

# Тестирование min_quality_threshold_long
python3 scripts/backtest_filter_parameters.py --threads 15 --period 90 --param min_quality_threshold_long

# Тестирование min_quality_for_short
python3 scripts/backtest_filter_parameters.py --threads 15 --period 90 --param min_quality_for_short

# Тестирование market_adjustment
python3 scripts/backtest_filter_parameters.py --threads 15 --period 90 --param market_adjustment

# Тестирование min_h4_confidence
python3 scripts/backtest_filter_parameters.py --threads 15 --period 90 --param min_h4_confidence
```

### Параметры командной строки

- `--threads` - Количество потоков для параллелизации (по умолчанию 15)
- `--period` - Период бэктеста в днях (по умолчанию 90)
- `--param` - Тестировать только один параметр (опционально)
- `--mode` - Режим фильтров: soft или strict (по умолчанию soft)

### Анализ результатов

После завершения бэктестов запустите анализ:

```bash
# Анализ всех параметров
python3 scripts/analyze_filter_parameters_results.py

# Анализ одного параметра
python3 scripts/analyze_filter_parameters_results.py --param min_confidence_for_short
```

Результаты будут сохранены в `docs/FILTER_PARAMETERS_OPTIMIZATION_RESULTS.md`.

## Результаты

### Расположение файлов

- **Результаты бэктестов:** `backtest_results/filter_parameters/{param_name}_results.json`
- **Сводка оптимальных значений:** `backtest_results/filter_parameters/optimal_values_summary.json`
- **Отчет анализа:** `docs/FILTER_PARAMETERS_OPTIMIZATION_RESULTS.md`

### Метрики

Бэктесты рассчитывают следующие метрики:

- **Win Rate (%)** - Процент прибыльных сделок
- **Profit Factor** - Отношение прибыли к убыткам
- **Total Return (%)** - Общая доходность
- **Max Drawdown (%)** - Максимальная просадка
- **Sharpe Ratio** - Риск-скорректированная доходность
- **Total Trades** - Общее количество сделок
- **Signals Generated** - Количество сгенерированных сигналов
- **Signals Executed** - Количество исполненных сигналов
- **Avg Profit per Trade** - Средняя прибыль на сделку

### Критерии выбора оптимального значения

Комплексный score рассчитывается на основе:

1. **Profit Factor** (вес 30%)
2. **Win Rate** (вес 25%)
3. **Total Return** (вес 20%)
4. **Sharpe Ratio** (вес 15%)
5. **Max Drawdown** (вес 10%, меньше = лучше)

## Технические детали

### Параметры бэктеста

- **Период:** 3 месяца (90 дней)
- **Символы:** Топ-20 монет из `intelligent_filter_system.py`
- **Таймфрейм:** 1h
- **Начальный баланс:** 10,000 USDT
- **Комиссия:** 0.1% (0.001)
- **Проскальзывание:** 0.05% (0.0005)
- **Параллелизация:** Rust с 15 потоками

### Переопределение параметров

Параметры переопределяются через environment variables:

- `BACKTEST_min_confidence_for_short`
- `BACKTEST_min_quality_threshold_long`
- `BACKTEST_min_quality_for_short`
- `BACKTEST_market_adjustment`
- `BACKTEST_min_h4_confidence`

Эти переменные используются в `signal_live.py` и `config.py` для переопределения значений во время бэктестов.

## Время выполнения

Ожидаемое время выполнения бэктестов:

- **Один параметр (4 значения, 20 монет):** ~2-4 часа
- **Все 5 параметров:** ~10-20 часов

Время может варьироваться в зависимости от:
- Количества символов
- Периода бэктеста
- Количества потоков
- Производительности системы

## Следующие шаги

После получения результатов:

1. Запустить анализ результатов
2. Просмотреть отчет `docs/FILTER_PARAMETERS_OPTIMIZATION_RESULTS.md`
3. Обновить значения параметров в `signal_live.py` и `config.py`
4. Убрать "ВРЕМЕННО" из комментариев
5. Добавить комментарии с обоснованием и ссылкой на отчет
6. Обновить документацию

