"""
DCA (Dollar-Cost Averaging) Module
Модуль усреднения (DCA)

This module contains DCA calculation and management functions
"""

import logging
import pandas as pd
from typing import Dict, Any, Tuple, List, Optional
from decimal import Decimal
from ..core.config import MAX_DCA, ALPHA

logger = logging.getLogger(__name__)


# Фибоначчи-шаги для DCA (процент просадки для каждого шага)
DCA_FIB_STEPS = [1.3, 2.1, 3.4, 5.5, 8.9, 14.4]

def calculate_dca_next_qty_and_tp(
    original_price: float,
    current_price: float,
    current_qty: float,
    current_dca_count: int,
    deposit_usdt: float,
    risk_pct: float = 2.0,
    max_dca: int = None
) -> Dict[str, Any]:
    """
    Расчет следующего количества и TP для DCA.
    Использует Фибоначчи-шаги для определения уровней усреднения.

    Args:
        original_price: Оригинальная цена входа
        current_price: Текущая цена
        current_qty: Текущее количество монет
        current_dca_count: Текущий счетчик DCA (0, 1, 2...)
        deposit_usdt: Депозит в USDT
        risk_pct: Процент риска
        max_dca: Максимальное количество DCA

    Returns:
        Dict: Результат расчета DCA
    """
    try:
        if max_dca is None:
            max_dca = MAX_DCA

        if current_dca_count >= max_dca:
            return {
                "can_dca": False,
                "reason": "Достигнут лимит DCA (%d)" % max_dca
            }

        # Конвертируем все в Decimal для точности
        avg_price = Decimal(str(original_price))
        current_price_dec = Decimal(str(current_price))
        current_qty_dec = Decimal(str(current_qty))
        deposit_usdt_dec = Decimal(str(deposit_usdt))
        risk_pct_dec = Decimal(str(risk_pct))

        # Расчет убытка в процентах
        loss_pct = abs(avg_price - current_price_dec) / avg_price * Decimal("100")
        loss_pct_float = float(loss_pct)

        # Определяем порог для текущего шага на основе Фибоначчи
        step_index = min(current_dca_count, len(DCA_FIB_STEPS) - 1)
        required_loss = Decimal(str(DCA_FIB_STEPS[step_index]))

        # Определяем необходимость DCA
        if loss_pct < required_loss:
            return {
                "can_dca": False,
                "reason": "Убыток %.2f%% меньше требуемого шага %s%% (DCA #%d)" % (
                    loss_pct_float, required_loss, current_dca_count + 1
                )
            }

        # Расчет нового количества
        # Используем коэффициент ALPHA из конфига для агрессивности усреднения
        # Применяем множитель, зависящий от номера шага (тоже на основе Фибоначчи для объема)
        fib_multipliers = [Decimal("1.0"), Decimal("1.0"), Decimal("2.0"), Decimal("3.0"), Decimal("5.0"), Decimal("8.0")]
        vol_multiplier = fib_multipliers[step_index] if step_index < len(fib_multipliers) else fib_multipliers[-1]
        
        # Базовая сумма для этого шага
        base_step_risk = (deposit_usdt_dec * risk_pct_dec / Decimal("100")) * vol_multiplier
        new_qty = base_step_risk / current_price_dec

        # Общее количество после DCA
        total_qty = current_qty_dec + new_qty

        # Новая средняя цена
        total_cost = (avg_price * current_qty_dec) + (new_qty * current_price_dec)
        new_avg_price = total_cost / total_qty

        # Расчет новых уровней TP
        profit_targets = calculate_dca_profit_targets(
            float(new_avg_price), float(current_price_dec), current_dca_count + 1
        )

        return {
            "can_dca": True,
            "new_qty": float(new_qty),
            "total_qty": float(total_qty),
            "new_avg_price": float(new_avg_price),
            "profit_targets": profit_targets,
            "dca_count": current_dca_count + 1,
            "loss_pct": loss_pct_float,
            "required_loss": float(required_loss),
            "reason": "DCA #%d (Fib Step %s%%), убыток %.2f%%" % (
                current_dca_count + 1, required_loss, loss_pct_float
            )
        }

    except Exception as e:
        logger.error("Ошибка расчета DCA: %s", e, exc_info=True)
        return {
            "can_dca": False,
            "reason": "Ошибка расчета DCA: %s" % str(e)
        }


