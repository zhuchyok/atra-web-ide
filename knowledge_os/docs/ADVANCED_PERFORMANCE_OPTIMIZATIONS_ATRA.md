# Дополнительные оптимизации производительности для ATRA и корпорации агентов

## Обзор

После реализации базовых оптимизаций (SQLite, Rust PGO, Python uvloop) можно дополнительно ускорить систему на 5-100x через:
- Векторизацию вычислений
- JIT компиляцию
- Оптимизацию сериализации
- Распределенное кэширование
- Параллельную обработку

## 1. Векторизация технических индикаторов

### Текущая проблема

**Файл:** `src/data/technical.py`

**Текущий код (строки 39-50):**
```python
gains = []
losses = []

# Расчет изменений цен
for i in range(1, len(prices)):
    change = prices[i] - prices[i-1]
    if change > 0:
        gains.append(change)
        losses.append(0)
    else:
        gains.append(0)
        losses.append(abs(change))
```

**Проблема:** Python циклы медленные, особенно для больших массивов

### Решение: Векторизация с NumPy

**Оптимизированный код:**
```python
import numpy as np

@staticmethod
def calculate_rsi_vectorized(prices: List[float], period: int = 14) -> Optional[float]:
    """Векторизованный расчет RSI с NumPy"""
    try:
        if len(prices) < period + 1:
            return None
        
        # Конвертируем в numpy array
        prices_arr = np.array(prices, dtype=np.float64)
        
        # Векторизованный расчет изменений
        deltas = np.diff(prices_arr)
        
        # Векторизованное разделение на gains и losses
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        # Расчет средних за период (векторизованно)
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return round(float(rsi), 2)
    except Exception as e:
        logger.error(f"Ошибка расчета RSI: {e}")
        return None
```

**Ожидаемый эффект:** Ускорение на 10-50x

## 2. JIT компиляция с Numba

### Применение

**Файл:** `src/data/technical.py`

**Оптимизированный код:**
```python
try:
    from numba import jit
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    def jit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

@jit(nopython=True, cache=True)
def _calculate_rsi_numba(prices_arr: np.ndarray, period: int) -> float:
    """JIT-компилированная функция расчета RSI"""
    n = len(prices_arr)
    if n < period + 1:
        return np.nan
    
    deltas = np.diff(prices_arr)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))

@staticmethod
def calculate_rsi_numba(prices: List[float], period: int = 14) -> Optional[float]:
    """RSI с JIT компиляцией"""
    if not NUMBA_AVAILABLE:
        return TechnicalIndicators.calculate_rsi_vectorized(prices, period)
    
    try:
        prices_arr = np.array(prices, dtype=np.float64)
        rsi = _calculate_rsi_numba(prices_arr, period)
        if np.isnan(rsi):
            return None
        return round(float(rsi), 2)
    except Exception as e:
        logger.error(f"Ошибка расчета RSI (Numba): {e}")
        return None
```

**Ожидаемый эффект:** Ускорение на 10-100x для численных вычислений

## 3. Polars вместо Pandas для больших данных

### Применение

**Новый модуль:** `src/data/polars_utils.py`

```python
"""
Утилиты для работы с Polars (быстрая альтернатива Pandas)
"""

try:
    import polars as pl
    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False
    pl = None

def pandas_to_polars(df: pd.DataFrame) -> 'pl.DataFrame':
    """Конвертация Pandas DataFrame в Polars"""
    if not POLARS_AVAILABLE:
        return df
    
    return pl.from_pandas(df)

def polars_to_pandas(df: 'pl.DataFrame') -> pd.DataFrame:
    """Конвертация Polars DataFrame в Pandas"""
    if not POLARS_AVAILABLE:
        return df
    
    return df.to_pandas()

def calculate_indicators_polars(df: 'pl.DataFrame') -> 'pl.DataFrame':
    """Расчет индикаторов с Polars (5-30x быстрее Pandas)"""
    if not POLARS_AVAILABLE:
        raise ImportError("Polars not available")
    
    return df.with_columns([
        # EMA
        pl.col("close").ewm_mean(span=7).alias("ema7"),
        pl.col("close").ewm_mean(span=25).alias("ema25"),
        
        # RSI
        (100 - (100 / (1 + pl.col("close").pct_change().rolling_mean(14)))).alias("rsi"),
        
        # Volume ratio
        (pl.col("volume") / pl.col("volume").rolling_mean(20)).alias("volume_ratio"),
        
        # Volatility
        (pl.col("close").pct_change().rolling_std(20) * 100).alias("volatility"),
    ])
```

