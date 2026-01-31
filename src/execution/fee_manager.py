#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль для получения реальных комиссий через API биржи
"""

import asyncio
import logging
import time
from typing import Optional, Dict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ExchangeFeeManager:
    """Менеджер для получения и кэширования комиссий биржи"""

    def __init__(self, cache_ttl_hours: int = 24):
        """
        Args:
            cache_ttl_hours: Время жизни кэша в часах (по умолчанию 24 часа)
        """
        self.cache_ttl_seconds = cache_ttl_hours * 3600
        self._fee_cache: Dict[str, Dict] = {}  # {cache_key: {fee_rate, timestamp}}
        self._cache_lock = asyncio.Lock()

    def _get_cache_key(self, user_id: str, symbol: str, trade_mode: str) -> str:
        """Генерирует ключ кэша"""
        return f"{user_id}:{symbol}:{trade_mode}"

    async def get_fee_rate(
        self,
        user_id: str,
        symbol: str,
        trade_mode: str = 'futures',
        exchange_adapter=None
    ) -> float:
        """
        Получает реальную комиссию через API или из кэша

        Args:
            user_id: ID пользователя
            symbol: Торговая пара
            trade_mode: Режим торговли ('spot' или 'futures')
            exchange_adapter: Адаптер биржи (опционально)

        Returns:
            Комиссия в виде десятичной дроби (например, 0.0005 для 0.05%)
        """
        cache_key = self._get_cache_key(user_id, symbol, trade_mode)

        # Проверяем кэш
        async with self._cache_lock:
            if cache_key in self._fee_cache:
                cached_data = self._fee_cache[cache_key]
                age = time.time() - cached_data['timestamp']

                if age < self.cache_ttl_seconds:
                    logger.debug(f"✅ Комиссия из кэша для {symbol} ({trade_mode}): {cached_data['fee_rate']}")
                    return cached_data['fee_rate']

        # Получаем через API
        fee_rate = await self._fetch_fee_from_api(user_id, symbol, trade_mode, exchange_adapter)

        # Сохраняем в кэш
        async with self._cache_lock:
            self._fee_cache[cache_key] = {
                'fee_rate': fee_rate,
                'timestamp': time.time()
            }

        return fee_rate

    async def _fetch_fee_from_api(
        self,
        user_id: str,
        symbol: str,
        trade_mode: str,
        exchange_adapter
    ) -> float:
        """
        Получает комиссию через API биржи

        Args:
            user_id: ID пользователя
            symbol: Торговая пара
            trade_mode: Режим торговли
            exchange_adapter: Адаптер биржи

        Returns:
            Комиссия в виде десятичной дроби
        """
        # Fallback на стандартные ставки
        default_fee = 0.001 if trade_mode == 'spot' else 0.0005

        if exchange_adapter is None:
            logger.debug(f"Адаптер биржи не предоставлен, используем стандартную комиссию: {default_fee}")
            return default_fee

        try:
            # Пробуем получить комиссию через API
            # Bitget API метод для получения комиссий
            fee_info = await exchange_adapter.get_trading_fee(symbol, trade_mode)

            if fee_info and isinstance(fee_info, dict):
                # Приоритет: takerFee > makerFee > default
                fee_rate = (
                    fee_info.get('takerFee') or
                    fee_info.get('makerFee') or
                    fee_info.get('feeRate') or
                    default_fee
                )

                # Конвертируем проценты в десятичную дробь если нужно
                if fee_rate > 1.0:
                    fee_rate = fee_rate / 100.0

                logger.info(f"✅ Получена комиссия через API для {symbol} ({trade_mode}): {fee_rate}")
                return float(fee_rate)

        except AttributeError:
            # Метод get_trading_fee не реализован в адаптере
            logger.debug(f"Метод get_trading_fee не реализован, используем стандартную комиссию: {default_fee}")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка получения комиссии через API для {symbol}: {e}")

        return default_fee

    def clear_cache(self, user_id: Optional[str] = None, symbol: Optional[str] = None):
        """
        Очищает кэш комиссий

        Args:
            user_id: ID пользователя (опционально, для очистки конкретного пользователя)
            symbol: Торговая пара (опционально, для очистки конкретной пары)
        """
        if user_id is None and symbol is None:
            # Очищаем весь кэш
            self._fee_cache.clear()
            logger.info("✅ Кэш комиссий полностью очищен")
        else:
            # Очищаем частично
            keys_to_remove = []
            for key in self._fee_cache.keys():
                if user_id and user_id not in key:
                    continue
                if symbol and symbol not in key:
                    continue
                keys_to_remove.append(key)

            for key in keys_to_remove:
                del self._fee_cache[key]

            logger.info(f"✅ Очищено {len(keys_to_remove)} записей из кэша комиссий")

    def get_cache_stats(self) -> Dict:
        """Возвращает статистику кэша"""
        total_entries = len(self._fee_cache)
        now = time.time()
        expired = sum(
            1 for data in self._fee_cache.values()
            if (now - data['timestamp']) >= self.cache_ttl_seconds
        )

        return {
            'total_entries': total_entries,
            'valid_entries': total_entries - expired,
            'expired_entries': expired,
            'cache_ttl_hours': self.cache_ttl_seconds / 3600
        }


# Глобальный экземпляр менеджера
_fee_manager_instance: Optional[ExchangeFeeManager] = None


def get_fee_manager() -> ExchangeFeeManager:
    """Получает глобальный экземпляр менеджера комиссий"""
    global _fee_manager_instance
    if _fee_manager_instance is None:
        _fee_manager_instance = ExchangeFeeManager()
    return _fee_manager_instance


async def get_real_fee_rate(
    user_id: str,
    symbol: str,
    trade_mode: str = 'futures',
    exchange_adapter=None
) -> float:
    """
    Удобная функция для получения реальной комиссии

    Args:
        user_id: ID пользователя
        symbol: Торговая пара
        trade_mode: Режим торговли
        exchange_adapter: Адаптер биржи

    Returns:
        Комиссия в виде десятичной дроби
    """
    fee_manager = get_fee_manager()
    return await fee_manager.get_fee_rate(user_id, symbol, trade_mode, exchange_adapter)
