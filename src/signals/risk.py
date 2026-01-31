"""
Динамические параметры риска и управления позициями
Содержит функции для расчета динамических TP/SL, плеча и риска
"""

import pandas as pd
import numpy as np
from typing import Tuple, Dict, Any, Optional
import logging
from decimal import Decimal
from src.shared.utils.datetime_utils import get_utc_now

logger = logging.getLogger(__name__)

# Импорты из других модулей (будут обновлены после создания всех модулей)
try:
    from ..core.config import AI_AVAILABLE
    import ai_position_sizing
except ImportError:
    AI_AVAILABLE = False
    ai_position_sizing = None


def get_dynamic_leverage(
    df: pd.DataFrame,
    i: int,
    base_leverage: Decimal = Decimal("1.0"),
    symbol: Optional[str] = None,
    user_data: Optional[Dict] = None,
    use_ai_optimization: bool = True
) -> Decimal:
    """
    Динамический расчет плеча на основе волатильности и тренда.
    Использует LeverageManager для комплексного анализа.
    
    Args:
        df: DataFrame с данными OHLCV и индикаторами
        i: Индекс текущей свечи
        base_leverage: Базовое плечо из настроек пользователя
        symbol: Символ торговой пары
        user_data: Данные пользователя
        use_ai_optimization: Использовать ли ИИ оптимизацию
        
    Returns:
        Decimal: Динамическое плечо
    """
    if i < 21:
        return base_leverage

    # 1. 🤖 ИИ-ОПТИМИЗАЦИЯ ПЛЕЧА
    if use_ai_optimization and symbol and user_data and AI_AVAILABLE and ai_position_sizing:
        try:
            _, ai_leverage, _ = ai_position_sizing.calculate_ai_optimized_position_size(
                symbol=symbol,
                side="long",  # Переопределяется при вызове
                df=df,
                current_index=i,
                user_data=user_data,
                base_risk_pct=Decimal("2.0"),
                base_leverage=base_leverage
            )
            logger.info("🤖 ИИ-оптимизированное плечо для %s: %.1fx", symbol, float(ai_leverage))
            return Decimal(str(ai_leverage))
        except Exception as e:
            logger.warning("⚠️ ИИ-оптимизация плеча недоступна для %s: %s, используем стандартный расчет", symbol, e)

    # 2. 📉 СТАНДАРТНЫЙ РАСЧЕТ ЧЕРЕЗ LeverageManager (Volatility-Adjusted)
    try:
        from src.signals.leverage import leverage_manager
        
        # Определяем рыночный режим (если доступен в user_data или через режим)
        market_condition = "normal"
        if user_data and 'market_regime' in user_data:
            market_condition = user_data['market_regime']
            
        dynamic_leverage = Decimal(str(leverage_manager.calculate_dynamic_leverage(
            df=df,
            i=i,
            base_leverage=float(base_leverage),
            market_condition=market_condition
        )))
        
        # Жёсткие лимиты безопасности (всегда соблюдаем)
        from src.core.config import MAX_LEVERAGE
        max_leverage_dec = Decimal(str(MAX_LEVERAGE))
        dynamic_leverage = max(Decimal("1.0"), min(max_leverage_dec, dynamic_leverage))
        
        return dynamic_leverage

    except (ImportError, Exception) as e:
        logger.error("Ошибка в get_dynamic_leverage (fallback) для %s: %s", symbol, e)
        # Если менеджер недоступен, используем простую логику из предыдущей версии
        return base_leverage


