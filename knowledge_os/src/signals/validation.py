#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль валидации сигналов
Вынесен из signal_live.py для рефакторинга
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional

import pandas as pd
from src.shared.utils.datetime_utils import get_utc_now

logger = logging.getLogger(__name__)


class DataValidationError(ValueError):
    """Исключение, выбрасываемое при нарушении правил валидации входных данных."""


def _ensure_required_keys(
    payload: Mapping[str, Any],
    required_keys: Iterable[str],
    *,
    entity: str,
) -> None:
    for key in required_keys:
        if key not in payload:
            raise DataValidationError(f"Отсутствует обязательное поле {key!r} для {entity}.")


def validate_signal_data(data: Mapping[str, Any]) -> bool:
    """
    Проверяет входной словарь сигнала перед генерацией позиций.

    Требуемые поля: symbol (строка ≥ 6 символов), side (long/short), price (положительное число),
    user_id (строка или int).
    """
    if not isinstance(data, Mapping):
        raise DataValidationError("Данные сигнала должны быть словарем.")

    _ensure_required_keys(data, ("symbol", "side", "price", "user_id"), entity="signal")

    symbol = str(data["symbol"]).upper()
    if len(symbol) < 6 or not symbol.isalnum():
        raise DataValidationError("Невалидный символ: ожидается тикер вида BTCUSDT.")

    side = str(data["side"]).lower()
    if side not in {"long", "short"}:
        raise DataValidationError("Сторона должна быть 'long' или 'short'.")

    price = data["price"]
    try:
        price_value = float(price)
    except (TypeError, ValueError) as exc:
        raise DataValidationError("Цена должна быть положительным числом.") from exc
    if price_value <= 0:
        raise DataValidationError("Цена должна быть положительным числом.")

    user_id = data["user_id"]
    if isinstance(user_id, (int, float)):
        if user_id <= 0:
            raise DataValidationError("Идентификатор пользователя должен быть положительным.")
    elif isinstance(user_id, str):
        if not user_id.isdigit():
            raise DataValidationError("Идентификатор пользователя должен содержать только цифры.")
    else:
        raise DataValidationError("Идентификатор пользователя имеет неподдерживаемый тип.")

    return True


def validate_dataframe(df: Optional[pd.DataFrame], required_columns: Iterable[str]) -> bool:
    """
    Проверяет, что DataFrame не пуст, содержит нужные колонки и не имеет NaN в обязательных полях.
    """
    if df is None:
        raise DataValidationError("DataFrame не может быть None.")
    if not isinstance(df, pd.DataFrame):
        raise DataValidationError("Ожидался pandas.DataFrame.")
    if df.empty:
        raise DataValidationError("DataFrame пустой.")

    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise DataValidationError(f"Отсутствуют колонки: {', '.join(missing_columns)}.")

    subset = df[list(required_columns)]
    if subset.isna().any().any():
        raise DataValidationError("Найдены NaN значения в обязательных колонках.")

    return True


def validate_user_data(data: Mapping[str, Any]) -> bool:
    """
    Проверяет данные пользователя (user_id + deposit).
    """
    if not isinstance(data, Mapping):
        raise DataValidationError("Данные пользователя должны быть словарем.")

    for field in ("user_id", "deposit"):
        if field not in data:
            raise DataValidationError(f"Отсутствует поле пользователя '{field}'.")

    deposit = data["deposit"]
    try:
        deposit_value = float(deposit)
    except (TypeError, ValueError) as exc:
        raise DataValidationError("Депозит должен быть положительным числом.") from exc
    if deposit_value <= 0:
        raise DataValidationError("Депозит должен быть положительным числом.")

    user_id = data["user_id"]
    if isinstance(user_id, str) and not user_id.isdigit():
        raise DataValidationError("Идентификатор пользователя должен содержать только цифры.")
    if isinstance(user_id, (int, float)) and user_id <= 0:
        raise DataValidationError("Идентификатор пользователя должен быть положительным.")

    return True


