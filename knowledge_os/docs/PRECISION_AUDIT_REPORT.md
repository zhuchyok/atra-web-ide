# АУДИТ ФОРМАТИРОВАНИЯ ЦЕН И ТОЧНОСТИ

## 📊 Анализ систем форматирования и точности

### Основные компоненты:

#### 1. **Функции форматирования цен:**

- **`safe_format_price(price, symbol)`** - Основная функция в `signal_live.py` и `telegram_bot.py`
- **`get_symbol_precision(symbol)`** - Получение точности для символа в `exchange_api.py`
- **`get_full_price_format(symbol)`** - Получение полного формата цены

#### 2. **Система точности:**

- **Статический словарь** в `get_symbol_precision()` с точностью для каждого символа
- **API-based precision** через `get_symbol_info()` (резервный вариант)
- **Fallback система** с 5 знаками для неизвестных символов

#### 3. **Интеграция с биржей:**

- **Binance API** для получения реальной точности символов
- **Кэширование** информации о символах (`_symbol_info_cache`)
- **Обработка ошибок** для недоступных данных

### 🔧 Анализ текущей системы точности:

#### **Статический словарь точности (`exchange_api.py`):**

```python
precision_map = {
    # Основные монеты (2 знака)
    'BTCUSDT': 2,    # 186.47
    'ETHUSDT': 2,    # 3245.67
    'BNBUSDT': 2,    # 245.89

    # Монеты с 4 знаками
    'XRPUSDT': 4,    # 0.5432
    'ADAUSDT': 4,    # 0.4321

    # Мемкоины с 6 знаками
    'DOGEUSDT': 6,   # 0.078456
    'PEPEUSDT': 6,   # 0.000123
    'SHIBUSDT': 6,   # 0.000023
}
```

- **Плюсы**: Быстрая работа, не зависит от API
- **Минусы**: Требует ручного обновления, может устаревать

#### **Функция safe_format_price:**

```python
def safe_format_price(price, symbol):
    try:
        from exchange_api import get_symbol_precision
        precision = get_symbol_precision(symbol)
        return f"{price:.{precision}f}"

    except (ValueError, TypeError):
        try:
            return f"{price:.5f}"  # Fallback
        except (ValueError, TypeError):
            return 'N/A'
```

- **Плюсы**: Надежная система fallback
- **Минусы**: Дублирование кода в `signal_live.py` и `telegram_bot.py`

#### **API-based точность:**

```python
# Через get_symbol_info()
symbol_info = await get_symbol_info(symbol)
price_precision = symbol_info.get('price_precision', 8)
```

- **Плюсы**: Автоматическое обновление, точные данные
- **Минусы**: Зависит от API, может быть недоступно

### 🚨 Выявленные проблемы:

#### **Проблема 1: Дублирование кода**

- **`safe_format_price`** реализована в `signal_live.py` и `telegram_bot.py`
- **Решение**: Объединить в общий модуль (`shared_utils.py`)

#### **Проблема 2: Устаревание статического словаря**

- Точность символов может меняться со временем
- Нет автоматического обновления
- **Решение**: Приоритизировать API-based precision с fallback на статический словарь

#### **Проблема 3: Разные fallback значения**

- В `signal_live.py`: fallback на 5 знаков
- В `telegram_bot.py`: fallback на 5 знаков
- В API-based: fallback на 8 знаков
- **Решение**: Стандартизировать fallback на 5 знаков для всех случаев

#### **Проблема 4: Отсутствие валидации точности**

- Нет проверки соответствия точности реальным биржевым данным
- Нет обработки edge cases (крайние значения)
- **Решение**: Добавить валидацию и нормализацию

#### **Проблема 5: Нет обработки минимальных лотов**

- Функции форматирования не учитывают минимальные размеры ордеров
- Нет проверки соответствия количества биржевым требованиям
- **Решение**: Интегрировать с `get_symbol_info()` для получения min_qty

### 🔧 Рекомендации по улучшению:

#### **1. Унификация функций форматирования:**

```python
# В shared_utils.py
def safe_format_price(price, symbol=None, default_precision=5):
    """
    Унифицированная функция форматирования цен
    """
    if price is None or (hasattr(price, 'isna') and pd.isna(price)):
        return 'N/A'

    if symbol is None:
        return f"{price:.{default_precision}f}"

    try:
        # Сначала пробуем API
        from exchange_api import get_symbol_info
        symbol_info = get_symbol_info(symbol)  # Синхронная версия
        if symbol_info and 'price_precision' in symbol_info:
            precision = symbol_info['price_precision']
            return f"{price:.{precision}f}"

        # Fallback на статический словарь
        from exchange_api import get_symbol_precision
        precision = get_symbol_precision(symbol)
        return f"{price:.{precision}f}"

    except Exception:
        return f"{price:.{default_precision}f}"

def safe_format_quantity(qty, symbol=None, default_precision=4):
    """
    Безопасное форматирование количества
    """
    if qty is None or (hasattr(qty, 'isna') and pd.isna(qty)):
        return 'N/A'

    if symbol is None:
        return f"{qty:.{default_precision}f}"

    try:
        # Получаем информацию о минимальном количестве
        from exchange_api import get_symbol_info
        symbol_info = get_symbol_info(symbol)
        if symbol_info and 'qty_precision' in symbol_info:
            precision = symbol_info['qty_precision']
            return f"{qty:.{precision}f}"

        return f"{qty:.{default_precision}f}"

    except Exception:
        return f"{qty:.{default_precision}f}"
```