def calculate_dca_profit_targets(
    avg_price: float,
    current_price: float,
    dca_count: int
) -> Dict[str, float]:
    """
    Расчет целей профита для DCA позиции.
    Уровни TP становятся более консервативными при увеличении количества DCA.

    Args:
        avg_price: Средняя цена позиции
        current_price: Текущая цена
        dca_count: Количество выполненных DCA

    Returns:
        Dict: Цели профита (tp1, tp2, tp3)
    """
    try:
        # Конвертируем в Decimal для точности
        avg_price_dec = Decimal(str(avg_price))
        
        # Базовые цели профита (в процентах от СРЕДНЕЙ цены)
        # Для DCA мы хотим выйти быстрее, поэтому снижаем цели при росте кол-ва DCA
        if dca_count == 1:
            base_tp1, base_tp2, base_tp3 = Decimal("1.2"), Decimal("2.5"), Decimal("4.0")
        elif dca_count == 2:
            base_tp1, base_tp2, base_tp3 = Decimal("1.0"), Decimal("2.0"), Decimal("3.5")
        elif dca_count >= 3:
            base_tp1, base_tp2, base_tp3 = Decimal("0.8"), Decimal("1.5"), Decimal("3.0")
        else:
            base_tp1, base_tp2, base_tp3 = Decimal("1.5"), Decimal("3.0"), Decimal("5.0")

        # Расчет абсолютных цен (всегда выше средней цены)
        tp1_price = avg_price_dec * (Decimal("1") + base_tp1 / Decimal("100"))
        tp2_price = avg_price_dec * (Decimal("1") + base_tp2 / Decimal("100"))
        tp3_price = avg_price_dec * (Decimal("1") + base_tp3 / Decimal("100"))

        return {
            "tp1": float(tp1_price),
            "tp2": float(tp2_price),
            "tp3": float(tp3_price),
            "tp1_pct": float(base_tp1),
            "tp2_pct": float(base_tp2),
            "tp3_pct": float(base_tp3)
        }

    except Exception as e:
        logger.error("Ошибка расчета целей профита DCA: %s", e, exc_info=True)
        avg_price_dec = Decimal(str(avg_price))
        return {
            "tp1": float(avg_price_dec * Decimal("1.01")),
            "tp2": float(avg_price_dec * Decimal("1.02")),
            "tp3": float(avg_price_dec * Decimal("1.03")),
            "tp1_pct": 1.0,
            "tp2_pct": 2.0,
            "tp3_pct": 3.0
        }


def should_dca(
    entry_price: float,
    current_price: float,
    current_dca_count: int,
    min_loss_pct: float = None,
    max_dca: int = None
) -> Dict[str, Any]:
    """
    Определение необходимости DCA на основе Фибоначчи-шагов.

    Args:
        entry_price: Средняя цена входа текущей позиции
        current_price: Текущая рыночная цена
        current_dca_count: Сколько DCA уже сделано
        min_loss_pct: Переопределить минимальный процент (опционально)
        max_dca: Максимальное количество DCA

    Returns:
        Dict: Результат анализа необходимости DCA
    """
    try:
        if max_dca is None:
            max_dca = MAX_DCA

        if current_dca_count >= max_dca:
            return {
                "should_dca": False,
                "reason": "Достигнут лимит DCA (%d)" % max_dca
            }

        # Конвертируем в Decimal для точности
        entry_price_dec = Decimal(str(entry_price))
        current_price_dec = Decimal(str(current_price))
        
        # Определяем направление (BUY или SELL) по ценам
        # Если current_price < entry_price, считаем что это LONG
        loss_pct = abs(entry_price_dec - current_price_dec) / entry_price_dec * Decimal("100")
        loss_pct_float = float(loss_pct)

        # Если цена выше входа для лонга или ниже для шорта (но тут мы берем abs)
        # Нам нужно знать сторону, но упростим: DCA только если убыток существенный
        if current_price_dec == entry_price_dec:
             return {"should_dca": False, "reason": "Цена на уровне входа"}

        # Фибоначчи порог для текущего шага
        step_index = min(current_dca_count, len(DCA_FIB_STEPS) - 1)
        fib_threshold = Decimal(str(DCA_FIB_STEPS[step_index]))
        
        # Если передан min_loss_pct, используем макс из двух
        if min_loss_pct:
            min_loss_pct_dec = Decimal(str(min_loss_pct))
            required_threshold = max(fib_threshold, min_loss_pct_dec)
        else:
            required_threshold = fib_threshold

        if loss_pct < required_threshold:
            return {
                "should_dca": False,
                "reason": "Текущий убыток %.2f%% меньше порога %s%% (DCA #%d)" % (
                    loss_pct_float, required_threshold, current_dca_count + 1
                )
            }

        return {
            "should_dca": True,
            "loss_pct": loss_pct_float,
            "threshold": float(required_threshold),
            "reason": "Убыток %.2f%% превысил Фибо-порог %s%%" % (loss_pct_float, required_threshold)
        }

    except Exception as e:
        logger.error("Ошибка анализа DCA: %s", e, exc_info=True)
        return {
            "should_dca": False,
            "reason": "Ошибка анализа DCA: %s" % str(e)
        }


