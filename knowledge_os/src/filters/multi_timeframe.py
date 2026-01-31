#!/usr/bin/env python3
"""
Multi-Timeframe Confirmation System
Подтверждение сигналов на старших таймфреймах
"""

import logging
import pandas as pd
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class MultiTimeframeConfirmer:
    """Система подтверждения сигналов на старших таймфреймах"""
    
    def __init__(self):
        self.enabled = True
        self.min_confidence = 0.6  # 60% минимальное подтверждение
        
    async def check_confirmation(self, symbol: str, signal_type: str, price: float, df_h4: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Проверяет подтверждение сигнала на старших таймфреймах
        
        Args:
            symbol: Торговый символ
            signal_type: Тип сигнала (LONG/SHORT)
            price: Цена входа
            df_h4: Данные на H4 (если доступны)
            
        Returns:
            Dict с результатами подтверждения
        """
        if not self.enabled:
            return {
                "confirmed": True,
                "confidence": 1.0,
                "reason": "MTF confirmation disabled"
            }
        
        try:
            # Если данные H4 доступны, используем их
            if df_h4 is not None and len(df_h4) > 20:
                return await self._check_h4_confirmation(df_h4, signal_type, price)
            
            # Fallback: используем текущие данные как подтверждение
            return {
                "confirmed": True,
                "confidence": 0.8,
                "reason": "H4 data not available, using current timeframe"
            }
            
        except Exception as e:
            logger.debug("[MTF] Ошибка подтверждения для %s: %s", symbol, e)
            return {
                "confirmed": True,
                "confidence": 0.5,
                "reason": f"Error: {e}"
            }
    
    async def _check_h4_confirmation(self, df_h4: pd.DataFrame, signal_type: str, price: float) -> Dict[str, Any]:
        """Проверяет подтверждение на H4"""
        try:
            # Проверяем наличие необходимых колонок
            required_cols = ['close', 'ema_fast', 'ema_slow']
            missing_cols = [col for col in required_cols if col not in df_h4.columns]
            
            if missing_cols:
                return {
                    "confirmed": True,
                    "confidence": 0.5,
                    "reason": f"Missing columns: {missing_cols}"
                }
            
            current_price = df_h4['close'].iloc[-1]
            ema_fast = df_h4['ema_fast'].iloc[-1]
            ema_slow = df_h4['ema_slow'].iloc[-1]
            
            confidence = 0.5  # Базовая уверенность
            
            if signal_type.upper() == "LONG":
                # Для LONG: цена выше EMA на H4
                if current_price > ema_fast and ema_fast > ema_slow:
                    confidence = 0.9
                    confirmed = True
                    reason = "H4 bullish trend confirmed"
                elif current_price > ema_slow:
                    confidence = 0.7
                    confirmed = True
                    reason = "H4 price above slow EMA"
                else:
                    confidence = 0.4
                    confirmed = False
                    reason = "H4 not bullish"
            else:  # SHORT
                # Для SHORT: цена ниже EMA на H4
                if current_price < ema_fast and ema_fast < ema_slow:
                    confidence = 0.9
                    confirmed = True
                    reason = "H4 bearish trend confirmed"
                elif current_price < ema_slow:
                    confidence = 0.7
                    confirmed = True
                    reason = "H4 price below slow EMA"
                else:
                    confidence = 0.4
                    confirmed = False
                    reason = "H4 not bearish"
            
            return {
                "confirmed": confirmed,
                "confidence": confidence,
                "reason": reason
            }
            
        except Exception as e:
            logger.error("[MTF] Ошибка проверки H4: %s", e)
            return {
                "confirmed": True,
                "confidence": 0.5,
                "reason": f"H4 check error: {e}"
            }
    
    def is_confirmed(self, confidence: float) -> bool:
        """Проверяет, достаточно ли подтверждения"""
        return confidence >= self.min_confidence