def get_dynamic_risk_pct(
    df: pd.DataFrame,
    i: int,
    symbol: Optional[str] = None,
    user_data: Optional[Dict] = None,
    use_ai_optimization: bool = True
) -> Decimal:
    """
    Динамический расчет процента риска на основе волатильности и рыночных условий
    
    Args:
        df: DataFrame с данными OHLCV и индикаторами
        i: Индекс текущей свечи
        symbol: Символ торговой пары
        user_data: Данные пользователя
        use_ai_optimization: Использовать ли ИИ оптимизацию
        
    Returns:
        Decimal: Динамический процент риска (1-5%)
    """
    if i < 21:
        return Decimal("2.0")  # базовый риск, если мало данных

    # 🤖 ИИ-ОПТИМИЗАЦИЯ РИСКА (если включена и доступны данные)
    if use_ai_optimization and symbol and user_data and AI_AVAILABLE and ai_position_sizing:
        try:
            ai_risk_pct, _, _ = ai_position_sizing.calculate_ai_optimized_position_size(
                symbol=symbol,
                side="long",  # Будет переопределено при вызове
                df=df,
                current_index=i,
                user_data=user_data,
                base_risk_pct=Decimal("2.0"),
                base_leverage=Decimal("1.0")
            )
            logger.info("🤖 ИИ-оптимизированный риск для %s: %.1f%%", symbol, float(ai_risk_pct))
            return Decimal(str(ai_risk_pct))
        except Exception as e:
            logger.warning("⚠️ ИИ-оптимизация риска недоступна для %s: %s, используем стандартный расчет", symbol, e)

    try:
        # Получаем ATR для расчета волатильности
        atr_val = df.get("atr", pd.Series([0] * len(df))).iloc[i]
        if pd.isna(atr_val) or atr_val == 0:
            # Рассчитываем ATR вручную если нет
            high_low = df["high"].iloc[i - 14:i] - df["low"].iloc[i - 14:i]
            high_close = np.abs(df["high"].iloc[i - 14:i] - df["close"].iloc[i - 13:i])
            low_close = np.abs(df["low"].iloc[i - 14:i] - df["close"].iloc[i - 13:i])
            atr_val = np.maximum(high_low, np.maximum(high_close, low_close)).mean()

        atr = Decimal(str(atr_val))
        
        # Получаем цену для нормализации ATR
        current_price = Decimal(str(df["close"].iloc[i]))
        atr_pct = (atr / current_price) * Decimal("100") if current_price > 0 else Decimal("2.0")

        # Базовый риск
        base_risk = Decimal("2.0")

        # Коэффициенты для расчета
        volatility_factor = Decimal("1.0") + (atr_pct - Decimal("2.0")) * Decimal("0.1")  # Адаптация к волатильности
        market_condition_factor = Decimal("1.0")  # Можно добавить анализ рыночных условий

        # Динамический риск
        dynamic_risk = base_risk * volatility_factor * market_condition_factor

        # Ограничения: 1-5% (согласно инвариантам TradeSignal)
        dynamic_risk = max(Decimal("0.1"), min(Decimal("5.0"), dynamic_risk))

        logger.debug(
            "Динамический риск: ATR=%.3f%%, base=%.1f%%, result=%.1f%%",
            float(atr_pct), float(base_risk), float(dynamic_risk)
        )

        # Валидация инварианта риска (превентивно)
        if not (Decimal("0.1") <= dynamic_risk <= Decimal("10.0")):
            logger.error("Критическое нарушение инварианта риска: %.2f%%", float(dynamic_risk))
            return Decimal("2.0")

        return dynamic_risk

    except Exception as e:
        logger.error("Ошибка в get_dynamic_risk_pct для %s: %s", symbol, e)
        return Decimal("2.0")