def calculate_dca_timeline(
    total_qty: float,
    total_cost: float,
    current_price: float,
    dca_count: int
) -> Dict[str, Any]:
    """
    Расчет временной линии для DCA позиции

    Args:
        total_qty: Общее количество монет
        total_cost: Общая стоимость позиции
        current_price: Текущая цена
        dca_count: Количество DCA

    Returns:
        Dict: Информация о временной линии
    """
    try:
        # Конвертируем в Decimal для точности
        total_qty_dec = Decimal(str(total_qty))
        total_cost_dec = Decimal(str(total_cost))
        current_price_dec = Decimal(str(current_price))
        
        avg_price = total_cost_dec / total_qty_dec
        current_value = total_qty_dec * current_price_dec

        # Расчет PnL
        pnl_usdt = current_value - total_cost_dec
        pnl_pct = (pnl_usdt / total_cost_dec) * Decimal("100")
        pnl_pct_float = float(pnl_pct)
        pnl_usdt_float = float(pnl_usdt)

        # Определение статуса
        if pnl_usdt > 0:
            status = "profit"
            status_desc = "В профите"
        elif pnl_usdt == 0:
            status = "breakeven"
            status_desc = "В нулях"
        else:
            status = "loss"
            status_desc = "Убыток %.1f%%" % abs(pnl_pct_float)

        # Расчет точек восстановления
        if pnl_usdt < 0:
            breakeven_price = float(total_cost_dec / total_qty_dec)
            profit_1pct_price = float(breakeven_price * Decimal("1.01"))
            profit_2pct_price = float(breakeven_price * Decimal("1.02"))
        else:
            breakeven_price = None
            profit_1pct_price = float(current_price_dec * Decimal("1.01"))
            profit_2pct_price = float(current_price_dec * Decimal("1.02"))

        return {
            "avg_price": float(avg_price),
            "current_price": float(current_price_dec),
            "current_value": float(current_value),
            "total_cost": float(total_cost_dec),
            "pnl_usdt": pnl_usdt_float,
            "pnl_pct": pnl_pct_float,
            "status": status,
            "status_desc": status_desc,
            "breakeven_price": breakeven_price,
            "profit_1pct_price": profit_1pct_price,
            "profit_2pct_price": profit_2pct_price,
            "dca_count": dca_count
        }

    except Exception as e:
        logger.error("Ошибка расчета временной линии DCA: %s", e, exc_info=True)
        return {
            "error": "Ошибка расчета временной линии DCA: %s" % str(e)
        }


def get_dca_recommendation(
    entry_price: float,
    current_price: float,
    current_dca_count: int,
    deposit_usdt: float,
    market_trend: str = "neutral"
) -> Dict[str, Any]:
    """
    Получить рекомендацию по DCA

    Args:
        entry_price: Цена входа
        current_price: Текущая цена
        current_dca_count: Текущий счетчик DCA
        deposit_usdt: Депозит в USDT
        market_trend: Тренд рынка ("bull", "bear", "neutral")

    Returns:
        Dict: Рекомендация по DCA
    """
    try:
        # Анализ необходимости DCA
        dca_analysis = should_dca(entry_price, current_price, current_dca_count)

        if not dca_analysis["should_dca"]:
            return {
                "recommendation": "HOLD",
                "reason": dca_analysis["reason"],
                "confidence": "high"
            }

        # Расчет рекомендуемого количества
        loss_pct = dca_analysis["loss_pct"]

        # Корректировка на основе тренда рынка
        if market_trend == "bull":
            qty_multiplier = 1.2  # Больше DCA в бычьем тренде
        elif market_trend == "bear":
            qty_multiplier = 0.8  # Меньше DCA в медвежьем тренде
        else:
            qty_multiplier = 1.0

        # Конвертируем в Decimal для точности
        entry_price_dec = Decimal(str(entry_price))
        current_price_dec = Decimal(str(current_price))
        deposit_usdt_dec = Decimal(str(deposit_usdt))
        qty_multiplier_dec = Decimal(str(qty_multiplier))
        
        # Расчет количества на основе убытка
        if loss_pct < 5:
            base_risk = Decimal("2.0")
        elif loss_pct < 10:
            base_risk = Decimal("3.0")
        else:
            base_risk = Decimal("4.0")

        recommended_qty = (deposit_usdt_dec * base_risk / Decimal("100")) / current_price_dec * qty_multiplier_dec

        # Определение уверенности
        if current_dca_count == 0 and loss_pct < 7:
            confidence = "high"
        elif current_dca_count <= 2 and loss_pct < 15:
            confidence = "medium"
        else:
            confidence = "low"

        estimated_new_avg = (entry_price_dec + current_price_dec) / Decimal("2")

        return {
            "recommendation": "DCA",
            "reason": "Убыток %.1f%%, рекомендуется усреднение" % loss_pct,
            "recommended_qty": float(recommended_qty),
            "estimated_new_avg": float(estimated_new_avg),
            "confidence": confidence,
            "market_trend": market_trend
        }

    except Exception as e:
        logger.error("Ошибка анализа DCA: %s", e, exc_info=True)
        return {
            "recommendation": "HOLD",
            "reason": "Ошибка анализа DCA: %s" % str(e),
            "confidence": "unknown"
        }
