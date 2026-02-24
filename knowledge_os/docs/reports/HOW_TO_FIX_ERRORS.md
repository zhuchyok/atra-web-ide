# КАК ПРАВИЛЬНО ИСПРАВЛЯТЬ ОШИБКИ

## 📋 ДЛЯ ИСПОЛНИТЕЛЯ (AI):

### НЕ ДЕЛАТЬ:

- ❌ Сразу удалять или комментировать код
- ❌ Предполагать, что функция не существует
- ❌ Игнорировать импорты и зависимости

### ДЕЛАТЬ:

- ✅ **НАЙТИ функцию** через grep/file_search
- ✅ **ПРОВЕРИТЬ** все места использования
- ✅ **ПОНЯТЬ** контекст и сигнатуру
- ✅ **ПРЕДЛОЖИТЬ** правильное исправление
- ✅ **ОБЪЯСНИТЬ** что изменилось и почему

## 🔍 ПОШАГОВЫЙ АЛГОРИТМ:

### 1. Найдите функцию:

```bash
grep -r "def function_name" .
find . -name "*.py" -exec grep -l "function_name" {} \;
```

### 2. Проверьте использование:

```bash
grep -n "function_name(" file.py
grep -A5 -B5 "from.*import function_name" .
```

### 3. Поймите контекст:

- Что функция принимает?
- Что возвращает?
- Где она определена?
- Как она используется?

### 4. Найдите правильное решение:

- Может быть другой путь импорта?
- Может быть нужно создать экземпляр класса?
- Может быть функция переименована?

### 5. Исправьте осторожно:

- Не удаляйте код без проверки
- Сохраните функциональность
- Объясните изменения

## ✅ ПРАВИЛЬНО:

### Пример 1: Ошибка импорта

```
Ошибка: cannot import name 'get_ohlc_binance_sync_async' from 'signal_live'
```

Что НЕ делать:

```python
# from signal_live import get_ohlc_binance_sync_async  # Закомментировано
```

Что делать:

```python
# 1. Найти функцию
grep -r "def get_ohlc_binance_sync_async"

# 2. Найти правильный импорт
# Функция в ohlc_utils.py, строка 203

# 3. Исправить импорт
from ohlc_utils import get_ohlc_binance_sync_async
```

### Пример 2: Функция в классе

```
Ошибка: cannot import name 'calculate_anomaly_based_volume' from 'signal_live'
```

Что НЕ делать:

```python
# volume_result = calculate_anomaly_based_volume(...)  # Закомментировано
```

Что делать:

```python
# 1. Найти функцию
grep -r "def calculate_anomaly_based_volume"
# Нашел: src/filters/anomaly.py, строка 208

# 2. Найти класс и импорт
grep -B5 "def calculate_anomaly_based_volume" src/filters/anomaly.py
# Нашел: class AnomalyFilter

# 3. Использовать правильно
from src.filters.anomaly import anomaly_filter
volume_result = anomaly_filter.calculate_anomaly_based_volume(df, base_volume)
```

## 📝 ЧЕКЛИСТ ПЕРЕД ИСПРАВЛЕНИЕМ:

- [ ] Нашел функцию в коде
- [ ] Проверил все места использования
- [ ] Понял сигнатуру функции
- [ ] Нашел правильный путь импорта
- [ ] Сохранил функциональность
- [ ] Объяснил изменения
- [ ] Проверил, что ничего не удалено лишнего

## 🎯 ПРАВИЛО:

**НЕ УДАЛЯЙ - АНАЛИЗИРУЙ!**