**Ожидаемый эффект:** Ускорение на 5-30x для обработки данных

## 4. Оптимизация сериализации

### MessagePack вместо JSON

**Применение:**
```python
try:
    import msgpack
    MSGPACK_AVAILABLE = True
except ImportError:
    MSGPACK_AVAILABLE = False

def serialize_fast(data: Any) -> bytes:
    """Быстрая сериализация с MessagePack (2-3x быстрее JSON)"""
    if MSGPACK_AVAILABLE:
        return msgpack.packb(data, use_bin_type=True)
    else:
        import json
        return json.dumps(data).encode('utf-8')

def deserialize_fast(data: bytes) -> Any:
    """Быстрая десериализация с MessagePack"""
    if MSGPACK_AVAILABLE:
        return msgpack.unpackb(data, raw=False)
    else:
        import json
        return json.loads(data.decode('utf-8'))
```

### Parquet для DataFrame

**Применение:**
```python
def save_dataframe_fast(df: pd.DataFrame, path: str):
    """Сохранение DataFrame в Parquet (10-100x быстрее pickle)"""
    df.to_parquet(path, compression='snappy', engine='pyarrow')

def load_dataframe_fast(path: str) -> pd.DataFrame:
    """Загрузка DataFrame из Parquet"""
    return pd.read_parquet(path, engine='pyarrow')
```

**Ожидаемый эффект:** Ускорение сериализации на 2-100x

## 5. Распределенное кэширование с Redis

### Применение

**Новый модуль:** `src/infrastructure/cache/redis_cache.py`

```python
"""
Распределенное кэширование с Redis для корпорации агентов
"""

try:
    import redis
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None
    aioredis = None

class RedisCache:
    """Распределенный кэш через Redis"""
    
    def __init__(self, host: str = 'localhost', port: int = 6379, db: int = 0):
        if not REDIS_AVAILABLE:
            raise ImportError("Redis not available")
        
        self.redis_client = redis.Redis(host=host, port=port, db=db, decode_responses=True)
        self.async_client = None
    
    async def get_async_client(self):
        """Получить async клиент Redis"""
        if self.async_client is None:
            self.async_client = await aioredis.from_url(f"redis://localhost:6379/{0}")
        return self.async_client
    
    def set(self, key: str, value: Any, ttl: int = 3600):
        """Установить значение в кэш"""
        import msgpack
        serialized = msgpack.packb(value, use_bin_type=True)
        self.redis_client.setex(key, ttl, serialized)
    
    def get(self, key: str) -> Optional[Any]:
        """Получить значение из кэша"""
        data = self.redis_client.get(key)
        if data is None:
            return None
        
        import msgpack
        return msgpack.unpackb(data, raw=False)
    
    async def set_async(self, key: str, value: Any, ttl: int = 3600):
        """Асинхронная установка значения"""
        client = await self.get_async_client()
        import msgpack
        serialized = msgpack.packb(value, use_bin_type=True)
        await client.setex(key, ttl, serialized)
    
    async def get_async(self, key: str) -> Optional[Any]:
        """Асинхронное получение значения"""
        client = await self.get_async_client()
        data = await client.get(key)
        if data is None:
            return None
        
        import msgpack
        return msgpack.unpackb(data, raw=False)
```

