import logging
from datetime import datetime, timezone
from typing import Tuple

import pandas as pd

def get_msk_now() -> datetime:
    """
    Получение текущего московского времени (MSK, UTC+3)
    
    Returns:
        datetime: Текущее время в МСК (timezone-aware)
    """
    try:
        import pytz
        # Получаем системную зону
        try:
            from tzlocal import get_localzone
            local_tz = get_localzone()
            now_local = datetime.now(timezone.utc).astimezone(local_tz)
        except ImportError:
            # Fallback если tzlocal не установлен
            from src.shared.utils.datetime_utils import get_utc_now
            now_local = get_utc_now()
        
        # Московское время (UTC+3)
        msk_tz = pytz.timezone("Europe/Moscow")
        now_msk = now_local.astimezone(msk_tz)
        return now_msk
    except (ImportError, Exception):
        # Fallback к UTC+3 (без timezone)
        # Просто добавляем 3 часа к UTC
        from datetime import timedelta, timezone
        from src.shared.utils.datetime_utils import get_utc_now
        utc_now = get_utc_now()
        msk_offset = timedelta(hours=3)
        return utc_now + msk_offset


def normalize_symbol_for_db(symbol: str, user_trade_mode: str = 'spot') -> str:
    """
    Нормализует символ для сохранения в базу данных.
    Приводит символ к единому формату XPLUSDT независимо от режима торговли.
    
    Args:
        symbol: Символ в любом формате (XPL/USDT, XPLUSDT, XPL/USDT:USDT)
        user_trade_mode: Режим торговли пользователя ('spot' или 'futures')
    
    Returns:
        Нормализованный символ в формате XPLUSDT
    """
    if not symbol:
        return symbol
    
    # Убираем пробелы и приводим к верхнему регистру
    symbol = symbol.strip().upper()
    
    if user_trade_mode == 'futures':
        # Futures: убираем суффиксы типа /USDT:USDT, /USDT
        if '/USDT:USDT' in symbol:
            symbol = symbol.replace('/USDT:USDT', 'USDT')
        elif '/USDT' in symbol and not symbol.endswith('USDT'):
            symbol = symbol.replace('/USDT', 'USDT')
    else:  # spot
        # Spot: убираем /USDT (если не заканчивается на USDT)
        if '/USDT' in symbol and not symbol.endswith('USDT'):
            symbol = symbol.replace('/USDT', 'USDT')
    
    return symbol


# --- Динамические TP уровни и учет комиссий ---------------------------------

logger = logging.getLogger(__name__)

_FEE_BUFFERS = {
    'spot': {
        'entry_fee': 0.10,
        'exit_fee': 0.10,
        'buffer': 0.02,  # доп. запас на проскальзывание/округления
    },
    'futures': {
        'entry_fee': 0.04,
        'exit_fee': 0.04,
        'buffer': 0.01,
    },
}


def adjust_tp_for_fees(tp_pct: float, trade_mode: str = 'spot') -> float:
    """
    Корректирует цель по прибыли с учётом комиссий и небольшого запаса.

    Args:
        tp_pct: Базовый TP в процентах.
        trade_mode: 'spot' или 'futures'. Для неизвестных режимов используется spot.

    Returns:
        float: TP, скорректированный так, чтобы чистая прибыль оставалась положительной.
    """
    if tp_pct is None:
        return tp_pct

    mode = (trade_mode or 'spot').lower()
    fees_cfg = _FEE_BUFFERS.get(mode, _FEE_BUFFERS['spot'])

    total_fees = fees_cfg['entry_fee'] + fees_cfg['exit_fee'] + fees_cfg['buffer']
    adjusted = tp_pct + total_fees

    # Минимальный TP должен быть чуть больше совокупных комиссий
    min_tp = max(0.15, total_fees + 0.01)
    if adjusted < min_tp:
        adjusted = min_tp

    logger.debug(
        "💰 Коррекция TP: base=%.3f%%, mode=%s, total_fees=%.3f%%, result=%.3f%%",
        tp_pct, mode, total_fees, adjusted
    )
    return adjusted


