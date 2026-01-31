"""
Параллельная обработка символов и пользователей.
Использует asyncio.gather для одновременной обработки множественных задач.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable, TypeVar, Tuple
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')


async def process_symbols_parallel(
    symbols: List[str],
    process_func: Callable[[str], Any],
    max_concurrent: int = 10
) -> Dict[str, Any]:
    """
    Параллельная обработка символов
    Ускорение на 5-10x для множественных символов
    
    Args:
        symbols: Список символов для обработки
        process_func: Асинхронная функция обработки символа
        max_concurrent: Максимальное количество одновременных задач
        
    Returns:
        Словарь {symbol: result}
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    results = {}
    
    async def process_with_semaphore(symbol: str):
        async with semaphore:
            try:
                result = await process_func(symbol)
                return symbol, result
            except Exception as e:
                logger.warning("Ошибка обработки символа %s: %s", symbol, e)
                return symbol, None
    
    # Запускаем все задачи параллельно
    tasks = [process_with_semaphore(symbol) for symbol in symbols]
    completed = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Собираем результаты
    for item in completed:
        if isinstance(item, Exception):
            logger.error("Исключение при обработке: %s", item)
            continue
        if isinstance(item, tuple) and len(item) == 2:
            symbol, result = item
            results[symbol] = result
    
    return results


async def process_users_parallel(
    user_ids: List[str],
    process_func: Callable[[str], Any],
    max_concurrent: int = 5
) -> Dict[str, Any]:
    """
    Параллельная обработка пользователей
    Ускорение на 3-5x для множественных пользователей
    
    Args:
        user_ids: Список ID пользователей
        process_func: Асинхронная функция обработки пользователя
        max_concurrent: Максимальное количество одновременных задач
        
    Returns:
        Словарь {user_id: result}
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    results = {}
    
    async def process_with_semaphore(user_id: str):
        async with semaphore:
            try:
                result = await process_func(user_id)
                return user_id, result
            except Exception as e:
                logger.warning("Ошибка обработки пользователя %s: %s", user_id, e)
                return user_id, None
    
    # Запускаем все задачи параллельно
    tasks = [process_with_semaphore(user_id) for user_id in user_ids]
    completed = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Собираем результаты
    for item in completed:
        if isinstance(item, Exception):
            logger.error("Исключение при обработке: %s", item)
            continue
        if isinstance(item, tuple) and len(item) == 2:
            user_id, result = item
            results[user_id] = result
    
    return results


async def process_symbol_user_pairs_parallel(
    symbol_user_pairs: List[Tuple[str, str]],
    process_func: Callable[[str, str], Any],
    max_concurrent: int = 20
) -> Dict[Tuple[str, str], Any]:
    """
    Параллельная обработка пар (символ, пользователь)
    Ускорение на 10-20x для множественных пар
    
    Args:
        symbol_user_pairs: Список кортежей (symbol, user_id)
        process_func: Асинхронная функция обработки пары
        max_concurrent: Максимальное количество одновременных задач
        
    Returns:
        Словарь {(symbol, user_id): result}
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    results = {}
    
    async def process_with_semaphore(symbol: str, user_id: str):
        async with semaphore:
            try:
                result = await process_func(symbol, user_id)
                return (symbol, user_id), result
            except Exception as e:
                logger.warning("Ошибка обработки пары (%s, %s): %s", symbol, user_id, e)
                return (symbol, user_id), None
    
    # Запускаем все задачи параллельно
    tasks = [process_with_semaphore(symbol, user_id) for symbol, user_id in symbol_user_pairs]
    completed = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Собираем результаты
    for item in completed:
        if isinstance(item, Exception):
            logger.error("Исключение при обработке: %s", item)
            continue
        if isinstance(item, tuple) and len(item) == 2:
            key, result = item
            results[key] = result
    
    return results


def parallelize(func: Callable) -> Callable:
    """
    Декоратор для автоматической параллелизации функции
    
    Usage:
        @parallelize
        async def process_item(item):
            # обработка
            return result
    """
    @wraps(func)
    async def wrapper(items: List[T], *args, **kwargs) -> Dict[T, Any]:
        """
        Параллельно обрабатывает список элементов
        """
        max_concurrent = kwargs.pop('max_concurrent', 10)
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_semaphore(item: T):
            async with semaphore:
                try:
                    result = await func(item, *args, **kwargs)
                    return item, result
                except Exception as e:
                    logger.warning("Ошибка обработки %s: %s", item, e)
                    return item, None
        
        tasks = [process_with_semaphore(item) for item in items]
        completed = await asyncio.gather(*tasks, return_exceptions=True)
        
        results = {}
        for item in completed:
            if isinstance(item, Exception):
                logger.error("Исключение: %s", item)
                continue
            if isinstance(item, tuple) and len(item) == 2:
                key, result = item
                results[key] = result
        
        return results
    
    return wrapper

