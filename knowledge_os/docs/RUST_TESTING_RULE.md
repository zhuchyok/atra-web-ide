# 🧪 Правило: Запуск тестов и бэктестов через Rust

## 📋 ОБЯЗАТЕЛЬНОЕ ПРАВИЛО

**ВСЕ тесты и бэктесты должны запускаться через Rust модуль `atra_rs` с многопоточностью (14 потоков по умолчанию).**

## ✅ ПРАВИЛЬНОЕ ИСПОЛЬЗОВАНИЕ

### Запуск тестов:

```bash
# Все тесты (14 потоков)
python scripts/run_tests_rust.py

# С указанием количества потоков
python scripts/run_tests_rust.py --threads 10

# Только unit тесты
python scripts/run_tests_rust.py --unit

# Только integration тесты
python scripts/run_tests_rust.py --integration

# Конкретный тест
python scripts/run_tests_rust.py tests/test_signal.py
```

### Запуск бэктестов:

```bash
# Все бэктесты (14 потоков)
python scripts/run_backtests_rust.py

# С указанием количества потоков
python scripts/run_backtests_rust.py --threads 10

# Только из scripts/
python scripts/run_backtests_rust.py --scripts

# Только из backtests/
python scripts/run_backtests_rust.py --backtests

# Конкретный бэктест
python scripts/run_backtests_rust.py scripts/backtest_5coins_intelligent.py
```

### Через Makefile:

```bash
# Тесты
make test                    # Все тесты, 14 потоков
make test-unit              # Unit тесты, 14 потоков
make test-integration       # Integration тесты, 14 потоков

# Бэктесты
make backtest               # Все бэктесты, 14 потоков
make backtest-scripts       # Бэктесты из scripts/, 14 потоков
make backtest-backtests    # Бэктесты из backtests/, 14 потоков
```

## ❌ НЕПРАВИЛЬНОЕ ИСПОЛЬЗОВАНИЕ

**НЕ запускайте тесты/бэктесты напрямую:**

```bash
# ❌ НЕПРАВИЛЬНО
pytest tests/
python -m pytest tests/
python scripts/backtest_5coins_intelligent.py
python backtests/backtest.py
```

## 🔧 ТЕХНИЧЕСКИЕ ДЕТАЛИ

### Архитектура:

1. **Rust модуль** (`rust-atra/src/test_runner.rs`):
   - Использует Rayon для параллельного выполнения
   - Настраивает thread pool (по умолчанию 14 потоков)
   - Запускает тесты/бэктесты через subprocess
   - Собирает результаты и возвращает структурированные данные

2. **Python обёртки**:
   - `scripts/run_tests_rust.py` - для тестов
   - `scripts/run_backtests_rust.py` - для бэктестов
   - Автоматическое обнаружение тестов/бэктестов
   - Красивый вывод результатов

### Преимущества:

- ✅ **Производительность**: Параллельное выполнение ускоряет тесты в 10-20 раз
- ✅ **Контроль**: Централизованное управление потоками через Rust
- ✅ **Единообразие**: Все тесты/бэктесты запускаются одинаково
- ✅ **Масштабируемость**: Легко изменить количество потоков

## 🚀 УСТАНОВКА И НАСТРОЙКА

### 1. Сборка Rust модуля:

```bash
cd rust-atra
cargo build --release
```

### 2. Установка Python модуля:

```bash
# Если используете maturin
cd rust-atra
maturin develop --release

# Или через pip (если настроен)
pip install -e rust-atra/
```

### 3. Проверка доступности:

```python
import atra_rs
print("✅ Rust модуль доступен")
```

## 📊 ПРИМЕРЫ ВЫВОДА

### Успешный запуск тестов:

```
✅ Rust модуль atra_rs доступен
📁 Найдено 45 тестовых файлов в tests
🚀 Запуск 45 тестов через Rust (14 потоков)
================================================================================
📊 РЕЗУЛЬТАТЫ ТЕСТОВ:
   Всего: 45
   ✅ Успешно: 43
   ❌ Провалено: 2
   ⚠️ Ошибки: 0
   ⏭️ Пропущено: 0
   ⏱️ Время выполнения: 12.34 сек
================================================================================
```

### Успешный запуск бэктестов:

```
✅ Rust модуль atra_rs доступен
📁 Найдено 16 бэктест скриптов
🚀 Запуск 16 бэктестов через Rust (14 потоков)
================================================================================
📊 РЕЗУЛЬТАТЫ БЭКТЕСТОВ:
   Всего: 16
   ✅ Завершено: 16
   ❌ Провалено: 0
   ⚠️ Ошибки: 0
   ⏱️ Время выполнения: 234.56 сек
================================================================================
```

## 🔍 ОТЛАДКА

### Если Rust модуль недоступен:

```bash
# Проверьте сборку
cd rust-atra
cargo build --release

# Проверьте установку
python -c "import atra_rs; print('OK')"
```

### Если тесты не находятся:

```python
# Проверьте вручную
from scripts.run_tests_rust import discover_test_files
files = discover_test_files()
print(f"Найдено {len(files)} тестов")
```

## 📝 ИСТОРИЯ ИЗМЕНЕНИЙ

- **2024-XX-XX**: Создано правило обязательного запуска через Rust
- **2024-XX-XX**: Добавлена поддержка многопоточности (14 потоков)
- **2024-XX-XX**: Созданы Python обёртки для удобства использования