def get_dynamic_sl_level(df: pd.DataFrame, i: int, side: str = "long", base_sl_pct: Decimal = Decimal("2.0"),
                         symbol: Optional[str] = None, use_ai_optimization: bool = True,
                         levels_detector: Any = None) -> Decimal:
    """
    Динамический расчет уровня Stop Loss на основе ATR с опциональной AI-оптимизацией
    и защитой за уровнями поддержки/сопротивления.
    
    Args:
        df: DataFrame с данными OHLCV и индикаторами
        i: Индекс текущей свечи
        side: Сторона позиции ("long" или "short")
        base_sl_pct: Базовый процент SL
        symbol: Торговый символ (для AI-оптимизации)
        use_ai_optimization: Использовать ли AI-оптимизацию
        levels_detector: Детектор уровней (опционально)
        
    Returns:
        Decimal: Динамический уровень SL в процентах
    """
    if i < 14:
        return base_sl_pct

    try:
        # 1. Попытка AI-оптимизации
        if use_ai_optimization and symbol:
            try:
                from ai_sl_optimizer import get_ai_sl_optimizer
                ai_optimizer = get_ai_sl_optimizer()
                ai_sl = Decimal(str(ai_optimizer.calculate_ai_optimized_sl(
                    symbol, side.upper(), df, i, float(base_sl_pct)
                )))
                logger.debug("🤖 ИИ-оптимизированный SL для %s %s: %.2f%%", symbol, side, float(ai_sl))
                return ai_sl
            except (ImportError, AttributeError, Exception) as e:
                logger.debug("⚠️ AI-оптимизация SL недоступна для %s: %s, используем стандартный расчет", symbol, e)

        # 2. Стандартный расчет на основе ATR
        atr_val = df.get("atr", pd.Series([0] * len(df))).iloc[i]
        if pd.isna(atr_val) or atr_val == 0:
            # Рассчитываем ATR вручную если нет в DataFrame
            high_low = df["high"].iloc[i - 14:i] - df["low"].iloc[i - 14:i]
            high_close = np.abs(df["high"].iloc[i - 14:i] - df["close"].iloc[i - 13:i])
            low_close = np.abs(df["low"].iloc[i - 14:i] - df["close"].iloc[i - 13:i])
            atr_val = np.maximum(high_low, np.maximum(high_close, low_close)).mean()

        atr = Decimal(str(atr_val))
        current_price = Decimal(str(df["close"].iloc[i]))
        atr_pct = (atr / current_price) * Decimal("100") if current_price > 0 else base_sl_pct

        # Динамический SL на основе ATR (обычно 2.0x ATR)
        dynamic_sl = atr_pct * Decimal("2.0")

        # 3. 🛡️ ЗАЩИТА ЗА УРОВНЯМИ (Smart Stop Loss)
        # Если детектор не передан, пытаемся получить глобальный
        if levels_detector is None:
            try:
                from src.filters.static_levels import get_levels_detector
                levels_detector = get_levels_detector()
            except ImportError:
                pass

        if levels_detector and hasattr(levels_detector, 'find_levels'):
            try:
                # Находим уровни на текущем DataFrame
                levels = levels_detector.find_levels(df.iloc[:i+1])
                
                if side.lower() == "long":
                    # Ищем ближайшую поддержку
                    support = levels_detector.get_nearest_support(float(current_price), levels.get('support', []))
                    if support:
                        # Стоп должен быть за поддержкой (на 0.2% ниже)
                        level_sl_pct = (current_price - Decimal(str(support))) / current_price * Decimal("100") + Decimal("0.2")
                        # Если стоп за уровнем адекватный (не слишком далеко), используем его
                        if level_sl_pct > dynamic_sl and level_sl_pct < Decimal("5.0"):
                            logger.info("🛡️ [Smart SL] %s LONG: Стоп перенесен за уровень поддержки: %.2f%% -> %.2f%%", 
                                       symbol or "Asset", float(dynamic_sl), float(level_sl_pct))
                            dynamic_sl = level_sl_pct
                else:
                    # Ищем ближайшее сопротивление
                    resistance = levels_detector.get_nearest_resistance(float(current_price), levels.get('resistance', []))
                    if resistance:
                        # Стоп должен быть за сопротивлением (на 0.2% выше)
                        level_sl_pct = (Decimal(str(resistance)) - current_price) / current_price * Decimal("100") + Decimal("0.2")
                        # Если стоп за уровнем адекватный, используем его
                        if level_sl_pct > dynamic_sl and level_sl_pct < Decimal("5.0"):
                            logger.info("🛡️ [Smart SL] %s SHORT: Стоп перенесен за уровень сопротивления: %.2f%% -> %.2f%%", 
                                       symbol or "Asset", float(dynamic_sl), float(level_sl_pct))
                            dynamic_sl = level_sl_pct
            except Exception as e:
                logger.debug("⚠️ Ошибка при расчете защищенного SL для %s: %s", symbol, e)

        # Ограничения: 1-8% (жёсткие рамки безопасности)
        dynamic_sl = max(Decimal("1.0"), min(Decimal("8.0"), dynamic_sl))

        logger.debug(
            "Финальный Динамический SL: ATR=%.3f%%, side=%s, result=%.1f%%",
            float(atr_pct), side, float(dynamic_sl)
        )

        return dynamic_sl

    except Exception as e:
        logger.error("Ошибка в get_dynamic_sl_level для %s: %s", symbol, e)
        return base_sl_pct


from src.core.contracts import precondition, postcondition
from src.core.self_validation import get_validation_manager
from src.core.invariants import register_all_invariants
from src.core.profiling import profile