def get_dynamic_tp_levels(df: pd.DataFrame, i: int, side: str = "long",
                          trade_mode: str = "spot", adjust_for_fees: bool = True) -> Tuple[float, float]:
    """
    Обёртка над основной реализацией динамических TP.

    Делегирует расчёт функции из `src.signals.risk`, чтобы избежать дублирования логики.
    При недоступности основного модуля возвращает безопасные значения (2%, 4%).
    """
    try:
        from src.signals.risk import get_dynamic_tp_levels as _core_get_dynamic_tp_levels
        return _core_get_dynamic_tp_levels(
            df, i, side=side, trade_mode=trade_mode, adjust_for_fees=adjust_for_fees
        )
    except Exception as exc:
        logger.error("⚠️ get_dynamic_tp_levels fallback: %s", exc)
        base_tp1, base_tp2 = 2.0, 4.0
        if adjust_for_fees:
            base_tp1 = adjust_tp_for_fees(base_tp1, trade_mode)
            base_tp2 = adjust_tp_for_fees(base_tp2, trade_mode)
        return base_tp1, base_tp2


def _extract_positions_from_user(user_data: dict, symbol: str) -> list:
    """Помощник: достаёт позиции пользователя по символу из разных ключей user_data."""
    if not isinstance(user_data, dict):
        return []

    possible_keys = (
        "positions", "open_positions", "portfolio_positions",
        "active_positions", "tracked_positions"
    )
    positions = []
    for key in possible_keys:
        items = user_data.get(key)
        if not items:
            continue
        try:
            for item in items:
                if (item or {}).get("symbol", "").upper() == symbol.upper():
                    positions.append(item)
        except TypeError:
            continue
    return positions


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def calculate_unified_tp_for_symbol(user_data: dict, symbol: str, entry_price: float,
                                    df: pd.DataFrame, index: int) -> Tuple[float, float]:
    """
    Расчитывает «унифицированные» TP уровни для символа, учитывая уже открытые позиции пользователя.

    Алгоритм стремится сделать цели более консервативными при высокой совокупной нагрузке, чтобы новые
    сделки не выставляли TP значительно дальше текущих целей по уже открытым позициям.
    """
    try:
        trade_mode = (user_data or {}).get("trade_mode", "spot")
        side = "long"

        # Базовые динамические уровни (учитывают волатильность и комиссии)
        base_tp1, base_tp2 = get_dynamic_tp_levels(
            df, index, side, trade_mode=trade_mode, adjust_for_fees=True
        )

        positions = _extract_positions_from_user(user_data or {}, symbol)
        if not positions:
            return round(base_tp1, 2), round(base_tp2, 2)

        # Считаем совокупный объём и риск по символу
        total_qty = 0.0
        total_cost = 0.0
        total_risk_amount = 0.0

        for pos in positions:
            qty = _safe_float(pos.get("qty") or pos.get("quantity"))
            if qty <= 0:
                continue

            total_qty += qty
            entry = _safe_float(pos.get("entry_price"), entry_price)
            total_cost += entry * qty
            total_risk_amount += _safe_float(pos.get("risk_amount") or pos.get("allocated_risk"))

            side = (pos.get("side") or side).lower()

        if total_qty <= 0:
            return round(base_tp1, 2), round(base_tp2, 2)

        unified_entry = total_cost / total_qty if total_qty else entry_price

        deposit = _safe_float(user_data.get("deposit") or user_data.get("balance"), 0.0)
        exposure_notional = total_cost
        exposure_ratio = 0.0
        if deposit > 0:
            exposure_ratio = min(1.5, exposure_notional / deposit)

        num_positions = max(1, len(positions))

        # Чем больше позиций и выше экспозиция, тем сильнее сдвигаем TP к более быстрым целям
        position_penalty = min(0.45, (num_positions - 1) * 0.07)
        exposure_penalty = min(0.5, exposure_ratio * 0.2)
        risk_penalty = 0.0
        if deposit > 0 and total_risk_amount > 0:
            risk_penalty = min(0.35, (total_risk_amount / deposit) * 0.25)

        penalty_factor = max(0.4, 1.0 - position_penalty - exposure_penalty - risk_penalty)

        unified_tp1 = max(0.3, base_tp1 * penalty_factor)
        unified_tp2 = max(unified_tp1 * 1.1, base_tp2 * penalty_factor)

        # Дополнительно контролируем, чтобы цели не уходили ниже минимального чистого значения
        unified_tp1 = max(unified_tp1, adjust_tp_for_fees(0.4, trade_mode))
        unified_tp2 = max(unified_tp2, unified_tp1 + 0.3)

        logger.debug(
            "📊 Unified TP for %s: entry=%.4f, base=(%.2f, %.2f), penalties=(pos=%.3f, exp=%.3f, risk=%.3f) → (%.2f, %.2f)",
            symbol, unified_entry, base_tp1, base_tp2,
            position_penalty, exposure_penalty, risk_penalty,
            unified_tp1, unified_tp2
        )

        return round(unified_tp1, 2), round(unified_tp2, 2)

    except Exception as exc:
        logger.warning("⚠️ calculate_unified_tp_for_symbol fallback: %s", exc)
        trade_mode = (user_data or {}).get("trade_mode", "spot")
        tp1, tp2 = get_dynamic_tp_levels(df, index, "long", trade_mode=trade_mode, adjust_for_fees=True)
        return round(tp1, 2), round(tp2, 2)


