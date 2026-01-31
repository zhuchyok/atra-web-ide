#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Triple Barrier Labeling - Marcos López de Prado метод
Улучшение Win Rate через правильную разметку данных для ML

Ответственный: Дмитрий (ML Engineer)
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, Tuple, List
from decimal import Decimal
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class TripleBarrierLabeling:
    """
    Triple Barrier Labeling для ML моделей
    
    Метод из "Advances in Financial Machine Learning" (Marcos López de Prado)
    
    Три барьера:
    1. Верхний барьер (TP) - целевая прибыль
    2. Нижний барьер (SL) - стоп-лосс
    3. Временной барьер - максимальное время удержания
    
    Label = 1 если достигнут TP до SL и временного барьера
    Label = 0 если достигнут SL или временной барьер
    """
    
    def __init__(
        self,
        tp_pct: float = 0.03,  # 3% TP
        sl_pct: float = 0.015,  # 1.5% SL
        max_hold_periods: int = 24,  # Максимум 24 часа (24 свечи на 1h)
        use_atr: bool = True
    ):
        self.tp_pct = tp_pct
        self.sl_pct = sl_pct
        self.max_hold_periods = max_hold_periods
        self.use_atr = use_atr
    
    def label_trade(
        self,
        df: pd.DataFrame,
        entry_index: int,
        entry_price: float,
        side: str = "LONG"
    ) -> Tuple[int, str, float, Optional[float]]:
        """
        Размечает сделку по triple barrier методу
        
        Args:
            df: DataFrame с OHLCV данными
            entry_index: Индекс входа
            entry_price: Цена входа
            side: Направление (LONG/SHORT)
        
        Returns:
            (label, barrier_hit, profit_pct, exit_index)
            label: 1 = прибыль, 0 = убыток
            barrier_hit: 'TP', 'SL', 'TIME'
            profit_pct: Процент прибыли/убытка
            exit_index: Индекс выхода
        """
        try:
            if entry_index >= len(df) - 1:
                return 0, 'TIME', 0.0, entry_index
            
            # Рассчитываем барьеры
            if side.upper() == "LONG":
                tp_price = entry_price * (1 + self.tp_pct)
                sl_price = entry_price * (1 - self.sl_pct)
            else:  # SHORT
                tp_price = entry_price * (1 - self.tp_pct)
                sl_price = entry_price * (1 + self.sl_pct)
            
            # Адаптируем барьеры по ATR если включено
            if self.use_atr and 'atr' in df.columns and entry_index < len(df):
                atr = df['atr'].iloc[entry_index]
                if atr > 0:
                    atr_pct = (atr / entry_price) * 100
                    # Используем ATR для динамических барьеров
                    if side.upper() == "LONG":
                        tp_price = entry_price * (1 + max(self.tp_pct, atr_pct * 1.5 / 100))
                        sl_price = entry_price * (1 - max(self.sl_pct, atr_pct * 1.0 / 100))
                    else:
                        tp_price = entry_price * (1 - max(self.tp_pct, atr_pct * 1.5 / 100))
                        sl_price = entry_price * (1 + max(self.sl_pct, atr_pct * 1.0 / 100))
            
            # Проверяем барьеры на следующих свечах
            lookahead = min(self.max_hold_periods, len(df) - entry_index - 1)
            
            for i in range(1, lookahead + 1):
                current_idx = entry_index + i
                if current_idx >= len(df):
                    break
                
                row = df.iloc[current_idx]
                high = row['high']
                low = row['low']
                close = row['close']
                
                if side.upper() == "LONG":
                    # Проверяем TP (верхний барьер)
                    if high >= tp_price:
                        profit_pct = (tp_price - entry_price) / entry_price * 100
                        return 1, 'TP', profit_pct, current_idx
                    
                    # Проверяем SL (нижний барьер)
                    if low <= sl_price:
                        profit_pct = (sl_price - entry_price) / entry_price * 100
                        return 0, 'SL', profit_pct, current_idx
                else:  # SHORT
                    # Проверяем TP (нижний барьер)
                    if low <= tp_price:
                        profit_pct = (entry_price - tp_price) / entry_price * 100
                        return 1, 'TP', profit_pct, current_idx
                    
                    # Проверяем SL (верхний барьер)
                    if high >= sl_price:
                        profit_pct = (entry_price - sl_price) / entry_price * 100
                        return 0, 'SL', profit_pct, current_idx
            
            # Временной барьер достигнут
            exit_price = df['close'].iloc[entry_index + lookahead]
            if side.upper() == "LONG":
                profit_pct = (exit_price - entry_price) / entry_price * 100
            else:
                profit_pct = (entry_price - exit_price) / entry_price * 100
            
            label = 1 if profit_pct > 0 else 0
            return label, 'TIME', profit_pct, entry_index + lookahead
            
        except Exception as e:
            logger.error(f"❌ Ошибка triple barrier labeling: {e}", exc_info=True)
            return 0, 'ERROR', 0.0, entry_index
    
    def label_trades_batch(
        self,
        df: pd.DataFrame,
        entry_indices: List[int],
        entry_prices: List[float],
        sides: List[str]
    ) -> pd.DataFrame:
        """
        Размечает батч сделок
        
        Returns:
            DataFrame с колонками: label, barrier_hit, profit_pct, exit_index
        """
        results = []
        
        for entry_idx, entry_price, side in zip(entry_indices, entry_prices, sides):
            label, barrier, profit, exit_idx = self.label_trade(df, entry_idx, entry_price, side)
            results.append({
                'entry_index': entry_idx,
                'entry_price': entry_price,
                'side': side,
                'label': label,
                'barrier_hit': barrier,
                'profit_pct': profit,
                'exit_index': exit_idx
            })
        
        return pd.DataFrame(results)


# Singleton instance
_triple_barrier_instance: Optional[TripleBarrierLabeling] = None


def get_triple_barrier_labeling(
    tp_pct: float = 0.03,
    sl_pct: float = 0.015,
    max_hold_periods: int = 24,
    use_atr: bool = True
) -> TripleBarrierLabeling:
    """Получить экземпляр triple barrier labeling"""
    global _triple_barrier_instance
    if _triple_barrier_instance is None:
        _triple_barrier_instance = TripleBarrierLabeling(
            tp_pct=tp_pct,
            sl_pct=sl_pct,
            max_hold_periods=max_hold_periods,
            use_atr=use_atr
        )
    return _triple_barrier_instance

