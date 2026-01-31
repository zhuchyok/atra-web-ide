#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, Optional, Tuple

from src.core.base_strategy import BaseStrategy
from src.signals.indicators import add_technical_indicators
from src.risk.correlation_risk import CorrelationRiskManager
from src.shared.utils.datetime_utils import get_utc_now

logger = logging.getLogger(__name__)

class SniperTrendStrategy(BaseStrategy):
    """
    Sniper Trend Strategy v4.5 (Based on Plan N)
    Трендовый снайпинг на 1H таймфрейме с фильтрацией по 4H EMA и ATR.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.name = "SniperTrend_V4"
        self.risk_manager = CorrelationRiskManager()
        
        # Настройки из Плана N
        self.rr_ratio = Decimal("3.5")
        self.atr_sl_mult = Decimal("1.5")
        self.rsi_long = 60
        self.rsi_short = 40
        self.leverage = 2
        
    async def analyze(self, symbol: str, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """Анализ символа и генерация сигнала"""
        try:
            if len(df) < 200:
                return None
            
            # 1. Расчет индикаторов
            df = add_technical_indicators(df, rsi_period=14, ema_periods=[200], atr_period=14)
            df['atr_sma'] = df['atr'].rolling(window=100).mean()
            
            # 2. Получение 4H тренда (упрощенно из текущего DF)
            df_4h = df.set_index('timestamp').resample('4h').agg({'close': 'last'}).dropna()
            import ta
            df_4h['ema200_4h'] = ta.trend.ema_indicator(df_4h['close'], window=200)
            
            # Берем последнюю актуальную 4H EMA
            last_ema4h = df_4h['ema200_4h'].iloc[-1]
            if np.isnan(last_ema4h):
                return None
            
            last_ema4h = Decimal(str(last_ema4h))
            row = df.iloc[-1]
            prev = df.iloc[-2]
            
            close = Decimal(str(row['close']))
            rsi = row['rsi']
            atr = row['atr']
            atr_sma = row['atr_sma']
            
            # 3. Логика входа
            side = None
            if close > last_ema4h and rsi > self.rsi_long and atr > atr_sma and close > Decimal(str(prev['high'])):
                side = "BUY"
            elif close < last_ema4h and rsi < self.rsi_short and atr > atr_sma and close < Decimal(str(prev['low'])):
                side = "SELL"
                
            if not side:
                return None
            
            # 4. Проверка корреляционных рисков
            risk_check = self.risk_manager.check_portfolio_correlation_risk(symbol, side)
            if not risk_check['allowed']:
                logger.warning(f"⚠️ {self.name}: Сигнал {side} по {symbol} отклонен риск-менеджером: {risk_check['reason']}")
                return None

            # 5. Формирование параметров сделки
            atr_val = Decimal(str(atr))
            sl_dist = atr_val * self.atr_sl_mult
            
            if side == "BUY":
                sl = close - sl_dist
                tp = close + (sl_dist * self.rr_ratio)
            else:
                sl = close + sl_dist
                tp = close - (sl_dist * self.rr_ratio)
                
            return {
                'symbol': symbol,
                'side': side,
                'entry_price': close,
                'stop_loss': sl,
                'take_profit': tp,
                'leverage': self.leverage,
                'strategy': self.name,
                'timestamp': get_utc_now()
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа в {self.name} для {symbol}: {e}")
            return None

