#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль расчета метрик производительности для крипторынка (24/7)
Использует данные из таблицы trades в БД
"""

import logging
import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from src.shared.utils.datetime_utils import get_utc_now
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)

CAPITAL_BASE_USD = 1_000.0

# Импортируем расширенные метрики
try:
    from extended_metrics import calculate_var, calculate_cvar, calculate_calmar_ratio, calculate_extended_metrics
except ImportError:
    # Fallback если модуль не найден
    logger.warning("Модуль extended_metrics не найден, расширенные метрики будут рассчитаны встроенным методом")
    calculate_var = None
    calculate_cvar = None
    calculate_calmar_ratio = None
    calculate_extended_metrics = None


class PerformanceMetricsCalculator:
    """Расчет метрик производительности из реальных сделок"""
    
    def __init__(self, db_path: str = "trading.db"):
        self.db_path = db_path
    
    def calculate_metrics(
        self,
        user_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        trade_mode: Optional[str] = None,
        risk_free_rate: float = 0.02,  # 2% годовых
    ) -> Dict[str, Any]:
        """
        Рассчитывает полные метрики производительности
        
        Args:
            user_id: ID пользователя (None для всех)
            start_date: Начальная дата (None для всех)
            end_date: Конечная дата (None для всех)
            risk_free_rate: Безрисковая ставка (годовая, 2%)
        
        Returns:
            Словарь с метриками
        """
        try:
            trades = self._get_trades_from_db(
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
                trade_mode=trade_mode,
            )

            if not trades:
                return self._empty_metrics(
                    start_date=start_date,
                    end_date=end_date,
                    user_id=user_id,
                    trade_mode=trade_mode,
                    risk_free_rate=risk_free_rate,
                )

            df = pd.DataFrame(trades)
            metrics = self._calculate_metrics_from_df(
                df=df,
                start_date=start_date,
                end_date=end_date,
                user_id=user_id,
                trade_mode=trade_mode,
                risk_free_rate=risk_free_rate,
            )
            metrics["start_date"] = start_date.isoformat() if start_date else None
            metrics["end_date"] = end_date.isoformat() if end_date else None
            metrics["user_id"] = user_id
            metrics["trade_mode"] = trade_mode
            metrics["risk_free_rate"] = risk_free_rate
            return metrics
            
        except Exception as e:
            logger.error("❌ Ошибка расчета метрик: %s", e, exc_info=True)
            return self._empty_metrics(
                start_date=start_date,
                end_date=end_date,
                user_id=user_id,
                trade_mode=trade_mode,
                risk_free_rate=risk_free_rate,
            )
    
    def calculate_metrics_by_mode(
        self,
        trade_modes: Optional[List[Optional[str]]] = None,
        user_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        risk_free_rate: float = 0.02,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Возвращает метрики для набора торговых режимов.

        trade_modes: список режимов (например, [None, "live", "backfill"]).
        None в списке означает агрегированные метрики по всем режимам.
        """
        modes = trade_modes or [None, "live", "backfill", "futures"]
        result: Dict[str, Dict[str, Any]] = {}
        for mode in modes:
            metrics = self.calculate_metrics(
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
                trade_mode=mode,
                risk_free_rate=risk_free_rate,
            )
            key = mode or "all"
            result[key] = metrics
        return result
    
    def _get_trades_from_db(
        self,
        user_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        trade_mode: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Получает сделки из БД"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM trades WHERE 1=1"
            params = []
            
            if user_id:
                query += " AND user_id = ?"
                params.append(str(user_id))
            
            if start_date:
                query += " AND exit_time >= ?"
                params.append(start_date.isoformat())
            
            if end_date:
                query += " AND exit_time <= ?"
                params.append(end_date.isoformat())

            if trade_mode:
                query += " AND trade_mode = ?"
                params.append(trade_mode)
            
            query += " ORDER BY exit_time ASC"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            
            trades = [dict(row) for row in rows]
            return trades
            
        except Exception as e:
            logger.error("❌ Ошибка получения сделок: %s", e)
            return []
    
    def _calculate_daily_returns(self, df: pd.DataFrame) -> pd.Series:
        """Рассчитывает дневные доходности (для крипторынка 24/7)"""
        if df.empty:
            return pd.Series(dtype=float)
        
        df_local = df.copy()
        if 'exit_dt' in df_local.columns:
            df_local['exit_dt'] = pd.to_datetime(df_local['exit_dt'], errors='coerce', utc=True)
        else:
            df_local['exit_dt'] = pd.to_datetime(df_local['exit_time'], errors='coerce', utc=True, format='mixed')
        df_local = df_local.dropna(subset=['exit_dt'])
        if df_local.empty:
            return pd.Series(dtype=float)
        
        df_local['exit_date'] = df_local['exit_dt'].dt.tz_convert('UTC').dt.date
        daily_pnl = df_local.groupby('exit_date')['net_pnl_usd'].sum().sort_index()
        
        # Доходность относительно базового капитала
        daily_returns = (daily_pnl / CAPITAL_BASE_USD).astype(float)
        
        return daily_returns
    
    def _calculate_sharpe_ratio(self, returns: pd.Series, risk_free_rate: float) -> float:
        """Рассчитывает Sharpe Ratio для 24/7 рынка"""
        if len(returns) < 2:
            return 0.0
        
        # Годовая доходность (365 дней для крипторынка)
        annual_return = returns.mean() * 365
        
        # Годовая волатильность
        annual_volatility = returns.std() * np.sqrt(365)
        
        if annual_volatility == 0:
            return 0.0
        
        # Sharpe Ratio
        sharpe = (annual_return - risk_free_rate) / annual_volatility
        
        return sharpe
    
    def _calculate_sortino_ratio(self, returns: pd.Series, risk_free_rate: float) -> float:
        """Рассчитывает Sortino Ratio (только отрицательные доходности)"""
        if len(returns) < 2:
            return 0.0
        
        # Годовая доходность
        annual_return = returns.mean() * 365
        
        # Отрицательные доходности
        negative_returns = returns[returns < 0]
        
        if len(negative_returns) == 0:
            # Если нет убытков, Sortino = Sharpe
            return self._calculate_sharpe_ratio(returns, risk_free_rate)
        
        # Годовая downside волатильность
        downside_volatility = negative_returns.std() * np.sqrt(365)
        
        if downside_volatility == 0:
            return 0.0
        
        # Sortino Ratio
        sortino = (annual_return - risk_free_rate) / downside_volatility
        
        return sortino
    
    def _calculate_max_drawdown(self, df: pd.DataFrame) -> float:
        """Рассчитывает максимальную просадку"""
        if df.empty:
            return 0.0
        
        # Сортируем по времени
        sort_column = 'exit_dt' if 'exit_dt' in df.columns else 'exit_time'
        df_sorted = df.sort_values(sort_column)
        
        cumulative_pnl = df_sorted['net_pnl_usd'].cumsum()
        equity_curve = CAPITAL_BASE_USD + cumulative_pnl
        
        running_max = equity_curve.cummax()
        
        drawdown = (equity_curve - running_max) / running_max.replace(0, np.nan)
        
        # Максимальная просадка
        max_dd = abs(drawdown.min()) if len(drawdown[~drawdown.isna()]) > 0 else 0.0
        
        return max_dd
    
    def _calculate_consecutive_streaks(self, df: pd.DataFrame) -> Tuple[int, int]:
        """Рассчитывает максимальные серии побед и поражений"""
        if df.empty:
            return 0, 0
        
        # Определяем результат каждой сделки
        results = (df['pnl_usd'] > 0).astype(int)
        
        # Находим серии
        max_wins = 0
        max_losses = 0
        current_win_streak = 0
        current_loss_streak = 0
        
        for result in results:
            if result == 1:  # Win
                current_win_streak += 1
                current_loss_streak = 0
                max_wins = max(max_wins, current_win_streak)
            else:  # Loss
                current_loss_streak += 1
                current_win_streak = 0
                max_losses = max(max_losses, current_loss_streak)
        
        return max_wins, max_losses
    
    def _empty_metrics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        user_id: Optional[str] = None,
        trade_mode: Optional[str] = None,
        risk_free_rate: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Возвращает пустые метрики"""
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0,
            'total_pnl_usd': 0,
            'total_net_pnl_usd': 0,
            'avg_pnl_usd': 0,
            'avg_pnl_percent': 0,
            'total_profit': 0,
            'total_loss': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'largest_win': 0,
            'largest_loss': 0,
            'profit_factor': 0,
            'sharpe_ratio': 0,
            'sortino_ratio': 0,
            'calmar_ratio': 0,
            'max_drawdown_pct': 0,
            'volatility_pct': 0,
            'annual_return_pct': 0,
            'var_95_pct': 0,
            'var_99_pct': 0,
            'cvar_95_pct': 0,
            'cvar_99_pct': 0,
            'consecutive_wins': 0,
            'consecutive_losses': 0,
            'avg_duration_minutes': 0,
            'avg_daily_profit_usd': 0,
            'avg_monthly_profit_usd': 0,
            'trading_days': 0,
            'start_date': start_date.isoformat() if start_date else None,
            'end_date': end_date.isoformat() if end_date else None,
            'user_id': user_id,
            'trade_mode': trade_mode,
            'risk_free_rate': risk_free_rate,
        }
    
    def get_symbol_performance(self, symbol: str, limit_days: int = 90, trade_mode: Optional[str] = None) -> Dict[str, Any]:
        """Получает производительность по конкретному символу"""
        try:
            start_date = get_utc_now() - timedelta(days=limit_days)
            trades = self._get_trades_from_db(start_date=start_date, trade_mode=trade_mode)
            # Фильтруем по символу
            trades = [t for t in trades if t.get('symbol') == symbol]
            if not trades:
                return self._empty_metrics(start_date=start_date, user_id=None, trade_mode=trade_mode)
            
            df = pd.DataFrame(trades)
            # Используем существующую логику расчета метрик
            return self._calculate_metrics_from_df(
                df=df,
                start_date=start_date,
                end_date=None,
                user_id=None,
                trade_mode=trade_mode,
                risk_free_rate=0.02,
            )
        except Exception as e:
            logger.error("❌ Ошибка получения производительности символа: %s", e)
            return self._empty_metrics(start_date=start_date, user_id=None, trade_mode=trade_mode)
    
    def _calculate_metrics_from_df(
        self,
        df: pd.DataFrame,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        user_id: Optional[str],
        trade_mode: Optional[str],
        risk_free_rate: float,
    ) -> Dict[str, Any]:
        """Внутренний метод расчета метрик из DataFrame"""
        if df.empty:
            return self._empty_metrics(
                start_date=start_date,
                end_date=end_date,
                user_id=user_id,
                trade_mode=trade_mode,
                risk_free_rate=risk_free_rate,
            )

        df = df.copy()
        df['exit_dt'] = pd.to_datetime(df['exit_time'], errors='coerce', utc=True, format='mixed')
        df = df.dropna(subset=['exit_dt'])
        if df.empty:
            return self._empty_metrics(
                start_date=start_date,
                end_date=end_date,
                user_id=user_id,
                trade_mode=trade_mode,
                risk_free_rate=risk_free_rate,
            )

        if 'entry_time' in df.columns:
            df['entry_dt'] = pd.to_datetime(df['entry_time'], errors='coerce', utc=True, format='mixed')
        else:
            df['entry_dt'] = pd.NaT

        # Рассчитываем базовые метрики
        total_trades = len(df)
        winning_trades = len(df[df['pnl_usd'] > 0])
        losing_trades = len(df[df['pnl_usd'] < 0])
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
        
        # PnL метрики
        total_pnl_usd = df['pnl_usd'].sum()
        total_net_pnl_usd = df['net_pnl_usd'].sum()
        avg_pnl_usd = df['pnl_usd'].mean()
        avg_pnl_percent = df['pnl_percent'].mean()
        
        # Прибыли и убытки
        profits = df[df['pnl_usd'] > 0]['pnl_usd']
        losses = df[df['pnl_usd'] < 0]['pnl_usd']
        
        total_profit = profits.sum() if len(profits) > 0 else 0
        total_loss = abs(losses.sum()) if len(losses) > 0 else 0
        avg_win = profits.mean() if len(profits) > 0 else 0
        avg_loss = losses.mean() if len(losses) > 0 else 0
        largest_win = profits.max() if len(profits) > 0 else 0
        largest_loss = losses.min() if len(losses) > 0 else 0
        
        # Profit Factor
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
        
        # Рассчитываем дневные доходности
        daily_returns = self._calculate_daily_returns(df)
        trading_days = len(daily_returns)
        avg_daily_profit_usd = daily_returns.mean() * CAPITAL_BASE_USD if trading_days else 0.0
        avg_monthly_profit_usd = avg_daily_profit_usd * 30 if trading_days else 0.0
        # Sharpe Ratio
        sharpe_ratio = self._calculate_sharpe_ratio(daily_returns, risk_free_rate)
        
        # Sortino Ratio
        sortino_ratio = self._calculate_sortino_ratio(daily_returns, risk_free_rate)
        
        # Max Drawdown
        max_drawdown = self._calculate_max_drawdown(df)
        
        # Calmar Ratio (используем расширенный модуль если доступен)
        annual_return = daily_returns.mean() * 365 if len(daily_returns) > 0 else 0
        if calculate_calmar_ratio is not None:
            try:
                calmar_ratio = calculate_calmar_ratio(annual_return, max_drawdown)
            except Exception:
                calmar_ratio = (annual_return / max_drawdown) if max_drawdown > 0 else 0
        else:
            calmar_ratio = (annual_return / max_drawdown) if max_drawdown > 0 else 0
        
        # Волатильность
        volatility = daily_returns.std() * np.sqrt(365) if len(daily_returns) > 1 else 0
        
        # Расширенные метрики (VaR, CVaR)
        var_95 = 0.0
        var_99 = 0.0
        cvar_95 = 0.0
        cvar_99 = 0.0
        
        if len(daily_returns) > 0:
            if calculate_var is not None and calculate_cvar is not None:
                try:
                    var_95 = calculate_var(daily_returns, confidence=0.95) * 100
                    var_99 = calculate_var(daily_returns, confidence=0.99) * 100
                    cvar_95 = calculate_cvar(daily_returns, confidence=0.95) * 100
                    cvar_99 = calculate_cvar(daily_returns, confidence=0.99) * 100
                except Exception as e:
                    logger.warning(f"Ошибка расчета VaR/CVaR: {e}")
            else:
                # Fallback расчет VaR/CVaR
                try:
                    var_95 = abs(daily_returns.quantile(0.05)) * 100
                    var_99 = abs(daily_returns.quantile(0.01)) * 100
                    var_95_threshold = daily_returns.quantile(0.05)
                    var_99_threshold = daily_returns.quantile(0.01)
                    cvar_95_returns = daily_returns[daily_returns <= var_95_threshold]
                    cvar_99_returns = daily_returns[daily_returns <= var_99_threshold]
                    cvar_95 = abs(cvar_95_returns.mean()) * 100 if len(cvar_95_returns) > 0 else var_95
                    cvar_99 = abs(cvar_99_returns.mean()) * 100 if len(cvar_99_returns) > 0 else var_99
                except Exception:
                    pass
        
        # Строки побед/поражений
        consecutive_wins, consecutive_losses = self._calculate_consecutive_streaks(df)
        
        # Среднее время удержания
        if 'duration_minutes' in df.columns and df['duration_minutes'].notna().any():
            avg_duration_minutes = float(df['duration_minutes'].dropna().mean())
        else:
            durations = (
                df['exit_dt'] - df['entry_dt']
                if 'entry_dt' in df.columns
                else pd.Series(dtype='timedelta64[ns]')
            )
            avg_duration_minutes = (
                float((durations.dt.total_seconds() / 60).dropna().mean())
                if not durations.empty and durations.notna().any()
                else 0.0
            )
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_pnl_usd': total_pnl_usd,
            'total_net_pnl_usd': total_net_pnl_usd,
            'avg_pnl_usd': avg_pnl_usd,
            'avg_pnl_percent': avg_pnl_percent,
            'total_profit': total_profit,
            'total_loss': total_loss,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'largest_win': largest_win,
            'largest_loss': largest_loss,
            'profit_factor': profit_factor,
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'calmar_ratio': calmar_ratio,
            'max_drawdown_pct': max_drawdown * 100,
            'volatility_pct': volatility * 100,
            'annual_return_pct': annual_return * 100,
            'var_95_pct': var_95,
            'var_99_pct': var_99,
            'cvar_95_pct': cvar_95,
            'cvar_99_pct': cvar_99,
            'consecutive_wins': consecutive_wins,
            'consecutive_losses': consecutive_losses,
            'avg_duration_minutes': avg_duration_minutes,
            'avg_daily_profit_usd': avg_daily_profit_usd,
            'avg_monthly_profit_usd': avg_monthly_profit_usd,
            'trading_days': trading_days,
            'start_date': start_date.isoformat() if start_date else None,
            'end_date': end_date.isoformat() if end_date else None,
            'user_id': user_id,
            'trade_mode': trade_mode,
            'risk_free_rate': risk_free_rate,
        }
    
    def get_daily_stats(self, days: int = 30) -> List[Dict[str, Any]]:
        """Получает дневную статистику"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            start_date = get_utc_now() - timedelta(days=days)
            
            cursor.execute("""
                SELECT 
                    DATE(exit_time) as trade_date,
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as winning_trades,
                    SUM(CASE WHEN pnl_usd < 0 THEN 1 ELSE 0 END) as losing_trades,
                    SUM(pnl_usd) as total_pnl_usd,
                    SUM(net_pnl_usd) as total_net_pnl_usd,
                    AVG(pnl_percent) as avg_pnl_percent
                FROM trades
                WHERE exit_time >= ?
                GROUP BY DATE(exit_time)
                ORDER BY trade_date DESC
            """, (start_date.isoformat(),))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error("❌ Ошибка получения дневной статистики: %s", e)
            return []


# Singleton instance
_metrics_calculator_instance = None

def get_metrics_calculator(db_path: str = "trading.db") -> PerformanceMetricsCalculator:
    """Получить экземпляр PerformanceMetricsCalculator (singleton)"""
    global _metrics_calculator_instance
    if _metrics_calculator_instance is None:
        _metrics_calculator_instance = PerformanceMetricsCalculator(db_path)
    return _metrics_calculator_instance
