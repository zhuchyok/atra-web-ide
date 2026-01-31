#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Адаптивные RSI уровни на основе волатильности символа
Оптимизировано для внутридневной торговли на крипторынке
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def calculate_volatility(df: pd.DataFrame, i: int, method: str = "atr") -> float:
    """
    Рассчитывает волатильность символа
    
    Args:
        df: DataFrame с данными
        i: Индекс текущей свечи
        method: Метод расчета ('atr' или 'std')
    
    Returns:
        Волатильность как процент (0.05 = 5%)
    """
    try:
        if i < 14:
            return 0.05  # Средняя волатильность по умолчанию
        
        if method == "atr" and 'atr' in df.columns:
            # Используем ATR если доступен
            atr = df.iloc[i]['atr']
            price = df.iloc[i]['close']
            if price > 0:
                volatility = (atr / price) * 100
                return volatility / 100  # Конвертируем в долю
        elif method == "std":
            # Используем стандартное отклонение цен за последние 20 свечей
            lookback = min(20, i + 1)
            prices = df.iloc[i - lookback + 1:i + 1]['close'].values
            if len(prices) > 1:
                price_std = np.std(prices)
                price_mean = np.mean(prices)
                if price_mean > 0:
                    volatility = (price_std / price_mean) * 100
                    return volatility / 100  # Конвертируем в долю
        
        # Fallback: используем размах свечей
        lookback = min(14, i + 1)
        highs = df.iloc[i - lookback + 1:i + 1]['high'].values
        lows = df.iloc[i - lookback + 1:i + 1]['low'].values
        closes = df.iloc[i - lookback + 1:i + 1]['close'].values
        
        if len(closes) > 0:
            avg_range = np.mean(highs - lows)
            avg_price = np.mean(closes)
            if avg_price > 0:
                volatility = (avg_range / avg_price) * 100
                return volatility / 100
        
        return 0.05  # Средняя волатильность по умолчанию
        
    except Exception as e:
        logger.debug(f"Ошибка расчета волатильности: {e}")
        return 0.05  # Средняя волатильность по умолчанию


def get_adaptive_rsi_levels(
    symbol: str,
    df: pd.DataFrame,
    i: int,
    base_overbought: float = 70,
    base_oversold: float = 30,
    base_period: int = 14
) -> Dict[str, float]:
    """
    Адаптивные уровни RSI на основе волатильности символа
    
    Args:
        symbol: Торговый символ
        df: DataFrame с данными
        i: Индекс текущей свечи
        base_overbought: Базовый уровень перекупленности
        base_oversold: Базовый уровень перепроданности
        base_period: Базовый период RSI
    
    Returns:
        Словарь с адаптивными параметрами RSI
    """
    try:
        # Рассчитываем волатильность
        volatility = calculate_volatility(df, i)
        
        # Определяем группу волатильности
        if symbol in ["BTCUSDT", "ETHUSDT"]:
            # BTC и ETH менее волатильны - используем более строгие уровни
            if volatility > 0.08:  # Высокая волатильность даже для BTC/ETH
                return {
                    'overbought': 75,
                    'oversold': 25,
                    'period': 12,
                    'volatility': volatility,
                    'group': 'high_volatility_major'
                }
            elif volatility > 0.04:  # Средняя волатильность
                return {
                    'overbought': 72,
                    'oversold': 28,
                    'period': 14,
                    'volatility': volatility,
                    'group': 'medium_volatility_major'
                }
            else:  # Низкая волатильность
                return {
                    'overbought': 70,
                    'oversold': 30,
                    'period': 16,
                    'volatility': volatility,
                    'group': 'low_volatility_major'
                }
        else:
            # Альткоины более волатильны - используем более мягкие уровни
            if volatility > 0.10:  # Высокая волатильность (>10%)
                return {
                    'overbought': 75,
                    'oversold': 25,
                    'period': 12,  # Более чувствительный
                    'volatility': volatility,
                    'group': 'high_volatility_alt'
                }
            elif volatility > 0.05:  # Средняя волатильность (5-10%)
                return {
                    'overbought': 72,
                    'oversold': 28,
                    'period': 14,
                    'volatility': volatility,
                    'group': 'medium_volatility_alt'
                }
            else:  # Низкая волатильность (<5%)
                return {
                    'overbought': 70,
                    'oversold': 30,
                    'period': 16,  # Меньше шума
                    'volatility': volatility,
                    'group': 'low_volatility_alt'
                }
                
    except Exception as e:
        logger.debug(f"Ошибка расчета адаптивных RSI уровней для {symbol}: {e}")
        # Возвращаем базовые уровни при ошибке
        return {
            'overbought': base_overbought,
            'oversold': base_oversold,
            'period': base_period,
            'volatility': 0.05,
            'group': 'default'
        }


def should_use_adaptive_rsi(symbol: str) -> bool:
    """
    Определяет, нужно ли использовать адаптивные RSI уровни для символа
    
    Args:
        symbol: Торговый символ
    
    Returns:
        True если нужно использовать адаптивные уровни
    """
    # Используем адаптивные уровни для всех символов
    # Можно добавить исключения для стейблкоинов
    stablecoins = ["USDTUSDT", "USDCUSDT", "BUSDUSDT", "FDUSDUSDT"]
    return symbol not in stablecoins