def sanitize_signal_data(data: MutableMapping[str, Any]) -> Dict[str, Any]:
    """
    Нормализует данные сигнала для сохранения в БД/отправки.
    """
    if not isinstance(data, MutableMapping):
        raise DataValidationError("sanitize_signal_data ожидает словарь.")

    normalized: Dict[str, Any] = dict(data)

    symbol = str(normalized.get("symbol", "")).upper()
    normalized["symbol"] = symbol if symbol else "UNKNOWNUSDT"

    side = str(normalized.get("side", "long")).lower()
    if side not in {"long", "short"}:
        side = "long"
    normalized["side"] = side

    price_raw = normalized.get("price", 0.0)
    try:
        price_value = float(price_raw)
        if price_value < 0:
            price_value = abs(price_value)
    except (TypeError, ValueError):
        price_value = 0.0
    normalized["price"] = price_value

    user_id = normalized.get("user_id")
    if isinstance(user_id, (int, float)):
        normalized["user_id"] = str(int(user_id))
    elif isinstance(user_id, str):
        normalized["user_id"] = user_id
    else:
        normalized["user_id"] = "0"

    normalized.setdefault("timestamp", get_utc_now().isoformat() + "Z")

    return normalized


def calculate_direction_confidence(df: pd.DataFrame, signal_type: str) -> bool:
    """
    Рассчитывает уверенность в направлении сигнала
    Требует минимум 3 из 4 подтверждений
    """
    try:
        confirmations = 0

        if signal_type == "BUY":
            # Проверка 1: EMA Fast > EMA Slow
            if 'ema_fast' in df.columns and 'ema_slow' in df.columns:
                if df['ema_fast'].iloc[-1] > df['ema_slow'].iloc[-1]:
                    confirmations += 1
                    logger.debug("✅ [BUY CONFIRM] EMA alignment")

            # Проверка 2: Price > EMA Fast
            if 'close' in df.columns and 'ema_fast' in df.columns:
                if df['close'].iloc[-1] > df['ema_fast'].iloc[-1]:
                    confirmations += 1
                    logger.debug("✅ [BUY CONFIRM] Price above EMA")

            # Проверка 3: RSI < 50 (не перекуплен)
            if 'rsi' in df.columns:
                rsi = df['rsi'].iloc[-1]
                if not pd.isna(rsi) and rsi < 50:
                    confirmations += 1
                    logger.debug("✅ [BUY CONFIRM] RSI %.1f < 50", rsi)

            # Проверка 4: MACD > MACD Signal
            if 'macd' in df.columns and 'macd_signal' in df.columns:
                macd = df['macd'].iloc[-1]
                macd_signal = df['macd_signal'].iloc[-1]
                if not pd.isna(macd) and not pd.isna(macd_signal) and macd > macd_signal:
                    confirmations += 1
                    logger.debug("✅ [BUY CONFIRM] MACD above signal")

        else:  # SELL
            # Проверка 1: EMA Fast < EMA Slow
            if 'ema_fast' in df.columns and 'ema_slow' in df.columns:
                if df['ema_fast'].iloc[-1] < df['ema_slow'].iloc[-1]:
                    confirmations += 1
                    logger.debug("✅ [SELL CONFIRM] EMA alignment")

            # Проверка 2: Price < EMA Fast
            if 'close' in df.columns and 'ema_fast' in df.columns:
                if df['close'].iloc[-1] < df['ema_fast'].iloc[-1]:
                    confirmations += 1
                    logger.debug("✅ [SELL CONFIRM] Price below EMA")

            # Проверка 3: RSI > 50 (не перепродан)
            if 'rsi' in df.columns:
                rsi = df['rsi'].iloc[-1]
                if not pd.isna(rsi) and rsi > 50:
                    confirmations += 1
                    logger.debug("✅ [SELL CONFIRM] RSI %.1f > 50", rsi)

            # Проверка 4: MACD < MACD Signal
            if 'macd' in df.columns and 'macd_signal' in df.columns:
                macd = df['macd'].iloc[-1]
                macd_signal = df['macd_signal'].iloc[-1]
                if not pd.isna(macd) and not pd.isna(macd_signal) and macd < macd_signal:
                    confirmations += 1
                    logger.debug("✅ [SELL CONFIRM] MACD below signal")

        # Требуем минимум 3 из 4 подтверждений
        result = confirmations >= 3
        if not result:
            # Детальное логирование отсутствующих проверок
            missing_checks = []
            if signal_type == "BUY":
                if (
                    'ema_fast' not in df.columns or
                    'ema_slow' not in df.columns or
                    df['ema_fast'].iloc[-1] <= df['ema_slow'].iloc[-1]
                ):
                    missing_checks.append("EMA alignment")
                if (
                    'close' not in df.columns or
                    'ema_fast' not in df.columns or
                    df['close'].iloc[-1] <= df['ema_fast'].iloc[-1]
                ):
                    missing_checks.append("Price > EMA")
                if 'rsi' not in df.columns or pd.isna(df['rsi'].iloc[-1]) or df['rsi'].iloc[-1] >= 50:
                    missing_checks.append("RSI < 50")
                if 'macd' not in df.columns or 'macd_signal' not in df.columns:
                    missing_checks.append("MACD (колонки отсутствуют)")
                elif (
                    pd.isna(df['macd'].iloc[-1]) or
                    pd.isna(df['macd_signal'].iloc[-1]) or
                    df['macd'].iloc[-1] <= df['macd_signal'].iloc[-1]
                ):
                    missing_checks.append("MACD > Signal")
            else:  # SELL
                if (
                    'ema_fast' not in df.columns or
                    'ema_slow' not in df.columns or
                    df['ema_fast'].iloc[-1] >= df['ema_slow'].iloc[-1]
                ):
                    missing_checks.append("EMA alignment")
                if (
                    'close' not in df.columns or
                    'ema_fast' not in df.columns or
                    df['close'].iloc[-1] >= df['ema_fast'].iloc[-1]
                ):
                    missing_checks.append("Price < EMA")
                if 'rsi' not in df.columns or pd.isna(df['rsi'].iloc[-1]) or df['rsi'].iloc[-1] <= 50:
                    missing_checks.append("RSI > 50")
                if 'macd' not in df.columns or 'macd_signal' not in df.columns:
                    missing_checks.append("MACD (колонки отсутствуют)")
                elif (
                    pd.isna(df['macd'].iloc[-1]) or
                    pd.isna(df['macd_signal'].iloc[-1]) or
                    df['macd'].iloc[-1] >= df['macd_signal'].iloc[-1]
                ):
                    missing_checks.append("MACD < Signal")

            logger.warning("🚫 [DIRECTION CHECK] %s: недостаточно подтверждений (%d/4). Отсутствуют: %s",
                         signal_type, confirmations, ", ".join(missing_checks) if missing_checks else "неизвестно")
        else:
            logger.info("✅ [DIRECTION CHECK] %s: %d/4 подтверждений", signal_type, confirmations)

        return result
    except Exception as e:
        logger.error("❌ Ошибка расчета направления для %s: %s", signal_type, e)
        return False


def check_rsi_warning(df: pd.DataFrame, signal_type: str) -> bool:
    """Проверяет RSI на перекупленность/перепроданность"""
    try:
        if 'rsi' not in df.columns:
            return True  # Если RSI нет, пропускаем проверку

        rsi = df['rsi'].iloc[-1]
        if pd.isna(rsi):
            return True  # Если RSI NaN, пропускаем

        if signal_type == "BUY":
            # Для LONG: RSI не должен быть в зоне перекупленности (> 70)
            if rsi > 70:
                logger.debug("⚠️ [RSI WARNING] %s: RSI %.1f > 70 (перекупленность)", signal_type, rsi)
                return False
        else:  # SELL
            # Для SHORT: RSI не должен быть в зоне перепроданности (< 30)
            if rsi < 30:
                logger.debug("⚠️ [RSI WARNING] %s: RSI %.1f < 30 (перепроданность)", signal_type, rsi)
                return False

        return True
    except Exception as e:
        logger.error("❌ Ошибка проверки RSI для %s: %s", signal_type, e)
        return True  # При ошибке пропускаем проверку
