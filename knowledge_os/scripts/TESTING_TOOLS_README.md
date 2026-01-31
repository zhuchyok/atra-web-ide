# Инструменты автоматизации проверок

Набор скриптов для автоматизации всех проверок из технического задания `TESTING_TEAM_TECHNICAL_SPECIFICATION.md`.

## Структура

### Базовые модули
- `test_utils.py` - общие утилиты (работа с БД, форматирование, результаты тестов)
- `test_config.py` - конфигурация тестов (пути, таблицы, параметры)

### Модули проверок
- `test_db_structure.py` - проверка структуры БД
- `test_files_modules.py` - проверка файлов и модулей
- `test_configuration.py` - проверка конфигурации
- `test_exchange_connection.py` - проверка подключения к бирже
- `test_logging.py` - проверка системы логирования
- `test_performance.py` - мониторинг производительности
- `test_metrics.py` - сбор и проверка метрик

### Генерация отчетов
- `test_report_generator.py` - генератор отчетов (JSON, Markdown, консоль)
- `test_suite_runner.py` - главный скрипт для запуска всех проверок

## Использование

### Запуск всех проверок

```bash
python scripts/test_suite_runner.py --all
```

### Запуск конкретной категории

```bash
# Проверка БД
python scripts/test_suite_runner.py --category db

# Проверка файлов и модулей
python scripts/test_suite_runner.py --category files

# Проверка конфигурации
python scripts/test_suite_runner.py --category config

# Проверка биржи
python scripts/test_suite_runner.py --category exchange

# Проверка логирования
python scripts/test_suite_runner.py --category logging

# Проверка производительности
python scripts/test_suite_runner.py --category performance

# Проверка метрик
python scripts/test_suite_runner.py --category metrics
```

### Генерация отчетов

```bash
# Все форматы (JSON + Markdown + консоль)
python scripts/test_suite_runner.py --all --report all

# Только JSON
python scripts/test_suite_runner.py --all --report json

# Только Markdown
python scripts/test_suite_runner.py --all --report markdown

# Только консоль
python scripts/test_suite_runner.py --all --report console

# Без консольного вывода
python scripts/test_suite_runner.py --all --no-console
```

### Настройка директории для отчетов

```bash
python scripts/test_suite_runner.py --all --output-dir my_reports
```

## Категории проверок

### 1. База данных (`db`)
- Подключение к БД
- Наличие всех требуемых таблиц
- Структура таблиц
- Целостность данных
- Данные в критических таблицах

### 2. Файлы и модули (`files`)
- Существование всех требуемых файлов
- Импорт модулей
- Наличие классов и функций
- Структура директорий

### 3. Конфигурация (`config`)
- Определение окружения (PROD/DEV)
- Корректность токенов Telegram
- Блокировка авто-исполнения в DEV
- Наличие API ключей биржи
- Настройки фильтров

### 4. Биржа (`exchange`)
- Импорт ExchangeAdapter
- Подключение к бирже
- Получение баланса
- Формат символов

### 5. Логирование (`logging`)
- Наличие лог-файлов
- Формат логов
- Уровни логирования
- Ротация логов
- Запись в БД

### 6. Производительность (`performance`)
- Использование CPU
- Использование памяти
- Производительность БД
- Использование диска

### 7. Метрики (`metrics`)
- Метрики сигналов
- Метрики ордеров
- Метрики позиций
- Метрики фильтров

### 8. Сигналы (функциональные) (`signals_func`)
- Генерация сигналов
- Работа фильтров
- Адаптивная стратегия
- Оценка качества сигналов

### 9. Ордера (функциональные) (`orders_func`)
- Структура OrderManager
- Валидация параметров ордеров
- Типы ордеров TP1/TP2/SL
- Логирование ордеров
- Флаг reduce_only

### 10. Риски (функциональные) (`risk_func`)
- Trailing Stop Manager
- Расчет безубытка
- Адаптивный trailing stop
- Управление позициями
- Логика разделения TP1/TP2

### 11. Интеграция (полный цикл) (`integration`)
- Поток сигнал → БД
- Поток сигнал → Telegram
- Поток принятие → ордер
- Поток ордер → управление
- Компоненты полного цикла
- Целостность передачи данных

### 12. Система алертов (`alerts`)
- Структура AlertSystem
- Каналы Telegram уведомлений
- Типы и уровни алертов
- Персональные vs системные алерты
- Приоритеты и эскалация

## Форматы отчетов

### JSON
Структурированный формат для машинной обработки:
```json
{
  "timestamp": "2025-01-27T12:00:00",
  "total_tests": 25,
  "passed": 20,
  "failed": 3,
  "warnings": 2,
  "results": [...]
}
```

### Markdown
Человекочитаемый формат с детальной информацией:
- Сводка результатов
- Детали по категориям
- Проваленные проверки
- Предупреждения
- Рекомендации

### Консоль
Краткая сводка в терминале с цветовой индикацией.

## Статусы проверок

- ✅ **PASS** - проверка пройдена успешно
- ❌ **FAIL** - проверка провалена (требует исправления)
- ⚠️ **WARNING** - предупреждение (не критично, но стоит обратить внимание)
- ⏭️ **SKIP** - проверка пропущена (не применима в текущих условиях)

## Примеры использования

### Быстрая проверка перед деплоем

```bash
python scripts/test_suite_runner.py --all --report markdown --output-dir pre_deploy_reports
```

### Проверка только критических компонентов

```bash
python scripts/test_suite_runner.py --category db
python scripts/test_suite_runner.py --category config
python scripts/test_suite_runner.py --category files
```

### Ежедневная проверка

```bash
python scripts/test_suite_runner.py --all --report json --output-dir daily_reports/$(date +%Y-%m-%d)
```

## Интеграция с CI/CD

Скрипт возвращает код выхода:
- `0` - все проверки пройдены
- `1` - есть проваленные проверки

Пример для CI:
```bash
python scripts/test_suite_runner.py --all --report json --no-console
if [ $? -ne 0 ]; then
    echo "Тесты провалены!"
    exit 1
fi
```

## Требования

- Python 3.7+
- Зависимости проекта (установлены через `requirements.txt`)
- Опционально: `psutil` для проверки производительности

## Примечания

- Некоторые проверки требуют наличия API ключей (пропускаются, если не установлены)
- Проверки БД требуют наличия файла `trading.db`
- Лог-файлы могут отсутствовать при первом запуске (это нормально)
- Метрики могут быть пустыми для новой установки

## Поддержка

При возникновении проблем:
1. Проверьте логи выполнения
2. Убедитесь, что все зависимости установлены
3. Проверьте наличие необходимых файлов и БД
4. Запустите проверки по категориям для диагностики

