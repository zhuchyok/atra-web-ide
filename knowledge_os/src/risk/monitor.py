#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Система мониторинга рисков для торгового бота.

Предоставляет комплексный мониторинг рисков:
- Контроль максимальной просадки
- Ограничение убытков на день/неделю
- Мониторинг корреляции позиций
- Автоматическое снижение экспозиции
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
class RiskLimits:
    """Лимиты риска"""
    max_drawdown_pct: float = 10.0  # Максимальная просадка в %
    max_daily_loss_pct: float = 5.0  # Максимальный дневной убыток в %
    max_weekly_loss_pct: float = 15.0  # Максимальный недельный убыток в %
    max_position_size_pct: float = 20.0  # Максимальный размер позиции в %
    max_correlation_risk: float = 0.7  # Максимальная корреляция между позициями
    max_leverage: float = 20.0  # Максимальное плечо
    min_capital_reserve_pct: float = 15.0  # Минимальный резерв капитала в %

@dataclass
class RiskAlert:
    """Алерт о риске"""
    alert_id: str
    alert_type: str  # 'drawdown', 'daily_loss', 'correlation', 'leverage'
    severity: str  # 'low', 'medium', 'high', 'critical'
    message: str
    timestamp: datetime = field(default_factory=get_utc_now)
    resolved: bool = False
    action_taken: str = None

@dataclass
class RiskMetrics:
    """Метрики риска"""
    current_drawdown: float
    daily_pnl: float
    weekly_pnl: float
    total_exposure: float
    leverage_used: float
    correlation_risk: float
    var_95: float  # Value at Risk 95%
    sharpe_ratio: float
    max_drawdown: float
    current_balance: float
    peak_balance: float

