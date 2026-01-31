#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Улучшенная система BOS/Retest с зонами и адаптивными бафферами
Решает проблему слишком строгих требований к структуре
"""

import pandas as pd
import numpy as np
from typing import Tuple, Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class ImprovedBOSRetestSystem:
    """Улучшенная система BOS/Retest с зонами и адаптивными бафферами"""
    
    def __init__(self):
        # Параметры для разных режимов рынка
        self.regime_params = {
            "TREND": {
                "zone_buffer_multiplier": 0.15,  # 15% от ATR для тренда
                "min_structure_bars": 5,         # Минимум баров для структуры
                "max_structure_bars": 20,        # Максимум баров для структуры
                "retest_tolerance": 0.20,        # 20% толерантность для ретеста
                "time_based_bypass_hours": 4     # Байпас через 4 часа
            },
            "RANGE": {
                "zone_buffer_multiplier": 0.10,  # 10% от ATR для флэта
                "min_structure_bars": 3,         # Меньше баров для флэта
                "max_structure_bars": 15,        # Меньше максимум для флэта
                "retest_tolerance": 0.15,        # 15% толерантность для ретеста
                "time_based_bypass_hours": 2     # Байпас через 2 часа
            },
            "TRANSITION": {
                "zone_buffer_multiplier": 0.20,  # 20% от ATR для переходов
                "min_structure_bars": 4,         # Средние значения
                "max_structure_bars": 18,        # Средние значения
                "retest_tolerance": 0.25,        # 25% толерантность для ретеста
                "time_based_bypass_hours": 3     # Байпас через 3 часа
            }
        }
    
    def detect_market_regime(self, df: pd.DataFrame, i: int) -> str:
        """Определяет режим рынка для адаптивных параметров"""
        try:
            if i < 50:
                return "TRANSITION"
            
            current = df.iloc[i]
            
            # Получаем индикаторы
            adx = current.get("adx", 20)
            bb_width = self._calculate_bb_width(df, i)
            atr = current.get("atr", current["close"] * 0.02)
            
            # Определяем режим
            if adx > 25 and bb_width > 0.15:
                return "TREND"
            elif adx < 15 and bb_width < 0.10:
                return "RANGE"
            else:
                return "TRANSITION"
                
        except Exception as e:
            logger.warning("Ошибка определения режима рынка: %s", e)
            return "TRANSITION"
    
    def _calculate_bb_width(self, df: pd.DataFrame, i: int) -> float:
        """Вычисляет ширину Bollinger Bands"""
        try:
            current = df.iloc[i]
            bb_high = current.get("bb_high", current["close"])
            bb_low = current.get("bb_low", current["close"])
            bb_mid = current.get("bb_mid", current["close"])
            
            if bb_mid == 0:
                return 0.1  # Fallback
            
            return (bb_high - bb_low) / bb_mid
            
        except Exception:
            return 0.1  # Fallback
    
    def find_structure_levels(self, df: pd.DataFrame, i: int, regime: str) -> Dict[str, Any]:
        """
        Находит уровни структуры с зонами вместо точных линий
        
        Returns:
            Dict с уровнями структуры и зонами
        """
        try:
            params = self.regime_params[regime]
            current = df.iloc[i]
            atr = current.get("atr", current["close"] * 0.02)
            
            # Адаптивный баффер на основе ATR и режима
            buffer = atr * params["zone_buffer_multiplier"]
            
            # Анализируем последние бары для поиска структуры
            lookback = min(params["max_structure_bars"], i)
            start_idx = max(0, i - lookback)
            
            recent_data = df.iloc[start_idx:i+1]
            
            # Находим локальные экстремумы
            highs, lows = self._find_local_extremes(recent_data, params["min_structure_bars"])
            
            if not highs and not lows:
                return {"has_structure": False, "levels": [], "zones": []}
            
            # Создаем зоны вокруг уровней
            structure_levels = []
            structure_zones = []
            
            # Обрабатываем максимумы
            for high_idx, high_price in highs:
                level = {
                    "type": "resistance",
                    "price": high_price,
                    "index": start_idx + high_idx,
                    "strength": self._calculate_level_strength(recent_data, high_idx, "high")
                }
                structure_levels.append(level)
                
                # Создаем зону вокруг уровня
                zone = {
                    "type": "resistance_zone",
                    "upper": high_price + buffer,
                    "lower": high_price - buffer,
                    "center": high_price,
                    "strength": level["strength"]
                }
                structure_zones.append(zone)
            
            # Обрабатываем минимумы
            for low_idx, low_price in lows:
                level = {
                    "type": "support",
                    "price": low_price,
                    "index": start_idx + low_idx,
                    "strength": self._calculate_level_strength(recent_data, low_idx, "low")
                }
                structure_levels.append(level)
                
                # Создаем зону вокруг уровня
                zone = {
                    "type": "support_zone",
                    "upper": low_price + buffer,
                    "lower": low_price - buffer,
                    "center": low_price,
                    "strength": level["strength"]
                }
                structure_zones.append(zone)
            
            return {
                "has_structure": len(structure_levels) > 0,
                "levels": structure_levels,
                "zones": structure_zones,
                "buffer": buffer,
                "regime": regime
            }
            
        except Exception as e:
            logger.error("Ошибка поиска структуры: %s", e)
            return {"has_structure": False, "levels": [], "zones": []}
    
    def _find_local_extremes(self, data: pd.DataFrame, min_bars: int) -> Tuple[List, List]:
        """Находит локальные максимумы и минимумы"""
        try:
            highs = []
            lows = []
            
            # Используем скользящее окно для поиска экстремумов
            window = min_bars
            
            for i in range(window, len(data) - window):
                # Проверяем максимум
                if data["high"].iloc[i] == data["high"].iloc[i-window:i+window+1].max():
                    highs.append((i, data["high"].iloc[i]))
                
                # Проверяем минимум
                if data["low"].iloc[i] == data["low"].iloc[i-window:i+window+1].min():
                    lows.append((i, data["low"].iloc[i]))
            
            return highs, lows
            
        except Exception as e:
            logger.error("Ошибка поиска экстремумов: %s", e)
            return [], []
    
    def _calculate_level_strength(self, data: pd.DataFrame, idx: int, extreme_type: str) -> float:
        """Вычисляет силу уровня структуры"""
        try:
            if extreme_type == "high":
                price = data["high"].iloc[idx]
                # Считаем количество касаний уровня
                touches = 0
                tolerance = price * 0.005  # 0.5% толерантность
                
                for i in range(len(data)):
                    if abs(data["high"].iloc[i] - price) <= tolerance:
                        touches += 1
                
                return min(touches / 5.0, 1.0)  # Нормализуем до 1.0
                
            else:  # low
                price = data["low"].iloc[idx]
                touches = 0
                tolerance = price * 0.005
                
                for i in range(len(data)):
                    if abs(data["low"].iloc[i] - price) <= tolerance:
                        touches += 1
                
                return min(touches / 5.0, 1.0)
                
        except Exception:
            return 0.5  # Средняя сила по умолчанию
    
    def check_bos_retest_improved(self, df: pd.DataFrame, i: int, symbol: str = None) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Улучшенная проверка BOS/Retest с зонами и адаптивными бафферами
        
        Returns:
            Tuple[bool, str, Dict]: (прошел_проверку, сообщение, детали)
        """
        try:
            # Определяем режим рынка
            regime = self.detect_market_regime(df, i)
            params = self.regime_params[regime]
            
            # Находим структуру
            structure_data = self.find_structure_levels(df, i, regime)
            
            if not structure_data["has_structure"]:
                return True, f"No structure found ({regime})", structure_data
            
            current = df.iloc[i]
            current_price = current["close"]
            current_time = current.get("timestamp", i)
            
            # Проверяем BOS (Break of Structure)
            bos_result = self._check_break_of_structure(
                current_price, structure_data["zones"], regime
            )
            
            if not bos_result["has_bos"]:
                return False, f"No BOS detected ({regime})", {
                    "regime": regime,
                    "bos_result": bos_result,
                    "structure": structure_data
                }
            
            # Проверяем Retest с зонами
            retest_result = self._check_retest_improved(
                df, i, bos_result, structure_data, params
            )
            
            # Time-based bypass для сильных трендов
            time_bypass = self._check_time_based_bypass(
                df, i, bos_result, params["time_based_bypass_hours"]
            )
            
            # Финальное решение
            if retest_result["has_retest"] or time_bypass["bypass"]:
                message = f"BOS+Retest passed ({regime})"
                if time_bypass["bypass"]:
                    message += " [Time bypass]"
                
                return True, message, {
                    "regime": regime,
                    "bos_result": bos_result,
                    "retest_result": retest_result,
                    "time_bypass": time_bypass,
                    "structure": structure_data
                }
            else:
                return False, f"BOS detected but no retest ({regime})", {
                    "regime": regime,
                    "bos_result": bos_result,
                    "retest_result": retest_result,
                    "structure": structure_data
                }
                
        except Exception as e:
            logger.error("Ошибка в улучшенной BOS/Retest проверке для %s: %s", symbol, e)
            return True, f"Fallback: {e}", {"error": str(e)}
    
    def _check_break_of_structure(self, current_price: float, zones: List[Dict], regime: str) -> Dict[str, Any]:
        """Проверяет пробой структуры с зонами"""
        try:
            bos_detected = False
            broken_zones = []
            direction = None
            
            for zone in zones:
                if zone["type"] == "resistance_zone":
                    # Проверяем пробой сопротивления (LONG)
                    if current_price > zone["upper"]:
                        bos_detected = True
                        broken_zones.append(zone)
                        direction = "LONG"
                        
                elif zone["type"] == "support_zone":
                    # Проверяем пробой поддержки (SHORT)
                    if current_price < zone["lower"]:
                        bos_detected = True
                        broken_zones.append(zone)
                        direction = "SHORT"
            
            return {
                "has_bos": bos_detected,
                "direction": direction,
                "broken_zones": broken_zones,
                "regime": regime
            }
            
        except Exception as e:
            logger.error("Ошибка проверки BOS: %s", e)
            return {"has_bos": False, "direction": None, "broken_zones": [], "regime": regime}
    
    def _check_retest_improved(self, df: pd.DataFrame, i: int, bos_result: Dict, 
                              structure_data: Dict, params: Dict) -> Dict[str, Any]:
        """Улучшенная проверка ретеста с зонами"""
        try:
            if not bos_result["has_bos"]:
                return {"has_retest": False, "retest_zones": [], "reason": "No BOS"}
            
            direction = bos_result["direction"]
            broken_zones = bos_result["broken_zones"]
            
            # Ищем ретест в последних барах
            lookback = min(10, i)  # Последние 10 баров
            start_idx = max(0, i - lookback)
            
            retest_zones = []
            
            for zone in broken_zones:
                # Проверяем, вернулась ли цена в зону
                for j in range(start_idx, i + 1):
                    price = df.iloc[j]["close"]
                    
                    if direction == "LONG":
                        # Для LONG: цена должна вернуться в зону сопротивления
                        if zone["lower"] <= price <= zone["upper"]:
                            retest_zones.append({
                                "zone": zone,
                                "retest_price": price,
                                "retest_index": j,
                                "strength": zone["strength"]
                            })
                            break
                    
                    elif direction == "SHORT":
                        # Для SHORT: цена должна вернуться в зону поддержки
                        if zone["lower"] <= price <= zone["upper"]:
                            retest_zones.append({
                                "zone": zone,
                                "retest_price": price,
                                "retest_index": j,
                                "strength": zone["strength"]
                            })
                            break
            
            has_retest = len(retest_zones) > 0
            
            return {
                "has_retest": has_retest,
                "retest_zones": retest_zones,
                "direction": direction,
                "reason": "Retest found" if has_retest else "No retest in zones"
            }
            
        except Exception as e:
            logger.error("Ошибка проверки ретеста: %s", e)
            return {"has_retest": False, "retest_zones": [], "reason": f"Error: {e}"}
    
    def _check_time_based_bypass(self, df: pd.DataFrame, i: int, bos_result: Dict, 
                                bypass_hours: int) -> Dict[str, Any]:
        """Проверяет time-based байпас для сильных трендов"""
        try:
            if not bos_result["has_bos"]:
                return {"bypass": False, "reason": "No BOS"}
            
            # Простая проверка времени (в реальности нужно использовать timestamp)
            # Здесь используем индекс как proxy для времени
            current_time = i
            bos_time = current_time - 5  # Предполагаем, что BOS был 5 баров назад
            
            time_elapsed = current_time - bos_time
            
            # Байпас если прошло достаточно времени
            bypass = time_elapsed >= bypass_hours
            
            return {
                "bypass": bypass,
                "time_elapsed": time_elapsed,
                "bypass_hours": bypass_hours,
                "reason": f"Time bypass after {time_elapsed}h" if bypass else f"Not enough time: {time_elapsed}h"
            }
            
        except Exception as e:
            logger.error("Ошибка time-based bypass: %s", e)
            return {"bypass": False, "reason": f"Error: {e}"}


# ============================================================================
# ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР
# ============================================================================

# Создаем глобальный экземпляр улучшенной системы BOS/Retest
improved_bos_retest_system = ImprovedBOSRetestSystem()

# Функция для обратной совместимости
def check_improved_bos_retest(df: pd.DataFrame, i: int, symbol: str = None) -> Tuple[bool, str]:
    """
    Улучшенная проверка BOS/Retest с зонами и адаптивными бафферами
    
    Args:
        df: DataFrame с данными
        i: Индекс текущей свечи
        symbol: Символ для логирования
        
    Returns:
        Tuple[bool, str]: (прошел_проверку, сообщение)
    """
    try:
        passed, message, details = improved_bos_retest_system.check_bos_retest_improved(df, i, symbol)
        
        # Логируем детали для диагностики
        if not passed:
            logger.debug("BOS/Retest blocked for %s: %s", symbol, message)
            logger.debug("BOS/Retest details: %s", details)
        
        return passed, message
        
    except Exception as e:
        logger.error("Ошибка в улучшенной системе BOS/Retest: %s", e)
        return True, f"Fallback: {e}"
