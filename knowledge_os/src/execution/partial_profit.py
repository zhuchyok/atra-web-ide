#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Partial Profit Manager - управление частичной фиксацией прибыли
Закрывает часть позиции при TP1, остальное к TP2
"""

import logging
import time
from typing import Dict, Any, Optional
import pandas as pd

logger = logging.getLogger(__name__)

# Импорт Exhaustion фильтра
try:
    from src.filters.exhaustion_filter import check_exhaustion_early_exit, get_exhaustion_recommendation
    EXHAUSTION_AVAILABLE = True
except ImportError:
    EXHAUSTION_AVAILABLE = False
    logger.warning("Exhaustion фильтр недоступен")


class PartialProfitManager:
    """
    Менеджер частичной фиксации прибыли
    
    Функционал:
    - Настройка уровней TP1/TP2
    - Автоматическое закрытие части при TP1
    - Перенос SL в безубыток после TP1
    - Адаптация уровней по режиму рынка
    """
    
    def __init__(self):
        self.profit_targets = {}
        
        # Настройки
        self.settings = {
            'min_position_size_usdt': 50,    # Минимум для partial TP
            'tp1_split_pct': 50,             # 50% на TP1
            'tp2_split_pct': 50,             # 50% на TP2
            'move_sl_to_be_after_tp1': True, # SL в безубыток после TP1
            'breakeven_offset_pct': 0.3      # Безубыток + 0.3%
        }
    
    def setup_partial_take_profit(
        self,
        symbol: str,
        entry_price: float,
        position_size_usdt: float,
        tp1_price: float,
        tp2_price: float,
        side: str = "LONG",
        regime: str = "NEUTRAL"
    ) -> bool:
        """
        Настраивает частичный тейк-профит для позиции
        
        Returns:
            bool: True если настроено успешно
        """
        try:
            # Проверка минимального размера
            if position_size_usdt < self.settings['min_position_size_usdt']:
                logger.debug("⚠️ [PARTIAL TP] %s: позиция слишком мала (%.2f USDT < %.2f)", 
                           symbol, position_size_usdt, self.settings['min_position_size_usdt'])
                return False
            
            # Расчет процентов TP
            if side == "LONG":
                tp1_pct = ((tp1_price - entry_price) / entry_price) * 100
                tp2_pct = ((tp2_price - entry_price) / entry_price) * 100
            else:  # SHORT
                tp1_pct = ((entry_price - tp1_price) / entry_price) * 100
                tp2_pct = ((entry_price - tp2_price) / entry_price) * 100
            
            # Настройка целей
            self.profit_targets[symbol] = {
                'entry_price': entry_price,
                'tp1_price': tp1_price,
                'tp2_price': tp2_price,
                'tp1_pct': tp1_pct,
                'tp2_pct': tp2_pct,
                'position_size_usdt': position_size_usdt,
                'tp1_size_usdt': position_size_usdt * (self.settings['tp1_split_pct'] / 100),
                'tp2_size_usdt': position_size_usdt * (self.settings['tp2_split_pct'] / 100),
                'tp1_executed': False,
                'tp2_executed': False,
                'sl_moved_to_be': False,
                'side': side,
                'regime': regime,
                'created_at': time.time()
            }
            
            logger.info("🎯 [PARTIAL TP] %s %s: TP1=%.4f (+%.2f%%), TP2=%.4f (+%.2f%%), split=%d%%/%d%%",
                       symbol, side, tp1_price, tp1_pct, tp2_price, tp2_pct,
                       self.settings['tp1_split_pct'], self.settings['tp2_split_pct'])
            
            return True
            
        except Exception as e:
            logger.error("❌ Ошибка настройки partial TP для %s: %s", symbol, e)
            return False
    
    def check_profit_targets(
        self, 
        symbol: str, 
        current_price: float,
        df: Optional[pd.DataFrame] = None,
        current_index: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Проверяет достижение целей и возвращает команды на исполнение
        
        Args:
            symbol: Торговый символ
            current_price: Текущая цена
            df: DataFrame с OHLCV данными (опционально, для exhaustion проверки)
            current_index: Индекс текущей свечи в df (опционально)
        
        Returns:
            Dict с командами или None
        """
        try:
            if symbol not in self.profit_targets:
                return None
            
            targets = self.profit_targets[symbol]
            side = targets['side']
            
            # Рассчитываем текущую прибыль
            if side == "LONG":
                current_profit_pct = ((current_price - targets['entry_price']) / targets['entry_price']) * 100
                tp1_reached = current_price >= targets['tp1_price']
                tp2_reached = current_price >= targets['tp2_price']
            else:  # SHORT
                current_profit_pct = ((targets['entry_price'] - current_price) / targets['entry_price']) * 100
                tp1_reached = current_price <= targets['tp1_price']
                tp2_reached = current_price <= targets['tp2_price']
            
            # Проверка Exhaustion для раннего выхода (если включено и есть данные)
            if (EXHAUSTION_AVAILABLE and 
                df is not None and 
                current_index is not None and
                current_index < len(df) and
                current_profit_pct > 0):  # Только если позиция в прибыли
                
                try:
                    from config import USE_EXHAUSTION_FILTER
                    if USE_EXHAUSTION_FILTER:
                        exhaustion_rec = get_exhaustion_recommendation(
                            df, current_index, side.lower(), targets['entry_price'], current_price
                        )
                        
                        if exhaustion_rec.get('should_exit'):
                            exit_pct = exhaustion_rec.get('exit_pct', 50.0)
                            exit_type = exhaustion_rec.get('exit_type', 'partial')
                            reason = exhaustion_rec.get('reason', 'Исчерпание движения')
                            
                            logger.info(
                                "⚠️ [EXHAUSTION EXIT] %s %s: %.4f (+%.2f%%), %s выход %.1f%% - %s",
                                symbol, side, current_price, current_profit_pct, exit_type, exit_pct, reason
                            )
                            
                            # Если полный выход или позиция уже частично закрыта
                            if exit_type == 'full' or targets['tp1_executed']:
                                # Полный выход
                                self.remove_position(symbol)
                                return {
                                    'action': 'EXHAUSTION_FULL_CLOSE',
                                    'symbol': symbol,
                                    'side': side,
                                    'close_price': current_price,
                                    'close_size_usdt': targets.get('tp2_size_usdt', targets['position_size_usdt']),
                                    'close_percent': 100.0,
                                    'profit_pct': current_profit_pct,
                                    'reason': reason,
                                    'exhaustion_level': exhaustion_rec.get('exhaustion_level', 0.0)
                                }
                            else:
                                # Частичный выход (аналогично TP1)
                                partial_size = targets['position_size_usdt'] * (exit_pct / 100)
                                return {
                                    'action': 'EXHAUSTION_PARTIAL_CLOSE',
                                    'symbol': symbol,
                                    'side': side,
                                    'close_price': current_price,
                                    'close_size_usdt': partial_size,
                                    'close_percent': exit_pct,
                                    'profit_pct': current_profit_pct,
                                    'reason': reason,
                                    'exhaustion_level': exhaustion_rec.get('exhaustion_level', 0.0)
                                }
                except Exception as e:
                    logger.debug(f"Ошибка проверки exhaustion для {symbol}: {e}")
            
            # TP1 достигнут?
            if not targets['tp1_executed'] and tp1_reached:
                targets['tp1_executed'] = True
                targets['tp1_execution_time'] = time.time()
                
                logger.info("✅ [TP1 HIT] %s %s: %.4f (+%.2f%%), закрываем %.2f USDT (50%% позиции)",
                           symbol, side, current_price, current_profit_pct, targets['tp1_size_usdt'])
                
                # Команда на перенос SL в безубыток
                sl_action = None
                if self.settings['move_sl_to_be_after_tp1'] and not targets['sl_moved_to_be']:
                    targets['sl_moved_to_be'] = True
                    
                    if side == "LONG":
                        breakeven_sl = targets['entry_price'] * (1 + self.settings['breakeven_offset_pct'] / 100)
                    else:  # SHORT
                        breakeven_sl = targets['entry_price'] * (1 - self.settings['breakeven_offset_pct'] / 100)
                    
                    sl_action = {
                        'action': 'MOVE_SL_TO_BREAKEVEN',
                        'new_sl': breakeven_sl,
                        'symbol': symbol
                    }
                    
                    logger.info("🛡️ [SL→BE] %s: SL перемещен в безубыток %.4f (+%.2f%%)",
                               symbol, breakeven_sl, self.settings['breakeven_offset_pct'])
                
                return {
                    'action': 'TP1_PARTIAL_CLOSE',
                    'symbol': symbol,
                    'side': side,
                    'close_price': current_price,
                    'close_size_usdt': targets['tp1_size_usdt'],
                    'close_percent': self.settings['tp1_split_pct'],
                    'profit_pct': current_profit_pct,
                    'sl_action': sl_action
                }
            
            # TP2 достигнут?
            elif targets['tp1_executed'] and not targets['tp2_executed'] and tp2_reached:
                targets['tp2_executed'] = True
                targets['tp2_execution_time'] = time.time()
                
                logger.info("🎉 [TP2 HIT] %s %s: %.4f (+%.2f%%), закрываем %.2f USDT (остаток 50%%)",
                           symbol, side, current_price, current_profit_pct, targets['tp2_size_usdt'])
                
                # После TP2 удаляем из отслеживания
                self.remove_position(symbol)
                
                return {
                    'action': 'TP2_FULL_CLOSE',
                    'symbol': symbol,
                    'side': side,
                    'close_price': current_price,
                    'close_size_usdt': targets['tp2_size_usdt'],
                    'close_percent': self.settings['tp2_split_pct'],
                    'profit_pct': current_profit_pct
                }
            
            return None
            
        except Exception as e:
            logger.error("❌ Ошибка проверки profit targets для %s: %s", symbol, e)
            return None
    
    def remove_position(self, symbol: str):
        """Удаляет позицию из отслеживания"""
        if symbol in self.profit_targets:
            del self.profit_targets[symbol]
            logger.info("🗑️ [PARTIAL TP] %s: позиция удалена из отслеживания", symbol)
    
    def get_position_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Получает информацию о позиции"""
        return self.profit_targets.get(symbol)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Статистика по partial TP"""
        total_positions = len(self.profit_targets)
        tp1_executed = sum(1 for p in self.profit_targets.values() if p['tp1_executed'])
        tp2_executed = sum(1 for p in self.profit_targets.values() if p['tp2_executed'])
        sl_moved = sum(1 for p in self.profit_targets.values() if p['sl_moved_to_be'])
        
        return {
            'total_positions': total_positions,
            'tp1_executed_count': tp1_executed,
            'tp2_executed_count': tp2_executed,
            'sl_moved_to_be_count': sl_moved,
            'pending_tp1': total_positions - tp1_executed,
            'pending_tp2': tp1_executed - tp2_executed
        }


# Глобальный экземпляр
_partial_manager = None

def get_partial_manager() -> PartialProfitManager:
    """Получение глобального экземпляра"""
    global _partial_manager
    if _partial_manager is None:
        _partial_manager = PartialProfitManager()
        logger.info("✅ PartialProfitManager инициализирован")
    return _partial_manager

