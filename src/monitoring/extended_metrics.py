#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль для расширенных метрик производительности
"""

import logging
from typing import List, Optional, Dict
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def calculate_var(
    returns: pd.Series,
    confidence: float = 0.95
) -> float:
    """
    Value at Risk (VaR) - максимальный ожидаемый убыток с заданной вероятностью

    Args:
        returns: Серия доходностей
        confidence: Уровень доверия (по умолчанию 0.95 = 95%)

    Returns:
        VaR в виде десятичной дроби
    """
    try:
        if len(returns) == 0:
            return 0.0

        # VaR = процентиль отрицательных доходностей
        var = returns.quantile(1 - confidence)
        
        # Возвращаем абсолютное значение (VaR обычно отрицательный)
        return abs(float(var))

    except Exception as e:
        logger.error(f"Ошибка расчета VaR: {e}")
        return 0.0


def calculate_cvar(
    returns: pd.Series,
    confidence: float = 0.95
) -> float:
    """
    Conditional Value at Risk (CVaR) / Expected Shortfall
    Средний убыток при превышении VaR

    Args:
        returns: Серия доходностей
        confidence: Уровень доверия (по умолчанию 0.95 = 95%)

    Returns:
        CVaR в виде десятичной дроби
    """
    try:
        if len(returns) == 0:
            return 0.0

        # Сначала получаем VaR
        var = calculate_var(returns, confidence)

        # CVaR = среднее значение всех доходностей <= -VaR
        # (берем отрицательные значения)
        var_threshold = -var
        cvar_returns = returns[returns <= var_threshold]

        if len(cvar_returns) == 0:
            return var  # Если нет таких значений, возвращаем VaR

        cvar = abs(float(cvar_returns.mean()))
        return cvar

    except Exception as e:
        logger.error(f"Ошибка расчета CVaR: {e}")
        return 0.0


def calculate_calmar_ratio(
    annual_return: float,
    max_drawdown: float
) -> float:
    """
    Calmar Ratio = Annual Return / Max Drawdown

    Args:
        annual_return: Годовая доходность в виде десятичной дроби
        max_drawdown: Максимальная просадка в виде десятичной дроби

    Returns:
        Calmar Ratio
    """
    try:
        if max_drawdown == 0:
            return 0.0

        calmar = annual_return / abs(max_drawdown)
        return float(calmar)

    except (ValueError, TypeError, ZeroDivisionError) as e:
        logger.error(f"Ошибка расчета Calmar Ratio: {e}")
        return 0.0


def calculate_extended_metrics(
    returns: List[float],
    max_drawdown: float,
    annual_return: Optional[float] = None
) -> Dict[str, float]:
    """
    Рассчитывает все расширенные метрики

    Args:
        returns: Список доходностей (десятичные дроби)
        max_drawdown: Максимальная просадка
        annual_return: Годовая доходность (опционально, рассчитается автоматически)

    Returns:
        Словарь с метриками
    """
    try:
        returns_series = pd.Series(returns)

        # Рассчитываем годовую доходность если не предоставлена
        if annual_return is None:
            if len(returns) > 0:
                daily_return = returns_series.mean()
                annual_return = daily_return * 365  # Для 24/7 рынка
            else:
                annual_return = 0.0

        # Рассчитываем метрики
        var_95 = calculate_var(returns_series, confidence=0.95)
        var_99 = calculate_var(returns_series, confidence=0.99)
        cvar_95 = calculate_cvar(returns_series, confidence=0.95)
        cvar_99 = calculate_cvar(returns_series, confidence=0.99)
        calmar_ratio = calculate_calmar_ratio(annual_return, max_drawdown)

        return {
            'var_95': var_95,
            'var_99': var_99,
            'cvar_95': cvar_95,
            'cvar_99': cvar_99,
            'calmar_ratio': calmar_ratio,
            'annual_return': annual_return
        }

    except Exception as e:
        logger.error(f"Ошибка расчета расширенных метрик: {e}")
        return {
            'var_95': 0.0,
            'var_99': 0.0,
            'cvar_95': 0.0,
            'cvar_99': 0.0,
            'calmar_ratio': 0.0,
            'annual_return': 0.0
        }
