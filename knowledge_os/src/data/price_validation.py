#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль валидации цен на аномалии
"""

import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def validate_price(
    price: float,
    symbol: str,
    entry_price: float,
    max_deviation_pct: float = 50.0,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None
) -> Tuple[bool, Optional[str]]:
    """
    Валидация цены на аномалии

    Args:
        price: Проверяемая цена
        symbol: Торговая пара
        entry_price: Цена входа (для проверки отклонения)
        max_deviation_pct: Максимальное отклонение от цены входа в процентах
        min_price: Минимальная допустимая цена (опционально)
        max_price: Максимальная допустимая цена (опционально)

    Returns:
        Tuple[bool, Optional[str]]: (валидна ли цена, сообщение об ошибке)
    """
    try:
        # Проверка на положительное значение
        if price <= 0:
            return False, f"Цена {symbol} не может быть <= 0: {price}"

        # Проверка на разумные пределы от цены входа
        if entry_price > 0:
            deviation_pct = abs(price - entry_price) / entry_price * 100.0
            if deviation_pct > max_deviation_pct:
                error_msg = (
                    f"⚠️ Аномальная цена {symbol}: {price:.8f} "
                    f"(вход: {entry_price:.8f}, отклонение: {deviation_pct:.2f}%)"
                )
                logger.warning(error_msg)
                return False, error_msg

        # Проверка на минимальную цену
        if min_price is not None and price < min_price:
            return False, f"Цена {symbol} ниже минимума: {price} < {min_price}"

        # Проверка на максимальную цену
        if max_price is not None and price > max_price:
            return False, f"Цена {symbol} выше максимума: {price} > {max_price}"

        return True, None

    except (ValueError, TypeError, ZeroDivisionError) as e:
        error_msg = f"Ошибка валидации цены {symbol}: {e}"
        logger.error(error_msg)
        return False, error_msg


def validate_spread(
    bid_price: float,
    ask_price: float,
    symbol: str,
    max_spread_pct: float = 1.0
) -> Tuple[bool, Optional[str]]:
    """
    Валидация спреда bid/ask

    Args:
        bid_price: Цена покупки (bid)
        ask_price: Цена продажи (ask)
        symbol: Торговая пара
        max_spread_pct: Максимальный допустимый спред в процентах

    Returns:
        Tuple[bool, Optional[str]]: (валиден ли спред, сообщение об ошибке)
    """
    try:
        if bid_price <= 0 or ask_price <= 0:
            return False, f"Некорректные bid/ask для {symbol}: bid={bid_price}, ask={ask_price}"

        if ask_price <= bid_price:
            return False, f"Некорректный спред для {symbol}: ask ({ask_price}) <= bid ({bid_price})"

        spread_pct = (ask_price - bid_price) / bid_price * 100.0

        if spread_pct > max_spread_pct:
            error_msg = (
                f"⚠️ Слишком большой спред {symbol}: {spread_pct:.2f}% "
                f"(bid: {bid_price}, ask: {ask_price})"
            )
            logger.warning(error_msg)
            return False, error_msg

        return True, None

    except (ValueError, TypeError, ZeroDivisionError) as e:
        error_msg = f"Ошибка валидации спреда {symbol}: {e}"
        logger.error(error_msg)
        return False, error_msg


async def get_validated_price(
    symbol: str,
    entry_price: float,
    price_func,
    max_deviation_pct: float = 50.0
) -> Optional[float]:
    """
    Получает и валидирует цену

    Args:
        symbol: Торговая пара
        entry_price: Цена входа
        price_func: Асинхронная функция для получения цены
        max_deviation_pct: Максимальное отклонение от цены входа

    Returns:
        Валидная цена или None
    """
    try:
        price = await price_func(symbol)
        if price is None:
            return None

        is_valid, error_msg = validate_price(price, symbol, entry_price, max_deviation_pct)
        if not is_valid:
            logger.warning(f"Цена не прошла валидацию: {error_msg}")
            return None

        return price

    except Exception as e:
        logger.error(f"Ошибка получения валидированной цены для {symbol}: {e}")
        return None