#### **2. Улучшенная система точности:**

```python
def get_dynamic_precision(symbol, price=None):
    """
    Динамическое определение точности с учетом цены
    """
    try:
        # Базовая точность
        base_precision = get_symbol_precision(symbol)

        # Корректировка для очень маленьких цен
        if price is not None and price < 0.01:
            # Для цен < 0.01 увеличиваем точность
            return base_precision + 2
        elif price is not None and price < 1:
            # Для цен < 1 увеличиваем точность на 1
            return base_precision + 1

        return base_precision

    except Exception:
        return 5  # Fallback
```

#### **3. Валидация биржевых ограничений:**

```python
def validate_order_parameters(symbol, price, qty):
    """
    Валидация параметров ордера на соответствие биржевым требованиям
    """
    errors = []

    try:
        from exchange_api import get_symbol_info
        symbol_info = get_symbol_info(symbol)

        if not symbol_info:
            errors.append("Не удалось получить информацию о символе")
            return errors

        # Проверка минимальной цены
        min_price = symbol_info.get('min_price', 0)
        if price < min_price:
            errors.append(f"Цена {price} ниже минимальной {min_price}")

        # Проверка максимальной цены
        max_price = symbol_info.get('max_price', float('inf'))
        if price > max_price:
            errors.append(f"Цена {price} выше максимальной {max_price}")

        # Проверка минимального количества
        min_qty = symbol_info.get('min_qty', 0)
        if qty < min_qty:
            errors.append(f"Количество {qty} ниже минимального {min_qty}")

        # Проверка максимального количества
        max_qty = symbol_info.get('max_qty', float('inf'))
        if qty > max_qty:
            errors.append(f"Количество {qty} выше максимального {max_qty}")

        # Проверка точности цены
        price_precision = symbol_info.get('price_precision', 5)
        formatted_price = f"{price:.{price_precision}f}"
        if abs(float(formatted_price) - price) > 1e-10:
            errors.append(f"Цена {price} не соответствует точности {price_precision}")

    except Exception as e:
        errors.append(f"Ошибка валидации: {e}")

    return errors
```

#### **4. Система нормализации:**

```python
def normalize_price(price, symbol):
    """
    Нормализация цены согласно биржевым правилам
    """
    try:
        from exchange_api import get_symbol_info
        symbol_info = get_symbol_info(symbol)

        if symbol_info:
            price_precision = symbol_info.get('price_precision', 5)
            tick_size = symbol_info.get('tick_size', 10**-price_precision)

            # Округление до ближайшего tick_size
            normalized_price = round(price / tick_size) * tick_size
            return normalized_price

        # Fallback на простое округление
        precision = get_symbol_precision(symbol)
        return round(price, precision)

    except Exception:
        return round(price, 5)  # Fallback

def normalize_quantity(qty, symbol):
    """
    Нормализация количества согласно биржевым правилам
    """
    try:
        from exchange_api import get_symbol_info
        symbol_info = get_symbol_info(symbol)

        if symbol_info:
            qty_precision = symbol_info.get('qty_precision', 4)
            step_size = symbol_info.get('step_size', 10**-qty_precision)

            # Округление до ближайшего step_size
            normalized_qty = round(qty / step_size) * step_size
            return normalized_qty

        # Fallback на простое округление
        return round(qty, 4)

    except Exception:
        return round(qty, 4)  # Fallback
```

### 📋 План улучшений:

#### **Фаза 1: Консолидация**

1. Объединить `safe_format_price` в `shared_utils.py`
2. Стандартизировать fallback точность на 5 знаков
3. Убрать дублирование кода

#### **Фаза 2: Улучшение точности**

1. Приоритизировать API-based precision
2. Добавить динамическую корректировку точности
3. Реализовать валидацию биржевых ограничений

#### **Фаза 3: Нормализация**

1. Добавить функции нормализации цен и количеств
2. Интегрировать с биржевыми ограничениями
3. Добавить автоматическую корректировку параметров

#### **Фаза 4: Тестирование**

1. Добавить unit тесты для функций форматирования
2. Провести валидацию на реальных данных
3. Документировать edge cases

### 🎯 Приоритеты:

#### **Высокий приоритет:**

1. Объединить дублированные функции форматирования
2. Стандартизировать fallback значения
3. Добавить валидацию биржевых ограничений

#### **Средний приоритет:**

1. Улучшить систему точности с API priority
2. Добавить нормализацию цен и количеств
3. Реализовать динамическую корректировку точности

#### **Низкий приоритет:**

1. Добавить расширенное логирование
2. Создать тесты для edge cases
3. Документировать все функции форматирования

---

_Аудит форматирования цен и точности завершен. Система имеет хорошую основу, но требует унификации и улучшения надежности._
