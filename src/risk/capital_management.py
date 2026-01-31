#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Система управления капиталом для торгового бота.

Предоставляет профессиональное управление капиталом с учетом:
- Размера депозита
- Риск-профиля пользователя
- Рыночных условий
- Корреляции позиций
"""

import asyncio
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from src.shared.utils.datetime_utils import get_utc_now
from collections import defaultdict
import json
import os

logger = logging.getLogger(__name__)

@dataclass
class CapitalAllocation:
    """Распределение капитала"""
    total_capital: float
    available_capital: float
    allocated_capital: float
    reserved_capital: float
    max_risk_per_trade: float
    max_total_risk: float
    current_exposure: float
    leverage_used: float

@dataclass
class PositionSize:
    """Размер позиции"""
    symbol: str
    side: str
    quantity: float
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_amount: float
    risk_percentage: float
    leverage: float
    margin_required: float
    max_position_size: float

class CapitalManager:
    """Главный класс управления капиталом"""
    
    def __init__(self):
        self.capital_allocation = None
        self.position_sizes = {}
        self.risk_limits = {
            'max_risk_per_trade': 0.02,  # 2% на сделку
            'max_total_risk': 0.10,      # 10% общий риск
            'max_correlation_risk': 0.05, # 5% на коррелированные позиции
            'max_leverage': 20.0,       # Максимальное плечо
            'min_capital_reserve': 0.15  # 15% резерв капитала
        }
        
        # История распределения капитала
        self.allocation_history = []
        
        # Корреляционная матрица
        self.correlation_matrix = {}
        
        # Статистика производительности
        self.performance_stats = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0.0,
            'max_drawdown': 0.0,
            'sharpe_ratio': 0.0
        }

    def calculate_capital_allocation(self, 
                                   total_capital: float,
                                   current_positions: List[Dict],
                                   market_conditions: Dict) -> CapitalAllocation:
        """Рассчитывает распределение капитала"""
        
        # Базовые расчеты
        reserved_capital = total_capital * self.risk_limits['min_capital_reserve']
        allocated_capital = sum(pos.get('margin_used', 0) for pos in current_positions)
        available_capital = total_capital - reserved_capital - allocated_capital
        
        # Адаптивные лимиты риска на основе производительности
        adaptive_risk = self._calculate_adaptive_risk()
        
        # Максимальный риск на сделку
        max_risk_per_trade = min(
            self.risk_limits['max_risk_per_trade'],
            adaptive_risk
        )
        
        # Максимальный общий риск
        max_total_risk = min(
            self.risk_limits['max_total_risk'],
            adaptive_risk * 5
        )
        
        # Текущая экспозиция
        current_exposure = allocated_capital / total_capital if total_capital > 0 else 0
        
        # Используемое плечо
        leverage_used = self._calculate_current_leverage(current_positions)
        
        allocation = CapitalAllocation(
            total_capital=total_capital,
            available_capital=available_capital,
            allocated_capital=allocated_capital,
            reserved_capital=reserved_capital,
            max_risk_per_trade=max_risk_per_trade,
            max_total_risk=max_total_risk,
            current_exposure=current_exposure,
            leverage_used=leverage_used
        )
        
        self.capital_allocation = allocation
        self.allocation_history.append({
            'timestamp': get_utc_now(),
            'allocation': allocation
        })
        
        return allocation

    def calculate_position_size(self,
                               symbol: str,
                               side: str,
                               entry_price: float,
                               stop_loss: float,
                               take_profit: float,
                               user_data: Dict,
                               market_data: Dict) -> Optional[PositionSize]:
        """Рассчитывает оптимальный размер позиции"""
        
        if not self.capital_allocation:
            logger.error("Capital allocation not calculated")
            return None
        
        # Получаем данные пользователя
        deposit = user_data.get('deposit', 0)
        risk_pct = user_data.get('risk_pct', 2.0)
        leverage = user_data.get('leverage', 1.0)
        trade_mode = user_data.get('trade_mode', 'spot')
        
        # Рассчитываем риск на сделку
        risk_amount = deposit * (risk_pct / 100)
        
        # Ограничиваем риск лимитами
        max_risk_amount = self.capital_allocation.total_capital * self.capital_allocation.max_risk_per_trade
        risk_amount = min(risk_amount, max_risk_amount)
        
        # Рассчитываем размер позиции
        price_diff = abs(entry_price - stop_loss)
        if price_diff == 0:
            logger.error(f"Invalid stop loss for {symbol}")
            return None
        
        # Количество для спота
        if trade_mode == 'spot':
            quantity = risk_amount / entry_price
            leverage = 1.0
        else:
            # Количество для фьючерсов
            quantity = (risk_amount * leverage) / entry_price
        
        # Проверяем максимальный размер позиции
        max_position_value = self.capital_allocation.available_capital * 0.5  # 50% от доступного капитала
        position_value = quantity * entry_price
        
        if position_value > max_position_value:
            quantity = max_position_value / entry_price
        
        # Рассчитываем маржу
        margin_required = (quantity * entry_price) / leverage if leverage > 1 else quantity * entry_price
        
        # Проверяем достаточность капитала
        if margin_required > self.capital_allocation.available_capital:
            logger.warning(f"Insufficient capital for {symbol}")
            return None
        
        # Рассчитываем риск в процентах
        risk_percentage = (risk_amount / deposit) * 100 if deposit > 0 else 0
        
        position_size = PositionSize(
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_amount=risk_amount,
            risk_percentage=risk_percentage,
            leverage=leverage,
            margin_required=margin_required,
            max_position_size=max_position_value
        )
        
        # Сохраняем размер позиции
        self.position_sizes[f"{symbol}_{side}"] = position_size
        
        return position_size

    def _calculate_adaptive_risk(self) -> float:
        """Рассчитывает адаптивный риск на основе производительности"""
        
        if self.performance_stats['total_trades'] < 10:
            return self.risk_limits['max_risk_per_trade']
        
        # Анализируем производительность
        win_rate = self.performance_stats['winning_trades'] / self.performance_stats['total_trades']
        avg_pnl = self.performance_stats['total_pnl'] / self.performance_stats['total_trades']
        
        # Увеличиваем риск при хорошей производительности
        if win_rate > 0.6 and avg_pnl > 0:
            risk_multiplier = min(1.5, 1 + (win_rate - 0.5) * 2)
        elif win_rate < 0.4 or avg_pnl < 0:
            risk_multiplier = max(0.5, 1 - (0.5 - win_rate) * 2)
        else:
            risk_multiplier = 1.0
        
        adaptive_risk = self.risk_limits['max_risk_per_trade'] * risk_multiplier
        return max(0.005, min(0.05, adaptive_risk))  # Ограничиваем 0.5% - 5%

    def _calculate_current_leverage(self, positions: List[Dict]) -> float:
        """Рассчитывает текущее используемое плечо"""
        
        if not positions:
            return 0.0
        
        total_margin = sum(pos.get('margin_used', 0) for pos in positions)
        total_value = sum(pos.get('quantity', 0) * pos.get('entry_price', 0) for pos in positions)
        
        if total_margin == 0:
            return 0.0
        
        return total_value / total_margin

    def update_performance(self, trade_result: Dict):
        """Обновляет статистику производительности"""
        
        self.performance_stats['total_trades'] += 1
        
        if trade_result.get('pnl', 0) > 0:
            self.performance_stats['winning_trades'] += 1
        else:
            self.performance_stats['losing_trades'] += 1
        
        self.performance_stats['total_pnl'] += trade_result.get('pnl', 0)
        
        # Обновляем максимальную просадку
        if trade_result.get('pnl', 0) < 0:
            current_drawdown = abs(trade_result.get('pnl', 0))
            if current_drawdown > self.performance_stats['max_drawdown']:
                self.performance_stats['max_drawdown'] = current_drawdown
        
        # Рассчитываем Sharpe ratio
        self._calculate_sharpe_ratio()

    def _calculate_sharpe_ratio(self):
        """Рассчитывает Sharpe ratio"""
        
        if self.performance_stats['total_trades'] < 2:
            self.performance_stats['sharpe_ratio'] = 0.0
            return
        
        # Упрощенный расчет Sharpe ratio
        avg_return = self.performance_stats['total_pnl'] / self.performance_stats['total_trades']
        volatility = self.performance_stats['max_drawdown'] / 100  # Упрощение
        
        if volatility == 0:
            self.performance_stats['sharpe_ratio'] = 0.0
        else:
            self.performance_stats['sharpe_ratio'] = avg_return / volatility

    def get_capital_report(self) -> Dict:
        """Возвращает отчет о состоянии капитала"""
        
        if not self.capital_allocation:
            return {'error': 'Capital allocation not calculated'}
        
        return {
            'total_capital': self.capital_allocation.total_capital,
            'available_capital': self.capital_allocation.available_capital,
            'allocated_capital': self.capital_allocation.allocated_capital,
            'reserved_capital': self.capital_allocation.reserved_capital,
            'current_exposure': self.capital_allocation.current_exposure,
            'leverage_used': self.capital_allocation.leverage_used,
            'max_risk_per_trade': self.capital_allocation.max_risk_per_trade,
            'max_total_risk': self.capital_allocation.max_total_risk,
            'performance_stats': self.performance_stats,
            'position_count': len(self.position_sizes),
            'timestamp': get_utc_now().isoformat()
        }

    def save_state(self, filepath: str = 'capital_management_state.json'):
        """Сохраняет состояние системы"""
        
        state = {
            'capital_allocation': self.capital_allocation.__dict__ if self.capital_allocation else None,
            'position_sizes': {k: v.__dict__ for k, v in self.position_sizes.items()},
            'performance_stats': self.performance_stats,
            'allocation_history': [
                {
                    'timestamp': h['timestamp'].isoformat(),
                    'allocation': h['allocation'].__dict__
                } for h in self.allocation_history
            ]
        }
        
        with open(filepath, 'w') as f:
            json.dump(state, f, indent=2)
        
        logger.info(f"Capital management state saved to {filepath}")

    def load_state(self, filepath: str = 'capital_management_state.json'):
        """Загружает состояние системы"""
        
        if not os.path.exists(filepath):
            logger.warning(f"State file {filepath} not found")
            return
        
        with open(filepath, 'r') as f:
            state = json.load(f)
        
        # Восстанавливаем состояние
        if state.get('capital_allocation'):
            self.capital_allocation = CapitalAllocation(**state['capital_allocation'])
        
        if state.get('position_sizes'):
            self.position_sizes = {
                k: PositionSize(**v) for k, v in state['position_sizes'].items()
            }
        
        if state.get('performance_stats'):
            self.performance_stats = state['performance_stats']
        
        logger.info(f"Capital management state loaded from {filepath}")

# Глобальный экземпляр
capital_manager = CapitalManager()