class RiskMonitor:
    """Главный класс мониторинга рисков"""
    
    def __init__(self):
        self.risk_limits = RiskLimits()
        self.risk_alerts = []
        self.risk_metrics = None
        
        # История баланса для расчета просадки
        self.balance_history = []
        self.peak_balance = 0.0
        self.current_balance = 0.0
        
        # История PnL
        self.daily_pnl_history = defaultdict(list)
        self.weekly_pnl_history = defaultdict(list)
        
        # Корреляционная матрица
        self.correlation_matrix = {}
        
        # Позиции для мониторинга
        self.positions = {}
        
        # Настройки мониторинга
        self.monitoring_settings = {
            'update_interval': 60,  # секунд
            'alert_cooldown': 300,  # 5 минут
            'max_alerts_per_hour': 10,
            'auto_reduce_exposure': True,
            'emergency_stop_enabled': True
        }
        
        # Статистика рисков
        self.risk_stats = {
            'total_alerts': 0,
            'critical_alerts': 0,
            'auto_actions_taken': 0,
            'emergency_stops': 0,
            'exposure_reductions': 0
        }

    def update_balance(self, new_balance: float):
        """Обновляет баланс и рассчитывает просадку"""
        
        self.current_balance = new_balance
        
        # Обновляем пиковый баланс
        if new_balance > self.peak_balance:
            self.peak_balance = new_balance
        
        # Добавляем в историю
        self.balance_history.append({
            'timestamp': get_utc_now(),
            'balance': new_balance
        })
        
        # Ограничиваем длину истории
        if len(self.balance_history) > 1000:
            self.balance_history = self.balance_history[-1000:]
        
        # Рассчитываем метрики риска
        self._calculate_risk_metrics()

    def add_position(self, position_data: Dict):
        """Добавляет позицию для мониторинга"""
        
        position_id = f"{position_data['symbol']}_{position_data['side']}"
        self.positions[position_id] = position_data
        
        # Проверяем риски новой позиции
        self._check_position_risks(position_data)

    def remove_position(self, position_id: str):
        """Удаляет позицию из мониторинга"""
        
        if position_id in self.positions:
            del self.positions[position_id]

    def update_position(self, position_id: str, updates: Dict):
        """Обновляет позицию"""
        
        if position_id in self.positions:
            self.positions[position_id].update(updates)
            
            # Проверяем риски обновленной позиции
            self._check_position_risks(self.positions[position_id])

    def _calculate_risk_metrics(self):
        """Рассчитывает метрики риска"""
        
        if not self.balance_history:
            return
        
        # Текущая просадка
        current_drawdown = 0.0
        if self.peak_balance > 0:
            current_drawdown = ((self.peak_balance - self.current_balance) / self.peak_balance) * 100
        
        # Максимальная просадка
        max_drawdown = 0.0
        peak = self.balance_history[0]['balance']
        for entry in self.balance_history:
            if entry['balance'] > peak:
                peak = entry['balance']
            else:
                drawdown = ((peak - entry['balance']) / peak) * 100
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
        
        # Дневной PnL
        today = get_utc_now().date()
        daily_pnl = self._calculate_daily_pnl(today)
        
        # Недельный PnL
        week_start = today - timedelta(days=today.weekday())
        weekly_pnl = self._calculate_weekly_pnl(week_start)
        
        # Общая экспозиция
        total_exposure = sum(pos.get('margin_used', 0) for pos in self.positions.values())
        
        # Используемое плечо
        leverage_used = self._calculate_current_leverage()
        
        # Корреляционный риск
        correlation_risk = self._calculate_correlation_risk()
        
        # Value at Risk (упрощенный)
        var_95 = self._calculate_var_95()
        
        # Sharpe ratio
        sharpe_ratio = self._calculate_sharpe_ratio()
        
        self.risk_metrics = RiskMetrics(
            current_drawdown=current_drawdown,
            daily_pnl=daily_pnl,
            weekly_pnl=weekly_pnl,
            total_exposure=total_exposure,
            leverage_used=leverage_used,
            correlation_risk=correlation_risk,
            var_95=var_95,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            current_balance=self.current_balance,
            peak_balance=self.peak_balance
        )

    def _calculate_daily_pnl(self, date) -> float:
        """Рассчитывает дневной PnL"""
        
        if not self.balance_history:
            return 0.0
        
        # Находим баланс в начале дня
        start_balance = None
        for entry in self.balance_history:
            if entry['timestamp'].date() == date:
                if start_balance is None:
                    start_balance = entry['balance']
                break
        
        if start_balance is None:
            return 0.0
        
        # Текущий баланс
        current_balance = self.current_balance
        
        return current_balance - start_balance

    def _calculate_weekly_pnl(self, week_start) -> float:
        """Рассчитывает недельный PnL"""
        
        if not self.balance_history:
            return 0.0
        
        # Находим баланс в начале недели
        start_balance = None
        for entry in self.balance_history:
            if entry['timestamp'].date() >= week_start:
                if start_balance is None:
                    start_balance = entry['balance']
                break
        
        if start_balance is None:
            return 0.0
        
        return self.current_balance - start_balance

    def _calculate_current_leverage(self) -> float:
        """Рассчитывает текущее используемое плечо"""
        
        if not self.positions:
            return 0.0
        
        total_margin = sum(pos.get('margin_used', 0) for pos in self.positions.values())
        total_value = sum(pos.get('quantity', 0) * pos.get('entry_price', 0) for pos in self.positions.values())
        
        if total_margin == 0:
            return 0.0
        
        return total_value / total_margin

    def _calculate_correlation_risk(self) -> float:
        """Рассчитывает корреляционный риск"""
        
        if len(self.positions) < 2:
            return 0.0
        
        # Упрощенный расчет корреляции
        # В реальной системе здесь был бы анализ исторических данных
        symbols = [pos['symbol'] for pos in self.positions.values()]
        
        # Для демонстрации возвращаем случайное значение
        return np.random.uniform(0.0, 0.8)

    def _calculate_var_95(self) -> float:
        """Рассчитывает Value at Risk 95%"""
        
        if not self.balance_history or len(self.balance_history) < 10:
            return 0.0
        
        # Рассчитываем дневные изменения баланса
        daily_changes = []
        for i in range(1, len(self.balance_history)):
            change = self.balance_history[i]['balance'] - self.balance_history[i-1]['balance']
            daily_changes.append(change)
        
        if not daily_changes:
            return 0.0
        
        # VaR 95% - 5-й процентиль
        return np.percentile(daily_changes, 5)

    def _calculate_sharpe_ratio(self) -> float:
        """Рассчитывает Sharpe ratio"""
        
        if not self.balance_history or len(self.balance_history) < 10:
            return 0.0
        
        # Рассчитываем дневные доходности
        returns = []
        for i in range(1, len(self.balance_history)):
            prev_balance = self.balance_history[i-1]['balance']
            curr_balance = self.balance_history[i]['balance']
            if prev_balance > 0:
                returns.append((curr_balance - prev_balance) / prev_balance)
        
        if not returns:
            return 0.0
        
        # Sharpe ratio (упрощенный)
        avg_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0.0
        
        # Безрисковая ставка = 0 для упрощения
        return avg_return / std_return

    def _check_position_risks(self, position_data: Dict):
        """Проверяет риски позиции"""
        
        # Проверяем размер позиции
        position_size_pct = (position_data.get('margin_used', 0) / self.current_balance) * 100
        if position_size_pct > self.risk_limits.max_position_size_pct:
            self._create_alert(
                'position_size',
                'high',
                f"Position size {position_size_pct:.2f}% exceeds limit {self.risk_limits.max_position_size_pct}%"
            )
        
        # Проверяем плечо
        leverage = position_data.get('leverage', 1.0)
        if leverage > self.risk_limits.max_leverage:
            self._create_alert(
                'leverage',
                'high',
                f"Leverage {leverage:.1f}x exceeds limit {self.risk_limits.max_leverage}x"
            )

    def _create_alert(self, alert_type: str, severity: str, message: str):
        """Создает алерт о риске"""
        
        # Проверяем cooldown
        recent_alerts = [
            alert for alert in self.risk_alerts
            if alert.alert_type == alert_type and 
            (get_utc_now() - alert.timestamp).total_seconds() < self.monitoring_settings['alert_cooldown']
        ]
        
        if recent_alerts:
            return  # Пропускаем из-за cooldown
        
        # Проверяем лимит алертов в час
        hour_ago = get_utc_now() - timedelta(hours=1)
        recent_alerts_count = len([
            alert for alert in self.risk_alerts
            if alert.timestamp > hour_ago
        ])
        
        if recent_alerts_count >= self.monitoring_settings['max_alerts_per_hour']:
            return  # Пропускаем из-за лимита
        
        alert = RiskAlert(
            alert_id=f"ALERT_{int(get_utc_now().timestamp())}",
            alert_type=alert_type,
            severity=severity,
            message=message
        )
        
        self.risk_alerts.append(alert)
        self.risk_stats['total_alerts'] += 1
        
        if severity == 'critical':
            self.risk_stats['critical_alerts'] += 1
        
        logger.warning(f"Risk alert: {alert_type} - {message}")
        
        # Принимаем автоматические действия
        self._take_automatic_action(alert)

    def _take_automatic_action(self, alert: RiskAlert):
        """Принимает автоматические действия по алерту"""
        
        if not self.monitoring_settings['auto_reduce_exposure']:
            return
        
        if alert.alert_type == 'drawdown' and alert.severity == 'critical':
            # Критическая просадка - закрываем все позиции
            self._emergency_stop()
            alert.action_taken = 'emergency_stop'
            
        elif alert.alert_type == 'daily_loss' and alert.severity == 'high':
            # Большой дневной убыток - снижаем экспозицию
            self._reduce_exposure(0.5)  # Снижаем на 50%
            alert.action_taken = 'reduce_exposure_50'
            
        elif alert.alert_type == 'leverage' and alert.severity == 'high':
            # Высокое плечо - снижаем размер позиций
            self._reduce_position_sizes(0.3)  # Снижаем на 30%
            alert.action_taken = 'reduce_position_sizes_30'
        
        if alert.action_taken:
            self.risk_stats['auto_actions_taken'] += 1

    def _emergency_stop(self):
        """Экстренная остановка торговли"""
        
        if self.monitoring_settings['emergency_stop_enabled']:
            # Здесь должна быть логика закрытия всех позиций
            logger.critical("EMERGENCY STOP: Closing all positions")
            self.risk_stats['emergency_stops'] += 1

    def _reduce_exposure(self, reduction_factor: float):
        """Снижает экспозицию"""
        
        # Здесь должна быть логика снижения экспозиции
        logger.warning(f"Reducing exposure by {reduction_factor*100}%")
        self.risk_stats['exposure_reductions'] += 1

    def _reduce_position_sizes(self, reduction_factor: float):
        """Снижает размеры позиций"""
        
        # Здесь должна быть логика снижения размеров позиций
        logger.warning(f"Reducing position sizes by {reduction_factor*100}%")

    def check_risk_limits(self) -> List[RiskAlert]:
        """Проверяет все лимиты риска"""
        
        if not self.risk_metrics:
            return []
        
        alerts = []
        
        # Проверяем просадку
        if self.risk_metrics.current_drawdown > self.risk_limits.max_drawdown_pct:
            severity = 'critical' if self.risk_metrics.current_drawdown > self.risk_limits.max_drawdown_pct * 1.5 else 'high'
            self._create_alert(
                'drawdown',
                severity,
                f"Current drawdown {self.risk_metrics.current_drawdown:.2f}% exceeds limit {self.risk_limits.max_drawdown_pct}%"
            )
        
        # Проверяем дневной убыток
        if self.risk_metrics.daily_pnl < -self.risk_limits.max_daily_loss_pct:
            severity = 'critical' if abs(self.risk_metrics.daily_pnl) > self.risk_limits.max_daily_loss_pct * 1.5 else 'high'
            self._create_alert(
                'daily_loss',
                severity,
                f"Daily loss {abs(self.risk_metrics.daily_pnl):.2f}% exceeds limit {self.risk_limits.max_daily_loss_pct}%"
            )
        
        # Проверяем недельный убыток
        if self.risk_metrics.weekly_pnl < -self.risk_limits.max_weekly_loss_pct:
            severity = 'critical' if abs(self.risk_metrics.weekly_pnl) > self.risk_limits.max_weekly_loss_pct * 1.5 else 'high'
            self._create_alert(
                'weekly_loss',
                severity,
                f"Weekly loss {abs(self.risk_metrics.weekly_pnl):.2f}% exceeds limit {self.risk_limits.max_weekly_loss_pct}%"
            )
        
        # Проверяем плечо
        if self.risk_metrics.leverage_used > self.risk_limits.max_leverage:
            self._create_alert(
                'leverage',
                'high',
                f"Current leverage {self.risk_metrics.leverage_used:.1f}x exceeds limit {self.risk_limits.max_leverage}x"
            )
        
        # Проверяем корреляцию
        if self.risk_metrics.correlation_risk > self.risk_limits.max_correlation_risk:
            self._create_alert(
                'correlation',
                'medium',
                f"Correlation risk {self.risk_metrics.correlation_risk:.2f} exceeds limit {self.risk_limits.max_correlation_risk}"
            )
        
        return alerts

    def get_risk_report(self) -> Dict:
        """Возвращает отчет о рисках"""
        
        if not self.risk_metrics:
            return {'error': 'Risk metrics not calculated'}
        
        return {
            'risk_metrics': {
                'current_drawdown': self.risk_metrics.current_drawdown,
                'daily_pnl': self.risk_metrics.daily_pnl,
                'weekly_pnl': self.risk_metrics.weekly_pnl,
                'total_exposure': self.risk_metrics.total_exposure,
                'leverage_used': self.risk_metrics.leverage_used,
                'correlation_risk': self.risk_metrics.correlation_risk,
                'var_95': self.risk_metrics.var_95,
                'sharpe_ratio': self.risk_metrics.sharpe_ratio,
                'max_drawdown': self.risk_metrics.max_drawdown,
                'current_balance': self.risk_metrics.current_balance,
                'peak_balance': self.risk_metrics.peak_balance
            },
            'risk_limits': {
                'max_drawdown_pct': self.risk_limits.max_drawdown_pct,
                'max_daily_loss_pct': self.risk_limits.max_daily_loss_pct,
                'max_weekly_loss_pct': self.risk_limits.max_weekly_loss_pct,
                'max_position_size_pct': self.risk_limits.max_position_size_pct,
                'max_correlation_risk': self.risk_limits.max_correlation_risk,
                'max_leverage': self.risk_limits.max_leverage,
                'min_capital_reserve_pct': self.risk_limits.min_capital_reserve_pct
            },
            'active_alerts': [
                {
                    'alert_id': alert.alert_id,
                    'alert_type': alert.alert_type,
                    'severity': alert.severity,
                    'message': alert.message,
                    'timestamp': alert.timestamp.isoformat(),
                    'resolved': alert.resolved,
                    'action_taken': alert.action_taken
                } for alert in self.risk_alerts if not alert.resolved
            ],
            'risk_stats': self.risk_stats,
            'positions_count': len(self.positions),
            'timestamp': get_utc_now().isoformat()
        }

    def resolve_alert(self, alert_id: str):
        """Помечает алерт как решенный"""
        
        for alert in self.risk_alerts:
            if alert.alert_id == alert_id:
                alert.resolved = True
                logger.info(f"Alert {alert_id} resolved")
                break

    def update_risk_limits(self, new_limits: Dict):
        """Обновляет лимиты риска"""
        
        for key, value in new_limits.items():
            if hasattr(self.risk_limits, key):
                setattr(self.risk_limits, key, value)
        
        logger.info("Risk limits updated")

    def save_state(self, filepath: str = 'risk_monitor_state.json'):
        """Сохраняет состояние системы"""
        
        state = {
            'risk_limits': self.risk_limits.__dict__,
            'risk_alerts': [
                {
                    'alert_id': alert.alert_id,
                    'alert_type': alert.alert_type,
                    'severity': alert.severity,
                    'message': alert.message,
                    'timestamp': alert.timestamp.isoformat(),
                    'resolved': alert.resolved,
                    'action_taken': alert.action_taken
                } for alert in self.risk_alerts
            ],
            'risk_stats': self.risk_stats,
            'monitoring_settings': self.monitoring_settings,
            'balance_history': [
                {
                    'timestamp': entry['timestamp'].isoformat(),
                    'balance': entry['balance']
                } for entry in self.balance_history
            ],
            'positions': self.positions,
            'peak_balance': self.peak_balance,
            'current_balance': self.current_balance
        }
        
        with open(filepath, 'w') as f:
            json.dump(state, f, indent=2)
        
        logger.info(f"Risk monitor state saved to {filepath}")

    def load_state(self, filepath: str = 'risk_monitor_state.json'):
        """Загружает состояние системы"""
        
        if not os.path.exists(filepath):
            logger.warning(f"State file {filepath} not found")
            return
        
        with open(filepath, 'r') as f:
            state = json.load(f)
        
        # Восстанавливаем лимиты риска
        if state.get('risk_limits'):
            self.risk_limits = RiskLimits(**state['risk_limits'])
        
        # Восстанавливаем алерты
        if state.get('risk_alerts'):
            self.risk_alerts = []
            for alert_data in state['risk_alerts']:
                alert_data['timestamp'] = datetime.fromisoformat(alert_data['timestamp'])
                self.risk_alerts.append(RiskAlert(**alert_data))
        
        # Восстанавливаем статистику
        if state.get('risk_stats'):
            self.risk_stats = state['risk_stats']
        
        if state.get('monitoring_settings'):
            self.monitoring_settings = state['monitoring_settings']
        
        # Восстанавливаем историю баланса
        if state.get('balance_history'):
            self.balance_history = []
            for entry in state['balance_history']:
                entry['timestamp'] = datetime.fromisoformat(entry['timestamp'])
                self.balance_history.append(entry)
        
        if state.get('positions'):
            self.positions = state['positions']
        
        if state.get('peak_balance'):
            self.peak_balance = state['peak_balance']
        
        if state.get('current_balance'):
            self.current_balance = state['current_balance']
        
        logger.info(f"Risk monitor state loaded from {filepath}")

# Глобальный экземпляр
risk_monitor = RiskMonitor()
