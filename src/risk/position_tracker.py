#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Система отслеживания позиций для торгового бота.

Предоставляет полное отслеживание позиций в реальном времени:
- Отслеживание открытых позиций
- Расчет PnL и просадки
- Мониторинг времени удержания
- Автоматическое обновление статусов
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
class Position:
    """Позиция в портфеле"""
    symbol: str
    side: str  # 'long' или 'short'
    quantity: float
    entry_price: float
    current_price: float
    stop_loss: float
    take_profit: float
    leverage: float
    margin_used: float
    unrealized_pnl: float
    realized_pnl: float
    status: str  # 'open', 'closed', 'partial'
    entry_time: datetime
    last_update: datetime = field(default_factory=get_utc_now)
    dca_count: int = 0
    max_drawdown: float = 0.0
    max_profit: float = 0.0

@dataclass
class PositionStats:
    """Статистика позиции"""
    total_pnl: float
    win_rate: float
    avg_hold_time: float
    max_drawdown: float
    sharpe_ratio: float
    total_trades: int
    winning_trades: int
    losing_trades: int

class PositionTracker:
    """Главный класс отслеживания позиций"""
    
    def __init__(self):
        self.positions = {}  # symbol_side -> Position
        self.closed_positions = []
        self.position_stats = {}
        
        # Статистика по символам
        self.symbol_stats = defaultdict(lambda: {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0.0,
            'avg_hold_time': 0.0,
            'max_drawdown': 0.0,
            'max_profit': 0.0
        })
        
        # Общая статистика
        self.overall_stats = {
            'total_positions': 0,
            'open_positions': 0,
            'closed_positions': 0,
            'total_pnl': 0.0,
            'win_rate': 0.0,
            'avg_hold_time': 0.0,
            'max_drawdown': 0.0,
            'sharpe_ratio': 0.0
        }
        
        # История изменений цен
        self.price_history = defaultdict(list)
        
        # Настройки мониторинга
        self.monitoring_settings = {
            'update_interval': 30,  # секунд
            'max_history_length': 1000,
            'auto_close_on_sl': True,
            'auto_close_on_tp': True,
            'trailing_stop_enabled': False
        }

    def add_position(self, position_data: Dict) -> bool:
        """Добавляет новую позицию"""
        
        try:
            position = Position(
                symbol=position_data['symbol'],
                side=position_data['side'],
                quantity=position_data['quantity'],
                entry_price=position_data['entry_price'],
                current_price=position_data['current_price'],
                stop_loss=position_data['stop_loss'],
                take_profit=position_data['take_profit'],
                leverage=position_data.get('leverage', 1.0),
                margin_used=position_data.get('margin_used', 0.0),
                unrealized_pnl=0.0,
                realized_pnl=0.0,
                status='open',
                entry_time=get_utc_now()
            )
            
            # Рассчитываем начальный PnL
            position.unrealized_pnl = self._calculate_unrealized_pnl(position)
            
            # Сохраняем позицию
            key = f"{position.symbol}_{position.side}"
            self.positions[key] = position
            
            # Обновляем статистику
            self.overall_stats['total_positions'] += 1
            self.overall_stats['open_positions'] += 1
            
            logger.info(f"Position added: {position.symbol} {position.side} {position.quantity:.4f}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding position: {e}")
            return False

    def update_position(self, symbol: str, side: str, current_price: float) -> bool:
        """Обновляет позицию с новой ценой"""
        
        key = f"{symbol}_{side}"
        if key not in self.positions:
            return False
        
        position = self.positions[key]
        position.current_price = current_price
        position.last_update = get_utc_now()
        
        # Рассчитываем новый PnL
        old_pnl = position.unrealized_pnl
        position.unrealized_pnl = self._calculate_unrealized_pnl(position)
        
        # Обновляем максимальную прибыль и просадку
        if position.unrealized_pnl > position.max_profit:
            position.max_profit = position.unrealized_pnl
        
        if position.unrealized_pnl < -position.max_drawdown:
            position.max_drawdown = abs(position.unrealized_pnl)
        
        # Сохраняем историю цен
        self.price_history[key].append({
            'timestamp': get_utc_now(),
            'price': current_price,
            'pnl': position.unrealized_pnl
        })
        
        # Ограничиваем длину истории
        if len(self.price_history[key]) > self.monitoring_settings['max_history_length']:
            self.price_history[key] = self.price_history[key][-self.monitoring_settings['max_history_length']:]
        
        # Проверяем условия закрытия
        if self.monitoring_settings['auto_close_on_sl']:
            if self._should_close_on_stop_loss(position):
                self.close_position(symbol, side, 'stop_loss')
                return True
        
        if self.monitoring_settings['auto_close_on_tp']:
            if self._should_close_on_take_profit(position):
                self.close_position(symbol, side, 'take_profit')
                return True
        
        return True

    def close_position(self, symbol: str, side: str, reason: str = 'manual') -> Optional[Position]:
        """Закрывает позицию"""
        
        key = f"{symbol}_{side}"
        if key not in self.positions:
            return None
        
        position = self.positions[key]
        position.status = 'closed'
        position.realized_pnl = position.unrealized_pnl
        
        # Перемещаем в закрытые позиции
        self.closed_positions.append(position)
        del self.positions[key]
        
        # Обновляем статистику
        self.overall_stats['open_positions'] -= 1
        self.overall_stats['closed_positions'] += 1
        self.overall_stats['total_pnl'] += position.realized_pnl
        
        # Обновляем статистику по символу
        self._update_symbol_stats(position)
        
        # Обновляем общую статистику
        self._update_overall_stats()
        
        logger.info(f"Position closed: {symbol} {side} PnL: {position.realized_pnl:.2f} Reason: {reason}")
        return position

    def partial_close(self, symbol: str, side: str, percentage: float) -> Optional[Position]:
        """Частично закрывает позицию"""
        
        key = f"{symbol}_{side}"
        if key not in self.positions:
            return None
        
        position = self.positions[key]
        
        # Рассчитываем количество для закрытия
        close_quantity = position.quantity * (percentage / 100)
        remaining_quantity = position.quantity - close_quantity
        
        # Рассчитываем PnL для закрываемой части
        partial_pnl = position.unrealized_pnl * (percentage / 100)
        
        # Обновляем позицию
        position.quantity = remaining_quantity
        position.margin_used *= (remaining_quantity / (remaining_quantity + close_quantity))
        position.realized_pnl += partial_pnl
        position.unrealized_pnl -= partial_pnl
        
        # Если позиция полностью закрыта
        if remaining_quantity <= 0.001:  # Минимальный остаток
            return self.close_position(symbol, side, 'partial_close')
        
        logger.info(f"Position partially closed: {symbol} {side} {percentage}% PnL: {partial_pnl:.2f}")
        return position

    def _calculate_unrealized_pnl(self, position: Position) -> float:
        """Рассчитывает нереализованный PnL"""
        
        if position.side == 'long':
            pnl = (position.current_price - position.entry_price) * position.quantity
        else:  # short
            pnl = (position.entry_price - position.current_price) * position.quantity
        
        # Применяем плечо
        if position.leverage > 1:
            pnl *= position.leverage
        
        return pnl

    def _should_close_on_stop_loss(self, position: Position) -> bool:
        """Проверяет, нужно ли закрыть позицию по стоп-лоссу"""
        
        if position.side == 'long':
            return position.current_price <= position.stop_loss
        else:  # short
            return position.current_price >= position.stop_loss

    def _should_close_on_take_profit(self, position: Position) -> bool:
        """Проверяет, нужно ли закрыть позицию по тейк-профиту"""
        
        if position.side == 'long':
            return position.current_price >= position.take_profit
        else:  # short
            return position.current_price <= position.take_profit

    def _update_symbol_stats(self, position: Position):
        """Обновляет статистику по символу"""
        
        symbol = position.symbol
        stats = self.symbol_stats[symbol]
        
        stats['total_trades'] += 1
        stats['total_pnl'] += position.realized_pnl
        
        if position.realized_pnl > 0:
            stats['winning_trades'] += 1
        else:
            stats['losing_trades'] += 1
        
        # Время удержания
        hold_time = (position.last_update - position.entry_time).total_seconds() / 3600  # часы
        stats['avg_hold_time'] = (stats['avg_hold_time'] * (stats['total_trades'] - 1) + hold_time) / stats['total_trades']
        
        # Максимальная просадка и прибыль
        if position.max_drawdown > stats['max_drawdown']:
            stats['max_drawdown'] = position.max_drawdown
        
        if position.max_profit > stats['max_profit']:
            stats['max_profit'] = position.max_profit

    def _update_overall_stats(self):
        """Обновляет общую статистику"""
        
        if self.overall_stats['closed_positions'] == 0:
            return
        
        # Win rate
        winning_positions = sum(1 for p in self.closed_positions if p.realized_pnl > 0)
        self.overall_stats['win_rate'] = (winning_positions / self.overall_stats['closed_positions']) * 100
        
        # Среднее время удержания
        total_hold_time = sum((p.last_update - p.entry_time).total_seconds() / 3600 for p in self.closed_positions)
        self.overall_stats['avg_hold_time'] = total_hold_time / self.overall_stats['closed_positions']
        
        # Максимальная просадка
        max_drawdown = max((p.max_drawdown for p in self.closed_positions), default=0.0)
        self.overall_stats['max_drawdown'] = max_drawdown
        
        # Sharpe ratio (упрощенный)
        if self.overall_stats['closed_positions'] > 1:
            avg_return = self.overall_stats['total_pnl'] / self.overall_stats['closed_positions']
            volatility = max_drawdown / 100  # Упрощение
            if volatility > 0:
                self.overall_stats['sharpe_ratio'] = avg_return / volatility

    def get_position_report(self, symbol: str = None) -> Dict:
        """Возвращает отчет о позициях"""
        
        if symbol:
            # Отчет по конкретному символу
            if symbol in self.symbol_stats:
                return {
                    'symbol': symbol,
                    'stats': self.symbol_stats[symbol],
                    'open_positions': [p.__dict__ for p in self.positions.values() if p.symbol == symbol],
                    'recent_closed': [p.__dict__ for p in self.closed_positions[-10:] if p.symbol == symbol]
                }
            else:
                return {'error': f'No data for symbol {symbol}'}
        else:
            # Общий отчет
            return {
                'overall_stats': self.overall_stats,
                'open_positions': [p.__dict__ for p in self.positions.values()],
                'symbol_stats': dict(self.symbol_stats),
                'recent_closed': [p.__dict__ for p in self.closed_positions[-20:]],
                'timestamp': get_utc_now().isoformat()
            }

    def get_performance_analysis(self) -> Dict:
        """Возвращает анализ производительности"""
        
        if not self.closed_positions:
            return {'error': 'No closed positions for analysis'}
        
        # Анализ по символам
        symbol_analysis = {}
        for symbol, stats in self.symbol_stats.items():
            if stats['total_trades'] > 0:
                win_rate = (stats['winning_trades'] / stats['total_trades']) * 100
                symbol_analysis[symbol] = {
                    'total_trades': stats['total_trades'],
                    'win_rate': win_rate,
                    'total_pnl': stats['total_pnl'],
                    'avg_pnl_per_trade': stats['total_pnl'] / stats['total_trades'],
                    'avg_hold_time': stats['avg_hold_time'],
                    'max_drawdown': stats['max_drawdown'],
                    'max_profit': stats['max_profit']
                }
        
        # Анализ по времени
        time_analysis = self._analyze_by_time()
        
        # Анализ по размеру позиций
        size_analysis = self._analyze_by_size()
        
        return {
            'symbol_analysis': symbol_analysis,
            'time_analysis': time_analysis,
            'size_analysis': size_analysis,
            'overall_performance': self.overall_stats,
            'recommendations': self._generate_recommendations()
        }

    def _analyze_by_time(self) -> Dict:
        """Анализ производительности по времени"""
        
        # Группируем по часам дня
        hourly_stats = defaultdict(lambda: {'trades': 0, 'pnl': 0.0, 'wins': 0})
        
        for position in self.closed_positions:
            hour = position.entry_time.hour
            hourly_stats[hour]['trades'] += 1
            hourly_stats[hour]['pnl'] += position.realized_pnl
            if position.realized_pnl > 0:
                hourly_stats[hour]['wins'] += 1
        
        # Рассчитываем метрики
        time_analysis = {}
        for hour, stats in hourly_stats.items():
            if stats['trades'] > 0:
                time_analysis[f"{hour:02d}:00"] = {
                    'trades': stats['trades'],
                    'win_rate': (stats['wins'] / stats['trades']) * 100,
                    'total_pnl': stats['pnl'],
                    'avg_pnl': stats['pnl'] / stats['trades']
                }
        
        return time_analysis

    def _analyze_by_size(self) -> Dict:
        """Анализ производительности по размеру позиций"""
        
        # Группируем по размеру позиции
        size_groups = {
            'small': {'min': 0, 'max': 100, 'trades': 0, 'pnl': 0.0, 'wins': 0},
            'medium': {'min': 100, 'max': 1000, 'trades': 0, 'pnl': 0.0, 'wins': 0},
            'large': {'min': 1000, 'max': float('inf'), 'trades': 0, 'pnl': 0.0, 'wins': 0}
        }
        
        for position in self.closed_positions:
            position_value = position.quantity * position.entry_price
            
            for group_name, group in size_groups.items():
                if group['min'] <= position_value < group['max']:
                    group['trades'] += 1
                    group['pnl'] += position.realized_pnl
                    if position.realized_pnl > 0:
                        group['wins'] += 1
                    break
        
        # Рассчитываем метрики
        size_analysis = {}
        for group_name, group in size_groups.items():
            if group['trades'] > 0:
                size_analysis[group_name] = {
                    'trades': group['trades'],
                    'win_rate': (group['wins'] / group['trades']) * 100,
                    'total_pnl': group['pnl'],
                    'avg_pnl': group['pnl'] / group['trades']
                }
        
        return size_analysis

    def _generate_recommendations(self) -> List[str]:
        """Генерирует рекомендации на основе анализа"""
        
        recommendations = []
        
        # Анализ win rate
        if self.overall_stats['win_rate'] < 50:
            recommendations.append("Consider reducing position sizes or improving entry criteria")
        
        # Анализ времени удержания
        if self.overall_stats['avg_hold_time'] > 24:
            recommendations.append("Consider implementing tighter stop losses or take profits")
        
        # Анализ максимальной просадки
        if self.overall_stats['max_drawdown'] > 10:
            recommendations.append("Consider implementing better risk management")
        
        # Анализ по символам
        for symbol, stats in self.symbol_stats.items():
            if stats['total_trades'] > 5 and (stats['winning_trades'] / stats['total_trades']) < 0.4:
                recommendations.append(f"Consider avoiding {symbol} or improving strategy")
        
        return recommendations

    def save_state(self, filepath: str = 'position_tracker_state.json'):
        """Сохраняет состояние системы"""
        
        state = {
            'positions': {k: v.__dict__ for k, v in self.positions.items()},
            'closed_positions': [p.__dict__ for p in self.closed_positions],
            'symbol_stats': dict(self.symbol_stats),
            'overall_stats': self.overall_stats,
            'price_history': {k: v for k, v in self.price_history.items()}
        }
        
        with open(filepath, 'w') as f:
            json.dump(state, f, indent=2, default=str)
        
        logger.info(f"Position tracker state saved to {filepath}")

    def load_state(self, filepath: str = 'position_tracker_state.json'):
        """Загружает состояние системы"""
        
        if not os.path.exists(filepath):
            logger.warning(f"State file {filepath} not found")
            return
        
        with open(filepath, 'r') as f:
            state = json.load(f)
        
        # Восстанавливаем позиции
        if state.get('positions'):
            self.positions = {}
            for k, v in state['positions'].items():
                v['entry_time'] = datetime.fromisoformat(v['entry_time'])
                v['last_update'] = datetime.fromisoformat(v['last_update'])
                self.positions[k] = Position(**v)
        
        # Восстанавливаем закрытые позиции
        if state.get('closed_positions'):
            self.closed_positions = []
            for p in state['closed_positions']:
                p['entry_time'] = datetime.fromisoformat(p['entry_time'])
                p['last_update'] = datetime.fromisoformat(p['last_update'])
                self.closed_positions.append(Position(**p))
        
        # Восстанавливаем статистику
        if state.get('symbol_stats'):
            self.symbol_stats = defaultdict(lambda: {
                'total_trades': 0, 'winning_trades': 0, 'losing_trades': 0,
                'total_pnl': 0.0, 'avg_hold_time': 0.0, 'max_drawdown': 0.0, 'max_profit': 0.0
            }, state['symbol_stats'])
        
        if state.get('overall_stats'):
            self.overall_stats = state['overall_stats']
        
        logger.info(f"Position tracker state loaded from {filepath}")

# Глобальный экземпляр
position_tracker = PositionTracker()
