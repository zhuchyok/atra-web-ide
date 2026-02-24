# 🚀 ИНСТРУКЦИЯ ПО ИСПОЛЬЗОВАНИЮ АВТОНОМНОЙ КОМАНДЫ

## 📋 БЫСТРЫЙ СТАРТ

### 1. Активация конкретной роли:

```bash
# В Cursor Chat просто упомяните роль:
@quant Разработай стратегию mean-reversion для BTCUSDT

@trader Валидируй эту стратегию на реальных данных

@devops Настрой deployment для этой стратегии

@risk_manager Установи risk limits для стратегии
```

### 2. Комплексные задачи с несколькими ролями:

```python
# В коде используйте комментарии для привлечения экспертов:

# @quant: Разработай математическую модель
# @trader: Проверь практическую применимость
# @devops: Обеспечь производительность
def complex_trading_strategy(data):
    # implementation
    pass
```

### 3. Автоматические процессы:

```bash
# Ежедневный стендап
@all_generate_daily_standup

# Code review всей команды
@all_review_strategy strategy_file.py

# Аудит рисков
@risk_manager conduct_risk_audit
```

## 🎯 ПРАКТИЧЕСКИЕ ПРИМЕРЫ

### Пример 1: Разработка новой стратегии

```bash
@quant Разработай mean-reversion стратегию для ETHUSDT с параметрами:
- Таймфрейм: 5 минут
- Индикаторы: RSI, Bollinger Bands
- Risk/Reward: 1:1.5
- Максимальная просадка: 8%

После разработки:
@trader Протестируй стратегию на исторических данных
@risk_manager Установи лимиты для этой стратегии
@devops Подготовь deployment в staging
```

### Пример 2: Оптимизация существующей стратегии

```bash
@quant Проанализируй performance стратегии momentum_btc:
1. Рассчитай метрики за последние 30 дней
2. Выяви параметры для оптимизации
3. Проведи walk-forward optimization

@trader Оцени улучшения на реальных данных
@data_scientist Предложи ML-улучшения для сигналов
```

### Пример 3: Инфраструктурные задачи

```bash
@devops Настрой мониторинг для trading системы:
- Latency до бирж
- PnL в реальном времени
- System health metrics
- Risk limits monitoring

@system_architect Проверь архитектурную корректность
```

## 🔧 НАСТРОЙКА CURSOR

### 1. Убедитесь что структура папок правильная:

```
algorithmic-trading-team/
├── .cursor/
│   ├── rules/          # Все .md файлы ролей
│   └── prompts/        # Шаблоны промптов
├── src/               # Исходный код
├── infrastructure/    # DevOps конфиги
└── tests/            # Тесты
```

### 2. Проверьте что Cursor использует правила:

- Откройте Cursor Settings
- Убедитесь что включено использование .cursorrules
- Проверьте что все .md файлы загружены

### 3. Тестирование системы:

```bash
# Протестируйте каждую роль
@quant Представься и опиши свою роль

@trader Какие метрики ты используешь для валидации стратегий?

@devops Как ты обеспечиваешь low-latency trading?
```

## 🎪 ВЗАИМОДЕЙСТВИЕ РОЛЕЙ

### Стандартный workflow разработки:

```
1. Trader: Идентификация рыночной возможности
2. Quant: Разработка математической модели
3. Data Scientist: ML-улучшения (опционально)
4. Trader: Валидация на реальных данных
5. Risk Manager: Установление лимитов
6. DevOps: Развертывание и мониторинг
7. System Architect: Контроль качества архитектуры
```

### Процесс code review:

```
Для каждого PR автоматически привлекаются:
- Quant: математическая корректность
- Trader: практическая применимость
- DevOps: производительность и deployment
- System Architect: архитектурное качество
```

## 📊 МОНИТОРИНГ ЭФФЕКТИВНОСТИ

### Ключевые метрики системы:

```python
SYSTEM_METRICS = {
    'strategy_success_rate': '> 70% стратегий profitable',
    'development_velocity': '2-3 стратегии в неделю',
    'system_uptime': '> 99.9%',
    'risk_compliance': '100% соблюдение лимитов',
    'team_autonomy': 'Минимальное ручное вмешательство'
}
```

### Отслеживание эффективности ролей:

```python
ROLE_PERFORMANCE = {
    'quant': ['strategies_developed', 'backtest_accuracy'],
    'trader': ['edge_validation_success', 'pnl_contribution'],
    'devops': ['uptime_percentage', 'deployment_success'],
    'risk': ['limit_breaches_prevented', 'drawdown_control']
}
```

## 🚀 ПРОДВИНУТЫЕ ВОЗМОЖНОСТИ

### Автоматическое планирование работы:

```bash
# Генерация weekly plan на основе метрик
@all_generate_weekly_plan

# Приоритизация задач на основе ROI
@system_architect prioritize_tasks_based_on_metrics

# Автоматическое распределение работы
@all_assign_tasks_based_on_expertise
```

### Интеграция с внешними системами:

```python
# Автоматический импорт рыночных данных
@data_engineer sync_market_data

# Экспорт метрик в дашборды
@devops update_monitoring_dashboards

# Интеграция с risk management системами
@risk_manager sync_with_risk_system
```

## 🆘 ПОЛУЧЕНИЕ ПОМОЩИ

### Если система не работает:

1. Проверьте структуру папок
2. Убедитесь что все .md файлы на месте
3. Проверьте синтаксис .cursorrules файлов
4. Перезапустите Cursor

### Для тонкой настройки:

```bash
# Диагностика правил
@system_architect diagnose_rule_issues

# Оптимизация промптов
@all_optimize_prompts_based_on_usage

# Добавление новых ролей
@system_architect add_new_role data_scientist
```

Эта система превратит вашу работу с Cursor в полноценную автономную trading команду! 🎯