# Регистрируем инварианты при импорте
try:
    register_all_invariants()
except Exception:
    pass  # Если уже зарегистрированы, игнорируем


@profile(threshold_ms=10.0)
@precondition(
    lambda df, i, side, trade_mode, adjust_for_fees: (
        df is not None and not df.empty and
        isinstance(i, int) and i >= 0 and
        side in ("long", "short") and
        trade_mode in ("spot", "futures") and
        isinstance(adjust_for_fees, bool)
    ),
    "Invalid input: df must be non-empty DataFrame, i must be non-negative int, side must be 'long' or 'short'"
)
@postcondition(
    lambda result, df, i, side, trade_mode, adjust_for_fees: (
        isinstance(result, tuple) and len(result) == 2 and
        all(isinstance(x, (int, float, Decimal)) and Decimal("0.5") <= Decimal(str(x)) <= Decimal("15.0") for x in result) and
        result[1] > result[0]  # TP2 > TP1
    ),
    "Invalid output: result must be tuple of (TP1, TP2) with TP1 in [0.5, 10.0]%, TP2 in [1.0, 15.0]%, and TP2 > TP1"
)
def get_dynamic_tp_levels(df: pd.DataFrame, i: int, side: str = "long", 
                          trade_mode: str = "spot", adjust_for_fees: bool = True) -> Tuple[Decimal, Decimal]:
    """
    Динамический расчет уровней Take Profit на основе ATR
    
    Args:
        df: DataFrame с данными OHLCV и индикаторами
        i: Индекс текущей свечи
        side: Сторона позиции ("long" или "short")
        trade_mode: Режим торговли ("spot" или "futures")
        adjust_for_fees: Учитывать ли комиссии при расчете TP
        
    Returns:
        Tuple[Decimal, Decimal]: (TP1, TP2) в процентах
    """
    if i < 14:
        base_tp1, base_tp2 = Decimal("2.0"), Decimal("4.0")
        if adjust_for_fees:
            # Используем функцию из shared_utils для учета комиссий
            try:
                from shared_utils import adjust_tp_for_fees
                base_tp1 = Decimal(str(adjust_tp_for_fees(float(base_tp1), trade_mode)))
                base_tp2 = Decimal(str(adjust_tp_for_fees(float(base_tp2), trade_mode)))
            except ImportError:
                pass  # Если не доступно, используем базовые значения
        return (base_tp1, base_tp2)

    try:
        # Получаем ATR
        atr_val = df.get("atr", pd.Series([0] * len(df))).iloc[i]
        if pd.isna(atr_val) or atr_val == 0:
            # Рассчитываем ATR вручную если нет
            high_low = df["high"].iloc[i - 14:i] - df["low"].iloc[i - 14:i]
            high_close = np.abs(df["high"].iloc[i - 14:i] - df["close"].iloc[i - 13:i])
            low_close = np.abs(df["low"].iloc[i - 14:i] - df["close"].iloc[i - 13:i])
            atr_val = np.maximum(high_low, np.maximum(high_close, low_close)).mean()

        atr = Decimal(str(atr_val))
        current_price = Decimal(str(df["close"].iloc[i]))
        atr_pct = (atr / current_price) * Decimal("100") if current_price > 0 else Decimal("2.0")

        # Динамические TP на основе ATR
        # TP1 = ATR * 1.5
        # TP2 = ATR * 3.0
        tp1 = atr_pct * Decimal("1.5")
        tp2 = atr_pct * Decimal("3.0")

        # Ограничения: TP1 (0.5-10%), TP2 (1-15%)
        tp1 = max(Decimal("0.5"), min(Decimal("10.0"), tp1))
        tp2 = max(Decimal("1.0"), min(Decimal("15.0"), tp2))

        # TP2 должен быть больше TP1
        if tp2 <= tp1:
            tp2 = tp1 * Decimal("2.0")

        # 💰 Корректировка с учетом комиссий
        if adjust_for_fees:
            try:
                from shared_utils import adjust_tp_for_fees
                tp1 = Decimal(str(adjust_tp_for_fees(float(tp1), trade_mode)))
                tp2 = Decimal(str(adjust_tp_for_fees(float(tp2), trade_mode)))
                logger.debug(
                    "💰 Динамические TP с учетом комиссий: ATR=%.3f%%, TP1=%.1f%%, TP2=%.1f%%",
                    float(atr_pct), float(tp1), float(tp2)
                )
            except ImportError:
                logger.debug(
                    "Динамические TP (shared_utils unavailable): ATR=%.3f%%, TP1=%.1f%%, TP2=%.1f%%",
                    float(atr_pct), float(tp1), float(tp2)
                )
        else:
            logger.debug(
                "Динамические TP: ATR=%.3f%%, TP1=%.1f%%, TP2=%.1f%%",
                float(atr_pct), float(tp1), float(tp2)
            )

        return (tp1, tp2)

    except Exception as e:
        logger.error("Ошибка в get_dynamic_tp_levels: %s", e)
        return (Decimal("2.0"), Decimal("4.0"))


