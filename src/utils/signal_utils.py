#!/usr/bin/env python3
"""
Вспомогательные функции для обработки сигналов
"""

import asyncio
import logging
from typing import Any, Dict, List

import pandas as pd
import ta

logger = logging.getLogger(__name__)


try:
    from src.signals.indicators import add_technical_indicators
except ImportError:
    # Fallback если модуль недоступен
    def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
        return df


def check_ai_volume_filter(df: pd.DataFrame, ai_params: Dict[str, Any]) -> bool:
    """Проверяет ИИ-фильтр по объему"""
    try:
        if df.empty or "volume" not in df.columns:
            return False

        current_volume = df["volume"].iloc[-1]
        avg_volume = df["volume"].rolling(window=20).mean().iloc[-1]

        min_volume_usd = ai_params.get("min_volume_usd", 50000)
        volume_ratio_threshold = ai_params.get("volume_ratio_threshold", 1.2)

        # Проверяем минимальный объем и отношение к среднему
        volume_ok = (
            current_volume >= min_volume_usd
            and current_volume / avg_volume >= volume_ratio_threshold
        )

        logger.debug(
            "📊 Volume filter: текущий=%.0f, средний=%.0f, "
            "отношение=%.2f, мин_объем=%.0f, пройден=%s",
            current_volume,
            avg_volume,
            current_volume / avg_volume,
            min_volume_usd,
            volume_ok,
        )

        return volume_ok

    except Exception as e:
        logger.error("Ошибка в ИИ-фильтре объема: %s", e)
        return True  # В случае ошибки пропускаем


def check_ai_volatility_filter(df: pd.DataFrame, ai_params: Dict[str, Any]) -> bool:
    """Проверяет ИИ-фильтр по волатильности"""
    try:
        if df.empty or "volatility" not in df.columns:
            return False

        current_volatility = df["volatility"].iloc[-1] / 100  # Переводим в доли
        min_vol = ai_params.get("min_volatility_pct", 0.005)
        max_vol = ai_params.get("max_volatility_pct", 0.15)

        volatility_ok = min_vol <= current_volatility <= max_vol

        logger.debug(
            "📊 Volatility filter: текущая=%.3f%%, диапазон=[%.3f%%, %.3f%%], пройден=%s",
            current_volatility * 100,
            min_vol * 100,
            max_vol * 100,
            volatility_ok,
        )

        return volatility_ok

    except Exception as e:
        logger.error("Ошибка в ИИ-фильтре волатильности: %s", e)
        return True  # В случае ошибки пропускаем


def is_signal_already_sent(symbol: str, user_id: str, signal_history: List[Dict[str, Any]]) -> bool:
    """Проверяет, был ли уже отправлен сигнал для данной пары пользователю"""
    for signal in signal_history:
        if signal.get("symbol") == symbol and signal.get("user_id") == user_id:
            return True
    return False


async def send_with_retry(
    user_id: str, message: str, reply_markup=None, trace_id: str = None, max_retries: int = 3
) -> bool:
    """Отправка с retry логикой"""
    for attempt in range(max_retries):
        try:
            # Импортируем функцию отправки
            from src.telegram.handlers import notify_user

            await notify_user(user_id, message, reply_markup=reply_markup)
            logger.info(
                "✅ [%s] Сообщение отправлено (попытка %d/%d)", trace_id, attempt + 1, max_retries
            )
            return True
        except Exception as e:
            logger.error(
                "❌ [%s] Ошибка отправки (попытка %d/%d): %s", trace_id, attempt + 1, max_retries, e
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(2**attempt)  # Экспоненциальная задержка

    logger.error("❌ [%s] Все попытки отправки исчерпаны", trace_id)
    return False


async def send_with_retry_fallback(
    user_id: str, message: str, reply_markup=None, trace_id: str = None, max_retries: int = 2
) -> bool:
    """Fallback отправка с retry логикой"""
    for attempt in range(max_retries):
        try:
            from src.telegram.handlers import notify_user

            await notify_user(user_id, message, reply_markup=reply_markup)
            logger.info(
                "✅ [%s] Fallback сообщение отправлено (попытка %d/%d)",
                trace_id,
                attempt + 1,
                max_retries,
            )
            return True
        except Exception as e:
            logger.error(
                "❌ [%s] Fallback ошибка (попытка %d/%d): %s", trace_id, attempt + 1, max_retries, e
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(1)

    logger.error("❌ [%s] Все fallback попытки исчерпаны", trace_id)
    return False
