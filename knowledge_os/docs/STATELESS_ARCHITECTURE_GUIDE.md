# 🔄 STATELESS ARCHITECTURE GUIDE

## 📋 Содержание

1. [Введение](#введение)
2. [Принципы stateless архитектуры](#принципы-stateless-архитектуры)
3. [Примеры правильного и неправильного подхода](#примеры-правильного-и-неправильного-подхода)
4. [Миграционный гайд](#миграционный-гайд)
5. [Best Practices](#best-practices)
6. [FAQ](#faq)

---

## 🎯 Введение

### Что такое stateless архитектура?

**Stateless архитектура** — это подход к проектированию, при котором функции и модули не хранят внутреннее состояние между вызовами. Вместо этого все состояние передается явно через параметры.

### Зачем это нужно?

**Проблемы текущего подхода (с модульными переменными):**

```python
# ❌ ПРОБЛЕМА: Модульная переменная создает скрытое состояние
_vp_cache = {}

def check_volume_profile_filter(df, i, side):
    if symbol not in _vp_cache:
        _vp_cache[symbol] = calculate_profile(df)
    # ...
```

**Проблемы:**
1. ❌ Невозможно использовать функцию в разных контекстах
2. ❌ Сложно тестировать (скрытое состояние)
3. ❌ Конфликты при параллельном использовании
4. ❌ Сложная отладка (непонятно, откуда берется состояние)

**Решение (stateless):**

```python
# ✅ РЕШЕНИЕ: Состояние передается явно
def check_volume_profile_filter(
    df, i, side,
    filter_state: Optional[FilterState] = None
):
    if filter_state is None:
        filter_state = FilterState()
    
    if symbol not in filter_state.cache:
        filter_state.cache[symbol] = calculate_profile(df)
    
    return result, filter_state
```

**Преимущества:**
1. ✅ Переиспользуемость в любом контексте
2. ✅ Легко тестировать (явное состояние)
3. ✅ Безопасно для параллельного использования
4. ✅ Простая отладка (все состояние видно)

---

## 📐 Принципы stateless архитектуры

### Принцип 1: Утилитные функции должны быть stateless

**Правило:** Функции не должны использовать модульные переменные для накопления состояния.

**❌ НЕПРАВИЛЬНО:**
```python
# Модульная переменная для кэша
_price_cache = {}

def get_price(symbol: str) -> float:
    if symbol in _price_cache:
        return _price_cache[symbol]
    
    price = fetch_price_from_api(symbol)
    _price_cache[symbol] = price
    return price
```

**✅ ПРАВИЛЬНО:**
```python
def get_price(
    symbol: str,
    cache_manager: Optional[CacheManager] = None
) -> Tuple[float, CacheManager]:
    if cache_manager is None:
        cache_manager = CacheManager()
    
    cached = cache_manager.get(f"price:{symbol}")
    if cached:
        return cached, cache_manager
    
    price = fetch_price_from_api(symbol)
    cache_manager.set(f"price:{symbol}", price, ttl=60)
    return price, cache_manager
```

### Принцип 2: Кэширование через явные менеджеры

**Правило:** Использовать классы-менеджеры кэша вместо модульных словарей.

**❌ НЕПРАВИЛЬНО:**
```python
# Модульные кэши
_symbol_info_cache = {}
_price_cache = {}

def get_symbol_info(symbol: str):
    if symbol in _symbol_info_cache:
        return _symbol_info_cache[symbol]
    # ...
```

**✅ ПРАВИЛЬНО:**
```python
class CacheManager:
    """Явный менеджер кэша"""
    def __init__(self):
        self._cache: Dict[str, CacheEntry] = {}
    
    def get(self, key: str) -> Optional[Any]:
        entry = self._cache.get(key)
        if entry and not entry.is_expired():
            return entry.value
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        self._cache[key] = CacheEntry(value, ttl=ttl)

# Использование:
cache_manager = CacheManager()

def get_symbol_info(
    symbol: str,
    cache_manager: CacheManager
) -> Dict[str, Any]:
    cached = cache_manager.get(f"symbol_info:{symbol}")
    if cached:
        return cached
    # ...
```

### Принцип 3: Индикаторы - передача предыдущих значений

**Правило:** Предыдущие значения индикаторов передаются через параметры, а не хранятся в модульных переменных.

**❌ НЕПРАВИЛЬНО:**
```python
# Модульные переменные для предыдущих значений
_prev_rsi = None
_prev_macd = None
_prev_ema = None

def calculate_indicators(df: pd.DataFrame, i: int):
    global _prev_rsi, _prev_macd, _prev_ema
    
    rsi = calculate_rsi(df, i, _prev_rsi)
    _prev_rsi = rsi
    
    macd = calculate_macd(df, i, _prev_macd)
    _prev_macd = macd
    
    return {'rsi': rsi, 'macd': macd}
```

**✅ ПРАВИЛЬНО:**
```python
@dataclass
class IndicatorState:
    """Контейнер состояния для индикаторов"""
    prev_rsi: Optional[float] = None
    prev_macd: Optional[float] = None
    prev_ema: Optional[float] = None

def calculate_indicators(
    df: pd.DataFrame,
    i: int,
    state: Optional[IndicatorState] = None
) -> Tuple[Dict[str, Any], IndicatorState]:
    """Возвращает (результат, новое_состояние)"""
    if state is None:
        state = IndicatorState()
    
    rsi = calculate_rsi(df, i, state.prev_rsi)
    macd = calculate_macd(df, i, state.prev_macd)
    
    result = {'rsi': rsi, 'macd': macd}
    new_state = IndicatorState(
        prev_rsi=rsi,
        prev_macd=macd,
        prev_ema=state.prev_ema
    )
    
    return result, new_state
```

### Принцип 4: Фильтры - явное управление состоянием

**Правило:** Фильтры используют контейнеры состояния вместо модульных переменных.

**❌ НЕПРАВИЛЬНО:**
```python
# Модульные переменные для фильтров
_vp_cache = {}
_vp_stats = {
    'total_checked': 0,
    'blocked_count': 0
}

def check_volume_profile_filter(df, i, side):
    _vp_stats['total_checked'] += 1
    
    if symbol not in _vp_cache:
        _vp_cache[symbol] = calculate_profile(df)
    # ...
```

**✅ ПРАВИЛЬНО:**
```python
@dataclass
class FilterState:
    """Контейнер состояния для фильтров"""
    cache: Dict[str, Any] = None
    stats: Dict[str, int] = None
    
    def __post_init__(self):
        if self.cache is None:
            self.cache = {}
        if self.stats is None:
            self.stats = {
                'total_checked': 0,
                'blocked_count': 0
            }

def check_volume_profile_filter(
    df: pd.DataFrame,
    i: int,
    side: str,
    filter_state: Optional[FilterState] = None
) -> Tuple[bool, Optional[str], FilterState]:
    """Возвращает (passed, reason, новое_состояние)"""
    if filter_state is None:
        filter_state = FilterState()
    
    filter_state.stats['total_checked'] += 1
    
    if symbol not in filter_state.cache:
        filter_state.cache[symbol] = calculate_profile(df)
    
    # ... логика фильтра
    
    return passed, reason, filter_state
```

---

## 📚 Примеры правильного и неправильного подхода

### Пример 1: Кэширование данных

**❌ НЕПРАВИЛЬНО:**
```python
# src/utils/cache_manager.py
_price_cache = {}
_symbol_info_cache = {}

def get_symbol_info(symbol: str):
    if symbol in _symbol_info_cache:
        return _symbol_info_cache[symbol]
    
    info = fetch_symbol_info(symbol)
    _symbol_info_cache[symbol] = info
    return info
```

**✅ ПРАВИЛЬНО:**
```python
# src/infrastructure/cache/stateless_cache.py
class StatelessCacheManager:
    def __init__(self):
        self._cache: Dict[str, CacheEntry] = {}
    
    def get(self, key: str) -> Optional[Any]:
        # ...
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        # ...

# src/utils/cache_manager.py
def get_symbol_info(
    symbol: str,
    cache_manager: StatelessCacheManager
) -> Dict[str, Any]:
    cached = cache_manager.get(f"symbol_info:{symbol}")
    if cached:
        return cached
    
    info = fetch_symbol_info(symbol)
    cache_manager.set(f"symbol_info:{symbol}", info, ttl=3600)
    return info
```

### Пример 2: Индикаторы с предыдущими значениями

**❌ НЕПРАВИЛЬНО:**
```python
# src/signals/indicators.py
_prev_rsi = None
_prev_ema_12 = None
_prev_ema_39 = None

def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    global _prev_rsi, _prev_ema_12, _prev_ema_39
    
    for i in range(len(df)):
        rsi = calculate_rsi(df, i, _prev_rsi)
        _prev_rsi = rsi
        
        ema_12 = calculate_ema(df, i, 12, _prev_ema_12)
        _prev_ema_12 = ema_12
        # ...
```

**✅ ПРАВИЛЬНО:**
```python
# src/signals/state_container.py
@dataclass
class IndicatorState:
    prev_rsi: Optional[float] = None
    prev_ema_12: Optional[float] = None
    prev_ema_39: Optional[float] = None

# src/signals/indicators.py
def add_technical_indicators(
    df: pd.DataFrame,
    state: Optional[IndicatorState] = None
) -> Tuple[pd.DataFrame, IndicatorState]:
    if state is None:
        state = IndicatorState()
    
    for i in range(len(df)):
        rsi = calculate_rsi(df, i, state.prev_rsi)
        state.prev_rsi = rsi
        
        ema_12 = calculate_ema(df, i, 12, state.prev_ema_12)
        state.prev_ema_12 = ema_12
        # ...
    
    return df, state
```

### Пример 3: Фильтры с кэшем

**❌ НЕПРАВИЛЬНО:**
```python
# src/signals/filters_volume_vwap.py
_vp_cache = {}
_vp_stats = {}

def check_volume_profile_filter(df, i, side):
    _vp_stats['total_checked'] = _vp_stats.get('total_checked', 0) + 1
    
    cache_key = f"{symbol}:{i}"
    if cache_key not in _vp_cache:
        _vp_cache[cache_key] = calculate_profile(df, i)
    # ...
```

**✅ ПРАВИЛЬНО:**
```python
# src/signals/filters_volume_vwap.py
@dataclass
class FilterState:
    cache: Dict[str, Any] = None
    stats: Dict[str, int] = None
    
    def __post_init__(self):
        if self.cache is None:
            self.cache = {}
        if self.stats is None:
            self.stats = {'total_checked': 0, 'blocked_count': 0}

def check_volume_profile_filter(
    df: pd.DataFrame,
    i: int,
    side: str,
    filter_state: Optional[FilterState] = None
) -> Tuple[bool, Optional[str], FilterState]:
    if filter_state is None:
        filter_state = FilterState()
    
    filter_state.stats['total_checked'] += 1
    
    cache_key = f"{symbol}:{i}"
    if cache_key not in filter_state.cache:
        filter_state.cache[cache_key] = calculate_profile(df, i)
    # ...
    
    return passed, reason, filter_state
```

---

## 🔄 Миграционный гайд

### Шаг 1: Выявить модульные переменные состояния

**Команда для поиска:**
```bash
# Найти все модульные переменные-словари
grep -r "^_[a-z].*=.*{}" src/
grep -r "^[A-Z_].*=.*{}" src/

# Найти использование global
grep -r "global " src/
```

**Примеры найденных проблем:**
- `_vp_cache = {}` в `filters_volume_vwap.py`
- `_price_cache = {}` в `cache_manager.py`
- `SENT_SIGNALS_CACHE = {}` в `config.py`

### Шаг 2: Создать класс-менеджер состояния

**Для кэшей:**
```python
# src/infrastructure/cache/stateless_cache.py
class StatelessCacheManager:
    def __init__(self):
        self._cache: Dict[str, CacheEntry] = {}
    # ...
```

**Для фильтров:**
```python
# src/signals/state_container.py
@dataclass
class FilterState:
    cache: Dict[str, Any] = None
    stats: Dict[str, int] = None
    # ...
```

### Шаг 3: Рефакторить функции

**Было:**
```python
_vp_cache = {}

def check_volume_profile_filter(df, i, side):
    if symbol not in _vp_cache:
        _vp_cache[symbol] = calculate_profile(df)
    # ...
```

**Стало:**
```python
def check_volume_profile_filter(
    df, i, side,
    filter_state: Optional[FilterState] = None
):
    if filter_state is None:
        filter_state = FilterState()
    
    if symbol not in filter_state.cache:
        filter_state.cache[symbol] = calculate_profile(df)
    # ...
    
    return result, filter_state
```

### Шаг 4: Обновить все места использования

**Было:**
```python
# Вызов функции
passed = check_volume_profile_filter(df, i, side)
```

**Стало:**
```python
# Создать экземпляр состояния
filter_state = FilterState()

# Передавать в функции
passed, reason, filter_state = check_volume_profile_filter(
    df, i, side, filter_state
)
```

### Шаг 5: Написать тесты

```python
def test_check_volume_profile_filter_stateless():
    """Тест stateless функции"""
    df = create_test_dataframe()
    filter_state = FilterState()
    
    # Первый вызов
    passed1, reason1, state1 = check_volume_profile_filter(
        df, 0, 'long', filter_state
    )
    
    # Второй вызов с тем же состоянием
    passed2, reason2, state2 = check_volume_profile_filter(
        df, 1, 'long', state1
    )
    
    # Проверяем, что состояние обновляется
    assert state2.stats['total_checked'] == 2
```

---

## 💡 Best Practices

### 1. Использовать dataclasses для состояния

```python
from dataclasses import dataclass, field

@dataclass
class FilterState:
    cache: Dict[str, Any] = field(default_factory=dict)
    stats: Dict[str, int] = field(default_factory=dict)
```

### 2. Всегда возвращать новое состояние

```python
def process_data(data, state: State) -> Tuple[Result, State]:
    # Обработка данных
    new_state = State(
        cache=state.cache.copy(),  # Копируем, если нужно
        stats=state.stats.copy()
    )
    return result, new_state
```

### 3. Использовать Optional для обратной совместимости

```python
def function(
    data: Any,
    state: Optional[State] = None
) -> Tuple[Result, State]:
    if state is None:
        state = State()  # Создаем по умолчанию
    # ...
```

### 4. Документировать состояние

```python
def check_filter(
    df: pd.DataFrame,
    i: int,
    filter_state: Optional[FilterState] = None
) -> Tuple[bool, Optional[str], FilterState]:
    """
    Проверяет фильтр на данных.
    
    Args:
        df: DataFrame с данными
        i: Индекс текущей свечи
        filter_state: Состояние фильтра (создается автоматически, если None)
    
    Returns:
        Tuple[passed, reason, новое_состояние]
    """
    # ...
```

### 5. Использовать type hints

```python
from typing import Dict, Any, Optional, Tuple

def process(
    data: Any,
    state: Optional[State] = None
) -> Tuple[Result, State]:
    # ...
```

---

## ❓ FAQ

### Q: Когда допустимо использовать модульные переменные?

**A:** Только для:
- Конфигурационных констант (`CONFIG_VALUE = 100`)
- Типов и классов (`SignalData = Dict[str, Any]`)
- Singleton для приложения (через явный класс, не модульную переменную)

### Q: Как обрабатывать состояние в async функциях?

**A:** Точно так же - передавать через параметры:

```python
async def async_process(
    data: Any,
    state: Optional[State] = None
) -> Tuple[Result, State]:
    if state is None:
        state = State()
    # ...
    return result, state
```

### Q: Что делать с singleton паттерном?

**A:** Использовать явный класс вместо модульной переменной:

```python
# ❌ НЕПРАВИЛЬНО:
_ai_instances = {}

# ✅ ПРАВИЛЬНО:
class AISystemManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instances = {}
        return cls._instance
```

### Q: Как мигрировать большой код?

**A:** Поэтапно:
1. Создать класс-менеджер состояния
2. Рефакторить одну функцию за раз
3. Обновить места использования
4. Написать тесты
5. Повторить для следующей функции

### Q: Влияет ли это на производительность?

**A:** Нет, наоборот:
- Явное управление состоянием проще оптимизировать
- Кэши работают эффективнее
- Параллелизм безопаснее

---

## 📖 Дополнительные ресурсы

- [Python Best Practices: Stateless Functions](https://docs.python.org/3/tutorial/classes.html)
- [Clean Code: Functions Should Be Stateless](https://clean-code-developer.com/)
- [Functional Programming in Python](https://docs.python.org/3/howto/functional.html)

---

## ✅ Чеклист миграции

- [ ] Выявлены все модульные переменные состояния
- [ ] Созданы классы-менеджеры состояния
- [ ] Рефакторены функции для работы с явным состоянием
- [ ] Обновлены все места использования
- [ ] Написаны unit-тесты
- [ ] Проведены бэктесты (для торговых функций)
- [ ] Обновлена документация
- [ ] Код проверен линтером
- [ ] Деплой на staging
- [ ] Деплой на production

---

**Автор:** Команда ATRA  
**Дата:** 2025-01-XX  
**Версия:** 1.0

