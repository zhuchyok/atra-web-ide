"""
Order Flow Filter - фильтр на основе индикаторов потока ордеров

Использует:
- Cumulative Delta Volume (CDV) - накопленное давление
- Volume Delta - давление на текущей свече
- Buy/Sell Pressure Ratio - соотношение давления

Фильтрует сигналы, оставляя только те, которые подтверждены Order Flow.
"""

import logging
from typing import Tuple, Optional
import pandas as pd

logger = logging.getLogger(__name__)

# Импорты с fallback
try:
    from src.analysis.order_flow import CumulativeDeltaVolume, VolumeDelta, PressureRatio
    ORDER_FLOW_AVAILABLE = True
except ImportError:
    ORDER_FLOW_AVAILABLE = False
    logger.warning("Order Flow модули недоступны")


def check_order_flow_filter(
    df: pd.DataFrame,
    i: int,
    side: str,
    strict_mode: bool = True,
) -> Tuple[bool, Optional[str]]:
    """
    Проверяет, соответствует ли сигнал Order Flow фильтрам
    
    Логика:
    - LONG: нужны подтверждения покупок (положительный CDV, Volume Delta, Pressure Ratio > 1.0)
    - SHORT: нужны подтверждения продаж (отрицательный CDV, Volume Delta, Pressure Ratio < 1.0)
    - В строгом режиме: требуются более сильные подтверждения
    
    Args:
        df: DataFrame с данными OHLCV
        i: Индекс текущей свечи
        side: "long" или "short"
        strict_mode: True для строгого режима (более жесткие фильтры)
    
    Returns:
        Tuple[passed, reason]
    """
    try:
        if not ORDER_FLOW_AVAILABLE:
            return True, None  # Если модуль недоступен, пропускаем фильтр
        
        if i >= len(df):
            return False, "Индекс выходит за границы DataFrame"
        
        # Инициализируем индикаторы
        cdv = CumulativeDeltaVolume(lookback=20)
        vd = VolumeDelta()
        pr = PressureRatio(lookback=5)
        
        # Получаем значения индикаторов
        cdv_signal = cdv.get_signal(df, i)
        vd_signal = vd.get_signal(df, i)
        pr_value = pr.get_value(df, i)
        cdv_value = cdv.get_value(df, i)
        
        if side.lower() == "long":
            # LONG: нужны подтверждения покупок
            
            # Проверка CDV
            cdv_ok = False
            if cdv_signal == 'long':
                cdv_ok = True
            elif cdv_signal is None and cdv_value is not None:
                # Если CDV нейтральный, но положительный - OK
                if strict_mode:
                    cdv_ok = cdv_value > 0  # В строгом режиме требуем положительный CDV
                else:
                    cdv_ok = True  # В мягком режиме нейтральный CDV допустим
            
            # Проверка Volume Delta
            vd_ok = False
            if vd_signal == 'long':
                vd_ok = True
            elif vd_signal is None:
                # Если Volume Delta нейтральный, проверяем значение
                vd_value = vd.get_value(df, i)
                if vd_value is not None:
                    if strict_mode:
                        vd_ok = vd_value > 0  # В строгом режиме требуем положительный Volume Delta
                    else:
                        vd_ok = True  # В мягком режиме нейтральный допустим
            
            # Проверка Pressure Ratio
            # Используем параметры из config.py
            try:
                from config import ORDER_FLOW_FILTER_CONFIG
                pr_threshold = ORDER_FLOW_FILTER_CONFIG.get("pr_threshold", 0.5)
                required_confirmations = ORDER_FLOW_FILTER_CONFIG.get("required_confirmations", 0)
            except ImportError:
                pr_threshold = 0.5
                required_confirmations = 0
            
            pr_ok = False
            if pr_value is not None:
                pr_ok = pr_value > pr_threshold
            else:
                pr_ok = not strict_mode  # В мягком режиме допустимо отсутствие данных
            
            # Комбинированная проверка
            # Используем параметры из config.py
            # Если required_confirmations = 0, проверяем только PR
            if required_confirmations == 0:
                # Только PR (оптимизированный режим)
                return pr_ok, None if pr_ok else f"Pressure Ratio {pr_value:.3f} <= {pr_threshold}"
            
            # Если required_confirmations > 0, используем комбинированную проверку
            confirmations = sum([cdv_ok, vd_ok, pr_ok])
            
            if confirmations >= required_confirmations:
                return True, None
            
            reasons = []
            if not cdv_ok:
                reasons.append(f"CDV не подтверждает покупки (signal={cdv_signal}, value={cdv_value})")
            if not vd_ok:
                reasons.append(f"Volume Delta не подтверждает покупки (signal={vd_signal})")
            if not pr_ok:
                reasons.append(f"Pressure Ratio не подтверждает покупки (value={pr_value})")
            
            return False, f"LONG: недостаточно подтверждений Order Flow ({confirmations}/{required_confirmations}). {', '.join(reasons)}"
        
        elif side.lower() == "short":
            # SHORT: нужны подтверждения продаж
            
            # Проверка CDV
            cdv_ok = False
            if cdv_signal == 'short':
                cdv_ok = True
            elif cdv_signal is None and cdv_value is not None:
                # Если CDV нейтральный, но отрицательный - OK
                if strict_mode:
                    cdv_ok = cdv_value < 0  # В строгом режиме требуем отрицательный CDV
                else:
                    cdv_ok = True  # В мягком режиме нейтральный CDV допустим
            
            # Проверка Volume Delta
            vd_ok = False
            if vd_signal == 'short':
                vd_ok = True
            elif vd_signal is None:
                # Если Volume Delta нейтральный, проверяем значение
                vd_value = vd.get_value(df, i)
                if vd_value is not None:
                    if strict_mode:
                        vd_ok = vd_value < 0  # В строгом режиме требуем отрицательный Volume Delta
                    else:
                        vd_ok = True  # В мягком режиме нейтральный допустим
            
            # Проверка Pressure Ratio
            # Оптимизированные параметры: pr_threshold = 0.6
            pr_ok = False
            if pr_value is not None:
                # Для SHORT: PR должен быть < 1.0 (преобладание продаж)
                # Но используем более мягкий порог для ослабления фильтра
                pr_ok = pr_value < 1.0
            else:
                pr_ok = not strict_mode  # В мягком режиме допустимо отсутствие данных
            
            # Комбинированная проверка
            # Оптимизированные параметры: required_confirmations = 0 (только PR)
            # Если required_confirmations = 0, проверяем только PR
            if not strict_mode:
                # Мягкий режим: только PR (required_confirmations = 0)
                return pr_ok, None if pr_ok else f"Pressure Ratio {pr_value:.3f} >= 1.0"
            
            # Строгий режим: используем старую логику (для обратной совместимости)
            confirmations = sum([cdv_ok, vd_ok, pr_ok])
            required_confirmations = 2
            
            if confirmations >= required_confirmations:
                return True, None
            
            reasons = []
            if not cdv_ok:
                reasons.append(f"CDV не подтверждает продажи (signal={cdv_signal}, value={cdv_value})")
            if not vd_ok:
                reasons.append(f"Volume Delta не подтверждает продажи (signal={vd_signal})")
            if not pr_ok:
                reasons.append(f"Pressure Ratio не подтверждает продажи (value={pr_value})")
            
            return False, f"SHORT: недостаточно подтверждений Order Flow ({confirmations}/{required_confirmations}). {', '.join(reasons)}"
        
        return True, None
        
    except Exception as e:
        logger.error(f"Ошибка в check_order_flow_filter: {e}")
        return True, None  # В случае ошибки пропускаем фильтр

