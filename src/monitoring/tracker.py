#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Система отслеживания производительности для торгового бота.

Предоставляет комплексный анализ производительности:
- Расчет ключевых метрик (Sharpe, Sortino, Calmar)
- Анализ эффективности стратегий
- Сравнение с бенчмарками
- Детальная статистика по символам
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
class PerformanceMetrics:
    """Метрики производительности"""
    total_return: float
    annualized_return: float
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    consecutive_wins: int
    consecutive_losses: int
    recovery_factor: float
    var_95: float
    cvar_95: float

@dataclass
class StrategyPerformance:
    """Производительность стратегии"""
    strategy_name: str
    metrics: PerformanceMetrics
    symbol_performance: Dict[str, PerformanceMetrics]
    time_performance: Dict[str, PerformanceMetrics]
    benchmark_comparison: Dict[str, float]

@dataclass
class Trade:
    """Сделка"""
    trade_id: str
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    pnl_pct: float
    entry_time: datetime
    exit_time: datetime
    hold_time: float  # в часах
    commission: float
    strategy: str
    user_id: str

class PerformanceTracker:
    """Главный класс отслеживания производительности"""
    
    def __init__(self):
        self.trades = []
        self.daily_returns = []
        self.weekly_returns = []
        self.monthly_returns = []
        
        # Статистика по символам
        self.symbol_stats = defaultdict(lambda: {
            'trades': [],
            'total_pnl': 0.0,
            'total_pnl_pct': 0.0,
            'win_rate': 0.0,
            'avg_hold_time': 0.0,
            'max_drawdown': 0.0,
            'max_profit': 0.0
        })
        
        # Статистика по стратегиям
        self.strategy_stats = defaultdict(lambda: {
            'trades': [],
            'total_pnl': 0.0,
            'total_pnl_pct': 0.0,
            'win_rate': 0.0,
            'avg_hold_time': 0.0,
            'max_drawdown': 0.0,
            'max_profit': 0.0
        })
        
        # Статистика по времени
        self.time_stats = {
            'hourly': defaultdict(list),
            'daily': defaultdict(list),
            'weekly': defaultdict(list),
            'monthly': defaultdict(list)
        }
        
        # Бенчмарки
        self.benchmarks = {
            'BTC': {'returns': [], 'volatility': 0.0},
            'ETH': {'returns': [], 'volatility': 0.0},
            'SPY': {'returns': [], 'volatility': 0.0}
        }
        
        # Настройки
        self.settings = {
            'risk_free_rate': 0.02,  # 2% годовых
            'benchmark_symbols': ['BTC', 'ETH', 'SPY'],
            'min_trades_for_analysis': 10,
            'lookback_periods': {
                'daily': 30,
                'weekly': 12,
                'monthly': 6
            }
        }

    def add_trade(self, trade_data: Dict):
        """Добавляет сделку"""
        
        trade = Trade(
            trade_id=trade_data['trade_id'],
            symbol=trade_data['symbol'],
            side=trade_data['side'],
            entry_price=trade_data['entry_price'],
            exit_price=trade_data['exit_price'],
            quantity=trade_data['quantity'],
            pnl=trade_data['pnl'],
            pnl_pct=trade_data['pnl_pct'],
            entry_time=trade_data['entry_time'],
            exit_time=trade_data['exit_time'],
            hold_time=trade_data['hold_time'],
            commission=trade_data.get('commission', 0.0),
            strategy=trade_data.get('strategy', 'default'),
            user_id=trade_data.get('user_id', 'unknown')
        )
        
        self.trades.append(trade)
        
        # Обновляем статистику по символу
        self._update_symbol_stats(trade)
        
        # Обновляем статистику по стратегии
        self._update_strategy_stats(trade)
        
        # Обновляем статистику по времени
        self._update_time_stats(trade)
        
        # Обновляем дневные доходности
        self._update_daily_returns(trade)
        
        logger.info(f"Trade added: {trade.symbol} {trade.side} PnL: {trade.pnl:.2f}")

    def _update_symbol_stats(self, trade: Trade):
        """Обновляет статистику по символу"""
        
        symbol = trade.symbol
        stats = self.symbol_stats[symbol]
        
        stats['trades'].append(trade)
        stats['total_pnl'] += trade.pnl
        stats['total_pnl_pct'] += trade.pnl_pct
        
        # Win rate
        winning_trades = sum(1 for t in stats['trades'] if t.pnl > 0)
        stats['win_rate'] = (winning_trades / len(stats['trades'])) * 100
        
        # Среднее время удержания
        total_hold_time = sum(t.hold_time for t in stats['trades'])
        stats['avg_hold_time'] = total_hold_time / len(stats['trades'])
        
        # Максимальная просадка и прибыль
        cumulative_pnl = 0.0
        max_pnl = 0.0
        max_drawdown = 0.0
        
        for t in stats['trades']:
            cumulative_pnl += t.pnl
            if cumulative_pnl > max_pnl:
                max_pnl = cumulative_pnl
            else:
                drawdown = max_pnl - cumulative_pnl
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
        
        stats['max_drawdown'] = max_drawdown
        stats['max_profit'] = max_pnl

    def _update_strategy_stats(self, trade: Trade):
        """Обновляет статистику по стратегии"""
        
        strategy = trade.strategy
        stats = self.strategy_stats[strategy]
        
        stats['trades'].append(trade)
        stats['total_pnl'] += trade.pnl
        stats['total_pnl_pct'] += trade.pnl_pct
        
        # Win rate
        winning_trades = sum(1 for t in stats['trades'] if t.pnl > 0)
        stats['win_rate'] = (winning_trades / len(stats['trades'])) * 100
        
        # Среднее время удержания
        total_hold_time = sum(t.hold_time for t in stats['trades'])
        stats['avg_hold_time'] = total_hold_time / len(stats['trades'])
        
        # Максимальная просадка и прибыль
        cumulative_pnl = 0.0
        max_pnl = 0.0
        max_drawdown = 0.0
        
        for t in stats['trades']:
            cumulative_pnl += t.pnl
            if cumulative_pnl > max_pnl:
                max_pnl = cumulative_pnl
            else:
                drawdown = max_pnl - cumulative_pnl
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
        
        stats['max_drawdown'] = max_drawdown
        stats['max_profit'] = max_pnl

    def _update_time_stats(self, trade: Trade):
        """Обновляет статистику по времени"""
        
        entry_time = trade.entry_time
        
        # По часам
        hour = entry_time.hour
        self.time_stats['hourly'][hour].append(trade)
        
        # По дням недели
        weekday = entry_time.weekday()
        self.time_stats['daily'][weekday].append(trade)
        
        # По неделям
        week = entry_time.isocalendar()[1]
        self.time_stats['weekly'][week].append(trade)
        
        # По месяцам
        month = entry_time.month
        self.time_stats['monthly'][month].append(trade)

    def _update_daily_returns(self, trade: Trade):
        """Обновляет дневные доходности"""
        
        # Группируем сделки по дням
        daily_pnl = defaultdict(float)
        for t in self.trades:
            date = t.exit_time.date()
            daily_pnl[date] += t.pnl
        
        # Рассчитываем доходности
        dates = sorted(daily_pnl.keys())
        if len(dates) < 2:
            return
        
        returns = []
        for i in range(1, len(dates)):
            prev_pnl = daily_pnl[dates[i-1]]
            curr_pnl = daily_pnl[dates[i]]
            if prev_pnl != 0:
                returns.append((curr_pnl - prev_pnl) / abs(prev_pnl))
        
        self.daily_returns = returns

    def calculate_performance_metrics(self, trades: List[Trade] = None) -> PerformanceMetrics:
        """Рассчитывает метрики производительности"""
        
        if trades is None:
            trades = self.trades
        
        if not trades:
            return PerformanceMetrics(
                total_return=0.0, annualized_return=0.0, volatility=0.0,
                sharpe_ratio=0.0, sortino_ratio=0.0, calmar_ratio=0.0,
                max_drawdown=0.0, win_rate=0.0, profit_factor=0.0,
                avg_win=0.0, avg_loss=0.0, largest_win=0.0, largest_loss=0.0,
                total_trades=0, winning_trades=0, losing_trades=0,
                consecutive_wins=0, consecutive_losses=0,
                recovery_factor=0.0, var_95=0.0, cvar_95=0.0
            )
        
        # Базовые метрики
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t.pnl > 0)
        losing_trades = total_trades - winning_trades
        
        total_pnl = sum(t.pnl for t in trades)
        total_pnl_pct = sum(t.pnl_pct for t in trades)
        
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0.0
        
        # Средние выигрыши и проигрыши
        wins = [t.pnl for t in trades if t.pnl > 0]
        losses = [t.pnl for t in trades if t.pnl < 0]
        
        avg_win = np.mean(wins) if wins else 0.0
        avg_loss = np.mean(losses) if losses else 0.0
        
        largest_win = max(wins) if wins else 0.0
        largest_loss = min(losses) if losses else 0.0
        
        # Profit factor
        total_wins = sum(wins) if wins else 0.0
        total_losses = abs(sum(losses)) if losses else 0.0
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        # Максимальная просадка
        cumulative_pnl = 0.0
        max_pnl = 0.0
        max_drawdown = 0.0
        
        for trade in trades:
            cumulative_pnl += trade.pnl
            if cumulative_pnl > max_pnl:
                max_pnl = cumulative_pnl
            else:
                drawdown = max_pnl - cumulative_pnl
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
        
        # Последовательные выигрыши и проигрыши
        consecutive_wins = 0
        consecutive_losses = 0
        max_consecutive_wins = 0
        max_consecutive_losses = 0
        
        current_wins = 0
        current_losses = 0
        
        for trade in trades:
            if trade.pnl > 0:
                current_wins += 1
                current_losses = 0
                max_consecutive_wins = max(max_consecutive_wins, current_wins)
            else:
                current_losses += 1
                current_wins = 0
                max_consecutive_losses = max(max_consecutive_losses, current_losses)
        
        # Доходности для расчета метрик
        returns = [t.pnl_pct / 100 for t in trades]  # Конвертируем в десятичные
        
        # Волатильность
        volatility = np.std(returns) if len(returns) > 1 else 0.0
        
        # Sharpe ratio
        avg_return = np.mean(returns) if returns else 0.0
        sharpe_ratio = (avg_return - self.settings['risk_free_rate'] / 365) / volatility if volatility > 0 else 0.0
        
        # Sortino ratio (используем только отрицательные доходности)
        negative_returns = [r for r in returns if r < 0]
        downside_volatility = np.std(negative_returns) if negative_returns else 0.0
        sortino_ratio = (avg_return - self.settings['risk_free_rate'] / 365) / downside_volatility if downside_volatility > 0 else 0.0
        
        # Calmar ratio
        annualized_return = avg_return * 365  # Упрощение
        calmar_ratio = annualized_return / max_drawdown if max_drawdown > 0 else 0.0
        
        # Recovery factor
        recovery_factor = total_pnl / max_drawdown if max_drawdown > 0 else 0.0
        
        # Value at Risk и Conditional Value at Risk
        var_95 = np.percentile(returns, 5) if returns else 0.0
        cvar_95 = np.mean([r for r in returns if r <= var_95]) if returns else 0.0
        
        return PerformanceMetrics(
            total_return=total_pnl_pct,
            annualized_return=annualized_return * 100,
            volatility=volatility * 100,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            consecutive_wins=max_consecutive_wins,
            consecutive_losses=max_consecutive_losses,
            recovery_factor=recovery_factor,
            var_95=var_95 * 100,
            cvar_95=cvar_95 * 100
        )

    def get_strategy_performance(self, strategy_name: str) -> Optional[StrategyPerformance]:
        """Возвращает производительность стратегии"""
        
        if strategy_name not in self.strategy_stats:
            return None
        
        strategy_trades = self.strategy_stats[strategy_name]['trades']
        if not strategy_trades:
            return None
        
        # Метрики стратегии
        strategy_metrics = self.calculate_performance_metrics(strategy_trades)
        
        # Метрики по символам
        symbol_performance = {}
        symbol_trades = defaultdict(list)
        for trade in strategy_trades:
            symbol_trades[trade.symbol].append(trade)
        
        for symbol, trades in symbol_trades.items():
            symbol_performance[symbol] = self.calculate_performance_metrics(trades)
        
        # Метрики по времени
        time_performance = {}
        for period, trades_by_time in self.time_stats.items():
            period_trades = []
            for time_slot, trades in trades_by_time.items():
                strategy_trades_in_slot = [t for t in trades if t.strategy == strategy_name]
                period_trades.extend(strategy_trades_in_slot)
            
            if period_trades:
                time_performance[period] = self.calculate_performance_metrics(period_trades)
        
        # Сравнение с бенчмарками
        benchmark_comparison = self._compare_with_benchmarks(strategy_metrics)
        
        return StrategyPerformance(
            strategy_name=strategy_name,
            metrics=strategy_metrics,
            symbol_performance=symbol_performance,
            time_performance=time_performance,
            benchmark_comparison=benchmark_comparison
        )

    def _compare_with_benchmarks(self, metrics: PerformanceMetrics) -> Dict[str, float]:
        """Сравнивает с бенчмарками"""
        
        comparison = {}
        
        for benchmark, data in self.benchmarks.items():
            if data['returns']:
                benchmark_return = np.mean(data['returns']) * 100
                benchmark_volatility = data['volatility'] * 100
                
                # Отношение доходности
                return_ratio = metrics.annualized_return / benchmark_return if benchmark_return != 0 else 0.0
                
                # Отношение волатильности
                volatility_ratio = metrics.volatility / benchmark_volatility if benchmark_volatility != 0 else 0.0
                
                # Отношение Sharpe ratio
                benchmark_sharpe = (benchmark_return - self.settings['risk_free_rate']) / benchmark_volatility if benchmark_volatility != 0 else 0.0
                sharpe_ratio = metrics.sharpe_ratio / benchmark_sharpe if benchmark_sharpe != 0 else 0.0
                
                comparison[benchmark] = {
                    'return_ratio': return_ratio,
                    'volatility_ratio': volatility_ratio,
                    'sharpe_ratio': sharpe_ratio
                }
        
        return comparison

    def get_performance_report(self) -> Dict:
        """Возвращает отчет о производительности"""
        
        # Общие метрики
        overall_metrics = self.calculate_performance_metrics()
        
        # Метрики по символам
        symbol_metrics = {}
        for symbol, stats in self.symbol_stats.items():
            if stats['trades']:
                symbol_metrics[symbol] = self.calculate_performance_metrics(stats['trades'])
        
        # Метрики по стратегиям
        strategy_metrics = {}
        for strategy, stats in self.strategy_stats.items():
            if stats['trades']:
                strategy_metrics[strategy] = self.calculate_performance_metrics(stats['trades'])
        
        # Анализ по времени
        time_analysis = self._analyze_time_performance()
        
        # Рекомендации
        recommendations = self._generate_recommendations()
        
        return {
            'overall_metrics': overall_metrics.__dict__,
            'symbol_metrics': {k: v.__dict__ for k, v in symbol_metrics.items()},
            'strategy_metrics': {k: v.__dict__ for k, v in strategy_metrics.items()},
            'time_analysis': time_analysis,
            'recommendations': recommendations,
            'total_trades': len(self.trades),
            'date_range': {
                'start': min(t.entry_time for t in self.trades).isoformat() if self.trades else None,
                'end': max(t.exit_time for t in self.trades).isoformat() if self.trades else None
            },
            'timestamp': get_utc_now().isoformat()
        }

    def _analyze_time_performance(self) -> Dict:
        """Анализирует производительность по времени"""
        
        analysis = {}
        
        for period, trades_by_time in self.time_stats.items():
            period_analysis = {}
            
            for time_slot, trades in trades_by_time.items():
                if trades:
                    metrics = self.calculate_performance_metrics(trades)
                    period_analysis[str(time_slot)] = {
                        'total_trades': len(trades),
                        'win_rate': metrics.win_rate,
                        'total_return': metrics.total_return,
                        'sharpe_ratio': metrics.sharpe_ratio,
                        'max_drawdown': metrics.max_drawdown
                    }
            
            analysis[period] = period_analysis
        
        return analysis

    def _generate_recommendations(self) -> List[str]:
        """Генерирует рекомендации на основе анализа"""
        
        recommendations = []
        
        overall_metrics = self.calculate_performance_metrics()
        
        # Анализ win rate
        if overall_metrics.win_rate < 50:
            recommendations.append("Consider improving entry criteria or risk management")
        
        # Анализ profit factor
        if overall_metrics.profit_factor < 1.0:
            recommendations.append("Strategy is losing money - consider stopping or major revision")
        elif overall_metrics.profit_factor < 1.5:
            recommendations.append("Low profit factor - consider optimizing exit strategy")
        
        # Анализ максимальной просадки
        if overall_metrics.max_drawdown > 20:
            recommendations.append("High maximum drawdown - implement better risk management")
        
        # Анализ Sharpe ratio
        if overall_metrics.sharpe_ratio < 1.0:
            recommendations.append("Low Sharpe ratio - consider reducing volatility or increasing returns")
        
        # Анализ по символам
        for symbol, stats in self.symbol_stats.items():
            if len(stats['trades']) >= 5:
                symbol_metrics = self.calculate_performance_metrics(stats['trades'])
                if symbol_metrics.win_rate < 40:
                    recommendations.append(f"Consider avoiding {symbol} or improving strategy")
        
        return recommendations

    def save_state(self, filepath: str = 'performance_tracker_state.json'):
        """Сохраняет состояние системы"""
        
        state = {
            'trades': [
                {
                    'trade_id': t.trade_id,
                    'symbol': t.symbol,
                    'side': t.side,
                    'entry_price': t.entry_price,
                    'exit_price': t.exit_price,
                    'quantity': t.quantity,
                    'pnl': t.pnl,
                    'pnl_pct': t.pnl_pct,
                    'entry_time': t.entry_time.isoformat(),
                    'exit_time': t.exit_time.isoformat(),
                    'hold_time': t.hold_time,
                    'commission': t.commission,
                    'strategy': t.strategy,
                    'user_id': t.user_id
                } for t in self.trades
            ],
            'daily_returns': self.daily_returns,
            'symbol_stats': {k: {
                'trades': [t.trade_id for t in v['trades']],
                'total_pnl': v['total_pnl'],
                'total_pnl_pct': v['total_pnl_pct'],
                'win_rate': v['win_rate'],
                'avg_hold_time': v['avg_hold_time'],
                'max_drawdown': v['max_drawdown'],
                'max_profit': v['max_profit']
            } for k, v in self.symbol_stats.items()},
            'strategy_stats': {k: {
                'trades': [t.trade_id for t in v['trades']],
                'total_pnl': v['total_pnl'],
                'total_pnl_pct': v['total_pnl_pct'],
                'win_rate': v['win_rate'],
                'avg_hold_time': v['avg_hold_time'],
                'max_drawdown': v['max_drawdown'],
                'max_profit': v['max_profit']
            } for k, v in self.strategy_stats.items()},
            'benchmarks': self.benchmarks,
            'settings': self.settings
        }
        
        with open(filepath, 'w') as f:
            json.dump(state, f, indent=2)
        
        logger.info(f"Performance tracker state saved to {filepath}")

    def load_state(self, filepath: str = 'performance_tracker_state.json'):
        """Загружает состояние системы"""
        
        if not os.path.exists(filepath):
            logger.warning(f"State file {filepath} not found")
            return
        
        with open(filepath, 'r') as f:
            state = json.load(f)
        
        # Восстанавливаем сделки
        if state.get('trades'):
            self.trades = []
            for trade_data in state['trades']:
                trade_data['entry_time'] = datetime.fromisoformat(trade_data['entry_time'])
                trade_data['exit_time'] = datetime.fromisoformat(trade_data['exit_time'])
                self.trades.append(Trade(**trade_data))
        
        # Восстанавливаем статистику
        if state.get('daily_returns'):
            self.daily_returns = state['daily_returns']
        
        if state.get('benchmarks'):
            self.benchmarks = state['benchmarks']
        
        if state.get('settings'):
            self.settings = state['settings']
        
        logger.info(f"Performance tracker state loaded from {filepath}")

# Глобальный экземпляр
performance_tracker = PerformanceTracker()