**Ожидаемый эффект:** Снижение нагрузки на БД на 50-90%

## 6. Параллельная обработка с Ray

### Применение

**Новый модуль:** `src/optimization/ray_optimizer.py`

```python
"""
Распределенная обработка данных с Ray
"""

try:
    import ray
    RAY_AVAILABLE = True
except ImportError:
    RAY_AVAILABLE = False
    ray = None

@ray.remote
def process_symbol_remote(symbol: str, data: pd.DataFrame) -> Dict[str, Any]:
    """Удаленная обработка символа"""
    # Обработка данных
    result = calculate_indicators(data)
    return {'symbol': symbol, 'result': result}

class RayOptimizer:
    """Оптимизатор с использованием Ray"""
    
    def __init__(self):
        if RAY_AVAILABLE:
            if not ray.is_initialized():
                ray.init(num_cpus=4)
    
    def process_symbols_parallel(self, symbols: List[str], data_dict: Dict[str, pd.DataFrame]) -> List[Dict]:
        """Параллельная обработка символов"""
        if not RAY_AVAILABLE:
            # Fallback на последовательную обработку
            return [process_symbol(s, data_dict[s]) for s in symbols]
        
        # Распределенная обработка
        futures = [process_symbol_remote.remote(s, data_dict[s]) for s in symbols]
        results = ray.get(futures)
        return results
```

**Ожидаемый эффект:** Ускорение на 4-20x для больших датасетов

## 7. Memory mapping для больших данных

### Применение

```python
import mmap
import numpy as np

def load_data_mmap(filepath: str, dtype=np.float64, shape: tuple) -> np.ndarray:
    """Загрузка данных через memory mapping"""
    with open(filepath, 'r+b') as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        data = np.frombuffer(mm, dtype=dtype).reshape(shape)
        return data
```

**Ожидаемый эффект:** Снижение потребления памяти на 50-80%

## 8. Batch processing для массовых операций

### Применение в Database

**Файл:** `src/database/db.py`

```python
def execute_batch(self, queries: List[Tuple[str, tuple]], is_write: bool = True):
    """Выполнение batch операций"""
    try:
        with self._lock:
            self.conn.execute("BEGIN TRANSACTION")
            for query, params in queries:
                self.cursor.execute(query, params)
            if is_write:
                self.conn.commit()
            else:
                self.conn.rollback()
            return True
    except Exception as e:
        self.conn.rollback()
        logger.error(f"Ошибка batch операции: {e}")
        return False

def executemany_optimized(self, query: str, params_list: List[tuple]):
    """Оптимизированный executemany с отключением индексов"""
    try:
        with self._lock:
            # Отключаем индексы для массовой вставки
            self.conn.execute("PRAGMA synchronous=OFF")
            self.conn.execute("BEGIN TRANSACTION")
            
            self.cursor.executemany(query, params_list)
            self.conn.commit()
            
            # Включаем обратно
            self.conn.execute("PRAGMA synchronous=NORMAL")
            return True
    except Exception as e:
        self.conn.rollback()
        self.conn.execute("PRAGMA synchronous=NORMAL")
        logger.error(f"Ошибка executemany: {e}")
        return False
```

**Ожидаемый эффект:** Ускорение на 50-90% для массовых операций

## 9. Shared memory для агентов

### Применение

**Новый модуль:** `src/infrastructure/shared_memory/agent_shared_memory.py`

```python
"""
Shared memory для обмена данными между агентами
"""

import mmap
import struct
import json
from typing import Dict, Any

class AgentSharedMemory:
    """Shared memory для координации агентов"""
    
    def __init__(self, size_mb: int = 100):
        self.size = size_mb * 1024 * 1024
        self.mmap_file = None
        self.lock = threading.Lock()
    
    def write_data(self, key: str, data: Any):
        """Запись данных в shared memory"""
        with self.lock:
            # Сериализация
            serialized = json.dumps(data).encode('utf-8')
            # Запись в mmap
            # ...
    
    def read_data(self, key: str) -> Optional[Any]:
        """Чтение данных из shared memory"""
        with self.lock:
            # Чтение из mmap
            # Десериализация
            # ...
```