@profile(threshold_ms=5.0)
@precondition(
    lambda deposit, risk_pct, entry_price, stop_loss_price, leverage: (
        Decimal(str(deposit)) > 0 and
        Decimal("0.1") <= Decimal(str(risk_pct)) <= Decimal("10.0") and
        Decimal(str(entry_price)) > 0 and
        Decimal(str(stop_loss_price)) > 0 and
        Decimal("1.0") <= Decimal(str(leverage)) <= Decimal("20.0")
    ),
    "Invalid input: deposit > 0, risk_pct in [0.1, 10.0]%, entry_price > 0, stop_loss_price > 0, leverage in [1.0, 20.0]x"
)
@postcondition(
    lambda result, deposit, risk_pct, entry_price, stop_loss_price, leverage: (
        isinstance(result, (int, float, Decimal)) and Decimal(str(result)) >= 0
    ),
    "Invalid output: position size must be non-negative number"
)
def calculate_position_size(
    deposit: Decimal,
    risk_pct: Decimal,
    entry_price: Decimal,
    stop_loss_price: Decimal,
    leverage: Decimal = Decimal("1.0")
) -> Decimal:
    """
    Расчет размера позиции на основе риска
    
    Args:
        deposit: Размер депозита
        risk_pct: Процент риска
        entry_price: Цена входа
        stop_loss_price: Цена стоп-лосса
        leverage: Плечо
        
    Returns:
        Decimal: Размер позиции в базовой валюте
    """
    try:
        # Рассчитываем риск в валюте депозита
        risk_amount = deposit * (risk_pct / Decimal("100.0"))
        
        # Рассчитываем расстояние до стоп-лосса
        stop_distance = abs(entry_price - stop_loss_price)
        if stop_distance == 0:
            return Decimal("0.0")
        
        # Рассчитываем размер позиции
        position_size = (risk_amount * leverage) / stop_distance
        
        return position_size

    except Exception as e:
        logger.error("Ошибка в calculate_position_size: %s", e)
        return Decimal("0.0")


def recalculate_balance_and_risks(user_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Пересчет баланса и рисков с учетом открытых позиций
    
    Args:
        user_data: Данные пользователя
        
    Returns:
        Dict с обновленными данными баланса или None при ошибке
    """
    try:
        deposit = Decimal(str(user_data.get("deposit", "1000.0")))
        positions = user_data.get("positions", [])
        
        # Рассчитываем общий риск по открытым позициям
        total_risk_amount = Decimal("0.0")
        
        for position in positions:
            if position.get("status") == "open":
                position_size = Decimal(str(position.get("size", "0.0")))
                entry_price = Decimal(str(position.get("entry_price", "0.0")))
                risk_pct = Decimal(str(position.get("risk_pct", "2.0")))
                leverage = Decimal(str(position.get("leverage", "1.0")))
                
                # Рассчитываем риск по позиции
                position_risk = (position_size * entry_price * risk_pct / Decimal("100.0")) / leverage
                total_risk_amount += position_risk
        
        # Рассчитываем свободные средства
        free_deposit = deposit - total_risk_amount
        
        # Обновленный депозит (с учетом открытых позиций)
        updated_deposit = deposit
        
        return {
            "deposit": float(deposit),
            "free_deposit": float(max(Decimal("0.0"), free_deposit)),
            "total_risk_amount": float(total_risk_amount),
            "updated_deposit": float(updated_deposit),
            "open_positions": len([p for p in positions if p.get("status") == "open"])
        }

    except Exception as e:
        logger.error("Ошибка в recalculate_balance_and_risks: %s", e)
        return None
