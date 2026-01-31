"""
Быстрая сериализация данных для ATRA
Использует MessagePack (2-3x быстрее JSON) и Parquet (10-100x быстрее pickle)
"""

import logging
from typing import Any, Optional
import json

logger = logging.getLogger(__name__)

# Попытка импорта MessagePack
try:
    import msgpack
    MSGPACK_AVAILABLE = True
except ImportError:
    MSGPACK_AVAILABLE = False
    msgpack = None

# Попытка импорта PyArrow для Parquet
try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    PYARROW_AVAILABLE = True
except ImportError:
    PYARROW_AVAILABLE = False
    pa = None
    pq = None


def serialize_fast(data: Any) -> bytes:
    """
    Быстрая сериализация с MessagePack (2-3x быстрее JSON)
    
    Args:
        data: Данные для сериализации
        
    Returns:
        Сериализованные данные в bytes
    """
    if MSGPACK_AVAILABLE:
        try:
            return msgpack.packb(data, use_bin_type=True)
        except Exception as e:
            logger.warning("Ошибка MessagePack сериализации, fallback на JSON: %s", e)
    
    # Fallback на JSON
    return json.dumps(data, ensure_ascii=False).encode('utf-8')


def deserialize_fast(data: bytes) -> Any:
    """
    Быстрая десериализация с MessagePack
    
    Args:
        data: Сериализованные данные в bytes
        
    Returns:
        Десериализованные данные
    """
    if MSGPACK_AVAILABLE:
        try:
            return msgpack.unpackb(data, raw=False)
        except Exception as e:
            logger.warning("Ошибка MessagePack десериализации, fallback на JSON: %s", e)
    
    # Fallback на JSON
    return json.loads(data.decode('utf-8'))


def save_dataframe_fast(df: Any, path: str, compression: str = 'snappy') -> bool:
    """
    Сохранение DataFrame в Parquet (10-100x быстрее pickle)
    
    Args:
        df: Pandas DataFrame
        path: Путь для сохранения
        compression: Тип сжатия ('snappy', 'gzip', 'brotli', 'zstd')
        
    Returns:
        True при успехе, False при ошибке
    """
    if not PYARROW_AVAILABLE:
        logger.warning("PyArrow недоступен, используйте pandas.to_pickle()")
        return False
    
    try:
        import pandas as pd
        if not isinstance(df, pd.DataFrame):
            logger.error("Объект не является pandas DataFrame")
            return False
        
        df.to_parquet(path, compression=compression, engine='pyarrow')
        logger.debug("DataFrame сохранен в Parquet: %s", path)
        return True
    except Exception as e:
        logger.error("Ошибка сохранения DataFrame в Parquet: %s", e)
        return False


def load_dataframe_fast(path: str) -> Optional[Any]:
    """
    Загрузка DataFrame из Parquet
    
    Args:
        path: Путь к файлу Parquet
        
    Returns:
        Pandas DataFrame или None при ошибке
    """
    if not PYARROW_AVAILABLE:
        logger.warning("PyArrow недоступен, используйте pandas.read_pickle()")
        return None
    
    try:
        import pandas as pd
        df = pd.read_parquet(path, engine='pyarrow')
        logger.debug("DataFrame загружен из Parquet: %s", path)
        return df
    except Exception as e:
        logger.error("Ошибка загрузки DataFrame из Parquet: %s", e)
        return None