**Ожидаемый эффект:** Снижение латентности на 90-99%

## 10. Оптимизация работы с DataFrame

### Использование категориальных данных

```python
def optimize_dataframe_types(df: pd.DataFrame) -> pd.DataFrame:
    """Оптимизация типов данных в DataFrame"""
    # Конвертация строк в категории
    for col in df.select_dtypes(include=['object']).columns:
        if df[col].nunique() < len(df) * 0.5:  # Если уникальных значений < 50%
            df[col] = df[col].astype('category')
    
    # Оптимизация численных типов
    for col in df.select_dtypes(include=['int64']).columns:
        df[col] = pd.to_numeric(df[col], downcast='integer')
    
    for col in df.select_dtypes(include=['float64']).columns:
        df[col] = pd.to_numeric(df[col], downcast='float')
    
    return df
```

**Ожидаемый эффект:** Снижение потребления памяти на 30-70%

## План реализации

### Этап 1: Быстрые победы (1 неделя)
1. Векторизация технических индикаторов с NumPy
2. JIT компиляция с Numba
3. MessagePack для сериализации
4. Batch processing в Database

### Этап 2: Средние оптимизации (2 недели)
5. Polars для больших DataFrame
6. Parquet для сохранения данных
7. Prepared statements в Database
8. Оптимизация типов DataFrame

### Этап 3: Продвинутые оптимизации (2-3 недели)
9. Redis кэширование
10. Ray для распределенной обработки
11. Shared memory для агентов
12. Memory mapping

## Ожидаемые итоговые результаты

### Производительность:
- **Расчеты индикаторов:** 10-100x быстрее (Numba + векторизация)
- **Обработка данных:** 5-30x быстрее (Polars)
- **Сериализация:** 2-100x быстрее (MessagePack/Parquet)
- **Массовые операции:** 50-90% быстрее (Batch processing)
- **Обмен данными агентов:** 90-99% снижение латентности (Shared memory)

### Память:
- **Потребление памяти:** 30-80% снижение (Polars, оптимизация типов)
- **Кэширование:** 50-90% снижение нагрузки на БД (Redis)

### Масштабируемость:
- **Распределенная обработка:** 4-20x ускорение (Ray)
- **Параллелизм агентов:** через shared memory

## Зависимости

### Новые зависимости:
```txt
# Быстрые вычисления
numba>=0.58.0  # JIT компиляция
numpy>=1.24.0  # Векторизация (уже есть)

# Быстрая обработка данных
polars>=0.19.0  # Альтернатива Pandas
pyarrow>=14.0.0  # Parquet поддержка

# Быстрая сериализация
msgpack>=1.0.0  # MessagePack
orjson>=3.9.0  # Быстрый JSON (опционально)

# Распределенное кэширование
redis>=5.0.0  # Redis клиент
hiredis>=2.2.0  # Быстрый парсер Redis

# Распределенная обработка
ray>=2.8.0  # Распределенная обработка (опционально)
```

## Критерии успеха

### Метрики производительности:
- Расчет RSI для 1000 свечей: < 1ms (сейчас ~10-50ms)
- Обработка DataFrame 1M строк: < 1 сек (сейчас ~5-30 сек)
- Сериализация 1MB данных: < 10ms (сейчас ~50-200ms)
- Batch insert 10K записей: < 100ms (сейчас ~1-5 сек)

### Метрики памяти:
- Потребление памяти для 1M строк: < 100MB (сейчас ~300-500MB)
- Кэш hit rate: > 80%

---

**Дата создания:** 2025-01-09  
**Статус:** Готов к реализации