# --- Управление риском ------------------------------------------------------

def clamp_new_risk(deposit: float, user_data: dict, symbol: str,
                   proposed_risk_usd: float, trade_mode: str = "spot") -> float:
    """
    Ограничивает риск для новой позиции с учётом депозита, существующих позиций и профиля риска.

    Args:
        deposit: общий депозит пользователя
        user_data: словарь данных пользователя
        symbol: торговый символ
        proposed_risk_usd: предлагаемая сумма риска в USD
        trade_mode: 'spot' или 'futures'

    Returns:
        float: риск в USD после ограничений
    """
    try:
        deposit = _safe_float(deposit, 0.0)
        if deposit <= 0:
            return max(0.0, proposed_risk_usd)

        trade_mode = (trade_mode or user_data.get("trade_mode") or "spot").lower()
        base_risk_pct = _safe_float(user_data.get("risk_pct"), 2.0)
        max_risk_pct = max(0.5, min(8.0, base_risk_pct * 1.5))

        try:
            from risk_profile import get_risk_profile  # type: ignore
            profile = get_risk_profile(deposit, trade_mode)
            hard_cap_pct = _safe_float(profile.get("max_risk_pct_per_position"), max_risk_pct)
        except Exception:
            hard_cap_pct = max_risk_pct

        hard_cap_usd = deposit * (hard_cap_pct / 100.0)
        capped_risk = min(proposed_risk_usd, hard_cap_usd)

        positions = _extract_positions_from_user(user_data or {}, symbol)
        total_existing_risk = sum(
            _safe_float(pos.get("risk_amount") or pos.get("allocated_risk"))
            for pos in positions
        )

        total_risk_cap_pct = min(20.0, base_risk_pct * 4)
        total_risk_cap_usd = deposit * (total_risk_cap_pct / 100.0)
        remaining_cap = max(0.0, total_risk_cap_usd - total_existing_risk)

        final_risk = min(capped_risk, remaining_cap)

        trade_mode = (trade_mode or "spot").lower()
        min_risk_pct = 0.15 if trade_mode == "spot" else 0.10
        min_risk_usd = deposit * (min_risk_pct / 100.0)

        final_risk = max(min_risk_usd, final_risk)

        logger.debug(
            "🛡️ clamp_new_risk: deposit=%.2f, proposed=%.2f, hard_cap=%.2f, existing=%.2f, "
            "remaining=%.2f, final=%.2f (mode=%s)",
            deposit, proposed_risk_usd, hard_cap_usd, total_existing_risk,
            remaining_cap, final_risk, trade_mode
        )

        return max(0.0, final_risk)

    except Exception as exc:
        logger.warning("⚠️ clamp_new_risk fallback: %s", exc)
        return max(0.0, proposed_risk_usd)
