#!/usr/bin/env python3

"""
Улучшенная система риск-менеджмента для торгового бота.

Предоставляет динамические лимиты позиций, защиту от маржин-колла,
адаптивное управление рисками и мониторинг корреляций.
"""

import asyncio
import json
import logging
import os
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

import config
from src.shared.utils.datetime_utils import get_utc_now

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Позиция в портфеле (🚀 ТОЧНОСТЬ DECIMAL)"""

    symbol: str
    side: str  # 'long' или 'short'
    quantity: Decimal
    entry_price: Decimal
    current_price: Decimal
    leverage: Decimal = Decimal("1.0")
    risk_pct: Decimal = Decimal("2.0")
    margin_used: Decimal = Decimal("0.0")
    unrealized_pnl: Decimal = Decimal("0.0")
    timestamp: datetime = field(default_factory=get_utc_now)


@dataclass
class RiskLimits:
    """Лимиты риска (🚀 ТОЧНОСТЬ DECIMAL)"""

    max_position_size_pct: Decimal = field(
        default_factory=lambda: Decimal(str(os.getenv("MAX_POSITION_SIZE_PCT", 10.0)))
    )
    max_total_risk_pct: Decimal = field(
        default_factory=lambda: Decimal(str(getattr(config, "PORTFOLIO_MAX_RISK_PCT", 8.0)))
    )
    max_correlation: Decimal = field(
        default_factory=lambda: Decimal(str(getattr(config, "CORRELATION_MAX_PAIRWISE", 0.85)))
    )
    max_positions: int = field(
        default_factory=lambda: int(getattr(config, "MAX_CONCURRENT_SYMBOLS", 6))
    )
    max_drawdown_pct: Decimal = field(
        default_factory=lambda: Decimal(str(os.getenv("MAX_DRAWDOWN_PCT", 15.0)))
    )
    margin_call_threshold: Decimal = field(
        default_factory=lambda: Decimal(str(os.getenv("MARGIN_CALL_THRESHOLD", 0.8)))
    )


@dataclass
class PortfolioMetrics:
    """Метрики портфеля (🚀 ТОЧНОСТЬ DECIMAL)"""

    total_balance: Decimal
    used_margin: Decimal
    free_margin: Decimal
    total_risk: Decimal
    total_pnl: Decimal
    positions_count: int
    max_correlation: Decimal
    portfolio_beta: Decimal
    var_95: Decimal
    sharpe_ratio: Decimal
    sortino_ratio: Decimal


class CorrelationAnalyzer:
    """Анализатор корреляций между активами"""

    def __init__(self, lookback_days: int = 30):
        self.lookback_days = lookback_days
        self.price_data = {}
        self.correlation_matrix = {}
        self.last_update = None

    async def update_correlations(self, symbols: List[str], price_data: Dict[str, List[float]]):
        """Обновляет корреляции между активами"""
        try:
            # Сохраняем данные о ценах
            for symbol, prices in price_data.items():
                self.price_data[symbol] = (
                    prices[-self.lookback_days :] if len(prices) >= self.lookback_days else prices
                )

            # Вычисляем корреляции
            if len(self.price_data) >= 2:
                self.correlation_matrix = self._calculate_correlation_matrix()
                self.last_update = get_utc_now()

                logger.info("Updated correlations for %d symbols", len(self.price_data))

        except Exception as e:
            logger.error("Error updating correlations: %s", e)

    def _calculate_correlation_matrix(self) -> Dict[Tuple[str, str], float]:
        """Вычисляет матрицу корреляций с высокой производительностью"""
        if not self.price_data or len(self.price_data) < 2:
            return {}

        try:
            # Создаем DataFrame из доходностей всех символов
            returns_data = {}
            for symbol, prices in self.price_data.items():
                if len(prices) > 1:
                    # Вычисляем доходности (векторизованно)
                    prices_arr = np.array(prices)
                    returns = (prices_arr[1:] - prices_arr[:-1]) / prices_arr[:-1]
                    returns_data[symbol] = returns

            if not returns_data:
                return {}

            # Находим минимальную длину ряда доходностей
            min_len = min(len(r) for r in returns_data.values())

            # Обрезаем все ряды до минимальной длины для корректного вычисления матрицы
            df_returns = pd.DataFrame(
                {symbol: returns[:min_len] for symbol, returns in returns_data.items()}
            )

            # Вычисляем матрицу корреляций одним вызовом (очень быстро)
            corr_matrix = df_returns.corr()

            # Преобразуем в словарь для обратной совместимости
            result = {}
            symbols = corr_matrix.columns
            for i, s1 in enumerate(symbols):
                for j, s2 in enumerate(symbols):
                    result[(s1, s2)] = float(corr_matrix.iloc[i, j])

            return result

        except Exception as e:
            logger.error(f"Error in vectorized correlation calculation: {e}")
            # Fallback к старому методу если что-то пошло не так
            return self._calculate_correlation_matrix_legacy()

    def _calculate_correlation_matrix_legacy(self) -> Dict[Tuple[str, str], float]:
        """Старый медленный метод (fallback)"""
        correlation_matrix = {}
        symbols = list(self.price_data.keys())
        for i, symbol1 in enumerate(symbols):
            for j, symbol2 in enumerate(symbols):
                if i != j:
                    prices1 = self.price_data[symbol1]
                    prices2 = self.price_data[symbol2]
                    correlation = self._calculate_correlation(prices1, prices2)
                    correlation_matrix[(symbol1, symbol2)] = correlation
                else:
                    correlation_matrix[(symbol1, symbol2)] = 1.0
        return correlation_matrix

    def _calculate_correlation(self, prices1: List[float], prices2: List[float]) -> float:
        """Вычисляет корреляцию между двумя рядами цен"""
        if len(prices1) != len(prices2) or len(prices1) < 2:
            return 0.0

        # Вычисляем доходности
        returns1 = [(prices1[i] - prices1[i - 1]) / prices1[i - 1] for i in range(1, len(prices1))]
        returns2 = [(prices2[i] - prices2[i - 1]) / prices2[i - 1] for i in range(1, len(prices2))]

        if len(returns1) < 2:
            return 0.0

        # Вычисляем корреляцию доходностей
        correlation = np.corrcoef(returns1, returns2)[0, 1]
        return correlation if not np.isnan(correlation) else 0.0

    def get_correlation(self, symbol1: str, symbol2: str) -> float:
        """Возвращает корреляцию между двумя символами"""
        return self.correlation_matrix.get((symbol1, symbol2), 0.0)

    def get_highly_correlated_pairs(self, threshold: float = 0.7) -> List[Tuple[str, str, float]]:
        """Возвращает пары с высокой корреляцией"""
        highly_correlated = []

        for (symbol1, symbol2), correlation in self.correlation_matrix.items():
            if symbol1 < symbol2 and abs(correlation) >= threshold:  # Избегаем дублирования
                highly_correlated.append((symbol1, symbol2, correlation))

        # Сортируем по убыванию корреляции
        highly_correlated.sort(key=lambda x: abs(x[2]), reverse=True)

        return highly_correlated


class PositionSizer:
    """Калькулятор размера позиций"""

    def __init__(self):
        self.base_risk_pct = 2.0  # Базовый риск на сделку
        self.max_position_pct = 10.0  # Максимальный размер позиции
        self.use_kelly_criterion = False  # Использовать Kelly Criterion
        self.kelly_fraction = 0.25  # Fractional Kelly (25% от полного Kelly для безопасности)

    def calculate_position_size(
        self,
        balance: Union[float, Decimal],
        entry_price: Union[float, Decimal],
        stop_loss_price: Union[float, Decimal],
        risk_pct: Optional[Union[float, Decimal]] = None,
        max_position_pct: Optional[Union[float, Decimal]] = None,
        use_kelly: bool = False,
        win_rate: Optional[float] = None,
        avg_win_loss_ratio: Optional[float] = None,
        ml_confidence: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Вычисляет размер позиции на основе риска (🚀 ТОЧНОСТЬ DECIMAL)
        """
        try:
            # Приведение к Decimal
            d_balance = Decimal(str(balance))
            d_entry_price = Decimal(str(entry_price))
            d_stop_price = Decimal(str(stop_loss_price))

            # Если используем Kelly Criterion
            if use_kelly:
                return self.calculate_kelly_position_size(
                    balance=d_balance,
                    entry_price=d_entry_price,
                    stop_loss_price=d_stop_price,
                    win_rate=win_rate or 0.5,
                    avg_win_loss_ratio=avg_win_loss_ratio or 1.5,
                    use_fractional=True,
                    kelly_fraction=self.kelly_fraction,
                    ml_confidence=ml_confidence,
                )

            # Стандартный метод (фиксированный риск)
            d_risk_pct = Decimal(str(risk_pct if risk_pct is not None else self.base_risk_pct))
            d_max_pos_pct = Decimal(
                str(max_position_pct if max_position_pct is not None else self.max_position_pct)
            )

            # Рассчитываем риск на сделку в абсолютном выражении
            risk_amount = d_balance * d_risk_pct / Decimal("100")

            # Рассчитываем расстояние до стоп-лосса
            if d_entry_price == 0:
                return {}

            stop_distance = abs(d_entry_price - d_stop_price) / d_entry_price

            if stop_distance == 0:
                # Fallback если стоп равен входу
                stop_distance = Decimal("0.02")  # 2% дефолт

            # Размер позиции на основе риска
            position_size_by_risk = risk_amount / (stop_distance * d_entry_price)

            # Максимальный размер позиции в абсолютном выражении
            max_position_amount = d_balance * d_max_pos_pct / Decimal("100")
            max_position_size = max_position_amount / d_entry_price

            # Выбираем меньший размер
            final_position_size = min(position_size_by_risk, max_position_size)

            # Рассчитываем маржу
            margin_used = final_position_size * d_entry_price

            return {
                "position_size": final_position_size,
                "margin_used": margin_used,
                "risk_amount": risk_amount,
                "stop_distance_pct": stop_distance * Decimal("100"),
                "position_size_pct": (margin_used / d_balance) * Decimal("100"),
                "method": "fixed_risk",
            }
        except Exception as e:
            logger.error("Ошибка в расчете размера позиции (Decimal): %s", e)
            return {}

    def calculate_adaptive_risk(
        self, balance: Decimal, recent_performance: List[Decimal], volatility: Decimal
    ) -> Decimal:
        """Вычисляет адаптивный риск на основе недавней производительности"""

        base_risk = Decimal(str(self.base_risk_pct))

        # Корректируем риск на основе недавней производительности
        if recent_performance:
            perf_floats = [float(p) for p in recent_performance[-10:]]
            avg_performance = Decimal(str(statistics.mean(perf_floats)))

            if avg_performance > 0:
                # Увеличиваем риск при хорошей производительности
                performance_multiplier = min(
                    Decimal("1.5"), Decimal("1.0") + avg_performance / Decimal("100")
                )
            else:
                # Уменьшаем риск при плохой производительности
                performance_multiplier = max(
                    Decimal("0.5"), Decimal("1.0") + avg_performance / Decimal("100")
                )
        else:
            performance_multiplier = Decimal("1.0")

        # Корректируем риск на основе волатильности
        if volatility > 0:
            # Уменьшаем риск при высокой волатильности
            volatility_multiplier = max(
                Decimal("0.5"), Decimal("1.0") - (volatility - Decimal("0.02")) * Decimal("10")
            )
        else:
            volatility_multiplier = Decimal("1.0")

        # Корректируем риск на основе размера баланса
        if balance < Decimal("1000"):
            # Меньший риск для маленьких депозитов
            balance_multiplier = Decimal("0.7")
        elif balance > Decimal("10000"):
            # Больший риск для больших депозитов
            balance_multiplier = Decimal("1.2")
        else:
            balance_multiplier = Decimal("1.0")

        adaptive_risk = (
            base_risk * performance_multiplier * volatility_multiplier * balance_multiplier
        )

        # Ограничиваем риск (согласно инвариантам)
        return max(Decimal("0.5"), min(Decimal("5.0"), adaptive_risk))

    def calculate_kelly_position_size(
        self,
        balance: Union[float, Decimal],
        entry_price: Union[float, Decimal],
        stop_loss_price: Union[float, Decimal],
        win_rate: float = 0.5,
        avg_win_loss_ratio: float = 1.5,
        use_fractional: bool = True,
        kelly_fraction: float = 0.25,
        ml_confidence: Optional[float] = None,
        confidence_score: Optional[float] = None,  # 🆕 Добавлен score от CompositeEngine
    ) -> Dict[str, Any]:
        """
        Вычисляет размер позиции используя Kelly Criterion (🚀 ТОЧНОСТЬ DECIMAL)
        """
        try:
            # Приведение к Decimal
            d_balance = Decimal(str(balance))
            d_entry_price = Decimal(str(entry_price))
            d_stop_price = Decimal(str(stop_loss_price))

            p = float(win_rate)  # Вероятность выигрыша

            # 🧠 Если передана уверенность ML, корректируем win_rate (p)
            if ml_confidence is not None:
                p = (p + float(ml_confidence)) / 2

            q = 1.0 - p  # Вероятность проигрыша
            b = float(avg_win_loss_ratio)  # Коэффициент выигрыша

            # Полный Kelly
            if b > 0:
                full_kelly = (p * b - q) / b
            else:
                full_kelly = 0.0

            # Ограничиваем Kelly (не может быть отрицательным или > 1.0)
            full_kelly = max(0.0, min(1.0, full_kelly))

            # Fractional Kelly (безопаснее)
            if use_fractional:
                kelly_fraction_value = full_kelly * float(kelly_fraction)
            else:
                kelly_fraction_value = full_kelly

            # 🧠 🆕 Дополнительная коррекция по уверенности CompositeEngine
            if confidence_score is not None:
                # confidence_score обычно 0.0 - 1.0
                kelly_fraction_value *= float(confidence_score)

            # 🧠 Дополнительная коррекция по уверенности ML
            if ml_confidence is not None and ml_confidence < 0.6:
                kelly_fraction_value *= 0.5

            # Конвертируем финальный коэффициент в Decimal для расчетов денег
            d_kelly_fraction = Decimal(str(kelly_fraction_value))

            # Размер позиции в процентах от баланса
            position_size_pct = d_kelly_fraction * Decimal("100")

            # Ограничиваем максимальным размером позиции
            # (ВАЖНО: здесь мы используем d_kelly_fraction * 100, но не более лимита)
            # Мы будем ограничивать это в вызывающем методе RiskManager

            # Рассчитываем размер позиции в абсолютном выражении
            position_amount = d_balance * position_size_pct / Decimal("100")

            if d_entry_price == 0:
                return {}

            position_size = position_amount / d_entry_price

            # Рассчитываем риск
            stop_distance = abs(d_entry_price - d_stop_price) / d_entry_price
            risk_amount = position_amount * stop_distance

            return {
                "position_size": position_size,
                "margin_used": position_amount,
                "risk_amount": risk_amount,
                "stop_distance_pct": stop_distance * Decimal("100"),
                "position_size_pct": position_size_pct,
                "kelly_fraction": d_kelly_fraction,
                "full_kelly": Decimal(str(full_kelly)),
                "confidence_score": confidence_score,
                "ml_confidence": ml_confidence,
                "method": "kelly_criterion_intelligent",
            }
        except Exception as e:
            logger.error("Ошибка в Kelly (Decimal): %s", e)
            return {}


class RiskManager:
    """Главный класс управления рисками"""

    def __init__(self, risk_limits: RiskLimits = None):
        self.risk_limits = risk_limits or RiskLimits()
        self.positions: List[Position] = []
        self.balance = Decimal("1000.0")  # Начальный баланс
        self.correlation_analyzer = CorrelationAnalyzer()
        self.position_sizer = PositionSizer()

        # История производительности для адаптивного риска
        self.performance_history: List[Decimal] = []

        # История сделок для Kelly Criterion
        self.trade_history = []

        # Мониторинг просадки
        self.peak_balance = self.balance
        self.current_drawdown = Decimal("0.0")

        # 🆕 Множители риска по режимам рынка
        self.regime_multipliers = {
            "BULL_TREND": Decimal("1.2"),
            "BEAR_TREND": Decimal("1.0"),
            "HIGH_VOL_RANGE": Decimal("0.8"),
            "LOW_VOL_RANGE": Decimal("0.7"),
            "REVERSAL": Decimal("0.9"),
            "CRASH": Decimal("0.4"),  # Резкое снижение риска
            "NORMAL": Decimal("1.0"),
        }

    def update_balance(self, new_balance: Union[float, Decimal]):
        """Обновляет баланс (🚀 ТОЧНОСТЬ DECIMAL)"""
        self.balance = Decimal(str(new_balance))

        # Обновляем пиковый баланс
        if self.balance > self.peak_balance:
            self.peak_balance = self.balance

        # Вычисляем текущую просадку
        if self.peak_balance > 0:
            self.current_drawdown = (
                (self.peak_balance - self.balance) / self.peak_balance * Decimal("100.0")
            )

    def add_position(self, position: Position) -> bool:
        """Добавляет позицию с проверкой рисков"""

        # Проверяем лимиты
        if not self.check_position_limits(position):
            return False

        # Проверяем корреляции
        if not self._check_correlation_limits(position):
            return False

        # Проверяем маржин-требования
        if not self._check_margin_requirements(position):
            return False

        # Добавляем позицию
        self.positions.append(position)

        logger.info(
            "Position added: %s %s %.4f", position.symbol, position.side, float(position.quantity)
        )
        return True

    def remove_position(self, symbol: str, side: str) -> Optional[Position]:
        """Удаляет позицию"""
        for i, position in enumerate(self.positions):
            if position.symbol == symbol and position.side == side:
                removed_position = self.positions.pop(i)

                # Обновляем историю производительности
                pnl = self._calculate_pnl(removed_position)
                self.performance_history.append(pnl)

                logger.info("Position removed: %s %s", symbol, side)
                return removed_position

        return None

    def check_position_limits(self, position: Position) -> bool:
        """Проверяет лимиты позиции"""

        # Проверяем максимальное количество позиций
        if len(self.positions) >= self.risk_limits.max_positions:
            logger.warning("Maximum positions limit reached: %d", len(self.positions))
            return False

        # Проверяем максимальный размер позиции
        position_value = position.quantity * position.entry_price
        if self.balance > 0:
            position_pct = (position_value / self.balance) * Decimal("100.0")
        else:
            position_pct = Decimal("100.0")

        if position_pct > self.risk_limits.max_position_size_pct:
            logger.warning(
                "Position size too large: %.2f%% > %.2f%%",
                float(position_pct),
                float(self.risk_limits.max_position_size_pct),
            )
            return False

        return True

    def _check_correlation_limits(self, new_position: Position) -> bool:
        """Проверяет лимиты корреляции"""

        for existing_position in self.positions:
            if existing_position.symbol == new_position.symbol:
                # Не разрешаем дублирующие позиции по одному символу
                logger.warning("Duplicate position for symbol %s", new_position.symbol)
                return False

            # Проверяем корреляцию
            correlation = self.correlation_analyzer.get_correlation(
                existing_position.symbol, new_position.symbol
            )

            if abs(correlation) > float(self.risk_limits.max_correlation):
                logger.warning(
                    "High correlation between %s and %s: %.3f",
                    existing_position.symbol,
                    new_position.symbol,
                    correlation,
                )
                return False

        return True

    def _check_margin_requirements(self, position: Position) -> bool:
        """Проверяет маржин-требования"""

        # Вычисляем общую используемую маржу
        total_margin = sum(pos.margin_used for pos in self.positions)
        new_total_margin = total_margin + position.margin_used

        # Проверяем, не превышает ли общая маржа допустимый лимит
        max_margin = self.balance * (self.risk_limits.max_total_risk_pct / Decimal("100.0"))

        if new_total_margin > max_margin:
            logger.warning(
                "Margin limit exceeded: %.2f > %.2f", float(new_total_margin), float(max_margin)
            )
            return False

        return True

    def _calculate_pnl(self, position: Position) -> Decimal:
        """Вычисляет PnL позиции (🚀 ТОЧНОСТЬ DECIMAL)"""
        if position.side == "long":
            return (position.current_price - position.entry_price) * position.quantity
        else:
            return (position.entry_price - position.current_price) * position.quantity

    def update_position_prices(self, price_updates: Dict[str, Union[float, Decimal]]):
        """Обновляет цены позиций"""
        for position in self.positions:
            if position.symbol in price_updates:
                position.current_price = Decimal(str(price_updates[position.symbol]))
                position.unrealized_pnl = self._calculate_pnl(position)

    def get_portfolio_metrics(self) -> PortfolioMetrics:
        """Возвращает метрики портфеля с оптимизированным расчетом"""
        if not self.positions:
            return PortfolioMetrics(
                total_balance=self.balance,
                used_margin=Decimal("0.0"),
                free_margin=self.balance,
                total_risk=Decimal("0.0"),
                total_pnl=Decimal("0.0"),
                positions_count=0,
                max_correlation=Decimal("0.0"),
                portfolio_beta=Decimal("1.0"),
                var_95=Decimal("0.0"),
                sharpe_ratio=Decimal("0.0"),
                sortino_ratio=Decimal("0.0"),
            )

        total_margin = sum(pos.margin_used for pos in self.positions)
        total_pnl = sum(pos.unrealized_pnl for pos in self.positions)

        # Вычисляем максимальную корреляцию
        max_corr = 0.0
        symbols = [pos.symbol for pos in self.positions]
        if len(symbols) >= 2:
            for i, s1 in enumerate(symbols):
                for j in range(i + 1, len(symbols)):
                    s2 = symbols[j]
                    correlation = abs(self.correlation_analyzer.get_correlation(s1, s2))
                    if correlation > max_corr:
                        max_corr = correlation

        # Вычисляем VaR 95%
        var_95 = Decimal(str(self._calculate_var_95()))

        # Вычисляем Sharpe и Sortino ratios
        sharpe_ratio = self._calculate_trade_sharpe()
        sortino_ratio = self._calculate_trade_sortino()

        total_risk = (
            (total_margin / self.balance * Decimal("100.0"))
            if self.balance > 0
            else Decimal("100.0")
        )

        return PortfolioMetrics(
            total_balance=self.balance,
            used_margin=total_margin,
            free_margin=self.balance - total_margin,
            total_risk=total_risk,
            total_pnl=total_pnl,
            positions_count=len(self.positions),
            max_correlation=Decimal(str(max_corr)),
            portfolio_beta=Decimal("1.0"),
            var_95=var_95,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
        )

    def _calculate_var_95(self) -> float:
        """Вычисляет Value at Risk 95%"""
        if not self.performance_history:
            return 0.0

        # Простой VaR на основе исторических данных
        sorted_returns = sorted(self.performance_history)
        var_index = int(len(sorted_returns) * 0.05)  # 5% худших результатов

        return sorted_returns[var_index] if var_index < len(sorted_returns) else sorted_returns[0]

    def _calculate_trade_sharpe(self) -> Decimal:
        """Вычисляет Sharpe ratio на основе истории сделок (Trade-based Sharpe)"""
        if not self.performance_history or len(self.performance_history) < 2:
            return Decimal("0.0")

        try:
            # Используем Decimal для всех расчетов
            returns = [Decimal(str(r)) for r in self.performance_history]
            avg_return = sum(returns) / Decimal(len(returns))

            # Расчет стандартного отклонения через Decimal
            variance = sum((r - avg_return) ** 2 for r in returns) / Decimal(len(returns) - 1)
            std_return = Decimal(str(variance)).sqrt()

            if std_return == 0:
                return Decimal("0.0")

            # Для Trade Sharpe обычно не используют аннуализацию,
            # но мы можем добавить коэффициент sqrt(среднее_колво_сделок_в_год)
            return avg_return / std_return
        except Exception as e:
            logger.error(f"❌ Ошибка расчета Trade Sharpe: {e}")
            return Decimal("0.0")

    def _calculate_trade_sortino(self) -> Decimal:
        """Вычисляет Sortino ratio на основе истории сделок (Downside risk only)"""
        if not self.performance_history or len(self.performance_history) < 2:
            return Decimal("0.0")

        try:
            returns = [Decimal(str(r)) for r in self.performance_history]
            avg_return = sum(returns) / Decimal(len(returns))

            # Только отрицательные результаты для Downside Deviation
            downside_returns = [r for r in returns if r < 0]
            if not downside_returns:
                return Decimal("100.0")  # Идеальный результат без убытков

            downside_variance = sum(r**2 for r in downside_returns) / Decimal(len(returns))
            downside_std = Decimal(str(downside_variance)).sqrt()

            if downside_std == 0:
                return Decimal("0.0")

            return avg_return / downside_std
        except Exception as e:
            logger.error(f"❌ Ошибка расчета Trade Sortino: {e}")
            return Decimal("0.0")

    def check_margin_call_risk(self) -> Dict[str, Any]:
        """Проверяет риск маржин-колла"""

        metrics = self.get_portfolio_metrics()

        # Вычисляем уровень маржи
        margin_level = (
            metrics.free_margin / metrics.used_margin if metrics.used_margin > 0 else float("inf")
        )
        margin_level_pct = (metrics.used_margin / metrics.total_balance) * 100

        # Проверяем приближение к маржин-коллу
        is_at_risk = margin_level_pct >= (self.risk_limits.margin_call_threshold * 100)

        # Рекомендации по действиям
        recommendations = []

        if is_at_risk:
            recommendations.append("Close some positions to reduce margin usage")
            recommendations.append("Consider reducing position sizes")

        if self.current_drawdown > self.risk_limits.max_drawdown_pct:
            recommendations.append("Drawdown exceeds limit - consider risk reduction")

        return {
            "margin_level": margin_level,
            "margin_level_pct": margin_level_pct,
            "is_at_risk": is_at_risk,
            "current_drawdown": self.current_drawdown,
            "recommendations": recommendations,
        }

    def get_risk_report(self) -> Dict[str, Any]:
        """Возвращает отчет о рисках"""

        metrics = self.get_portfolio_metrics()
        margin_risk = self.check_margin_call_risk()

        return {
            "timestamp": get_utc_now().isoformat(),
            "portfolio_metrics": {
                "total_balance": float(metrics.total_balance),
                "used_margin": float(metrics.used_margin),
                "free_margin": float(metrics.free_margin),
                "total_risk_pct": float(metrics.total_risk),
                "total_pnl": float(metrics.total_pnl),
                "positions_count": metrics.positions_count,
                "max_correlation": float(metrics.max_correlation),
                "var_95": float(metrics.var_95),
                "sharpe_ratio": float(metrics.sharpe_ratio),
                "sortino_ratio": float(metrics.sortino_ratio),
            },
            "risk_limits": {
                "max_position_size_pct": self.risk_limits.max_position_size_pct,
                "max_total_risk_pct": self.risk_limits.max_total_risk_pct,
                "max_correlation": self.risk_limits.max_correlation,
                "max_positions": self.risk_limits.max_positions,
                "max_drawdown_pct": self.risk_limits.max_drawdown_pct,
                "margin_call_threshold": self.risk_limits.margin_call_threshold,
            },
            "margin_call_risk": margin_risk,
            "positions": [
                {
                    "symbol": pos.symbol,
                    "side": pos.side,
                    "quantity": pos.quantity,
                    "entry_price": pos.entry_price,
                    "current_price": pos.current_price,
                    "unrealized_pnl": pos.unrealized_pnl,
                    "margin_used": pos.margin_used,
                }
                for pos in self.positions
            ],
        }

    def calculate_intelligent_position_size(
        self,
        symbol: str,
        entry_price: Union[float, Decimal],
        stop_loss_price: Union[float, Decimal],
        confidence_score: float = 0.5,
        ml_confidence: Optional[float] = None,
        regime: str = "NORMAL",
        win_rate: Optional[float] = None,
        avg_win_loss_ratio: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        🚀 ВЫСШАЯ ТОЧКА УПРАВЛЕНИЯ РИСКОМ
        Вычисляет размер позиции на основе Келли, уверенности и режима рынка.
        Использует РЕАЛЬНУЮ историю из БД если параметры не переданы.
        """
        try:
            # 🆕 ПЫТАЕМСЯ ПОЛУЧИТЬ РЕАЛЬНУЮ СТАТИСТИКУ ИЗ БД
            final_win_rate = win_rate
            final_ratio = avg_win_loss_ratio

            if final_win_rate is None or final_ratio is None:
                try:
                    from src.database.db import Database

                    db = Database(readonly=True)
                    stats = db.get_signal_performance_stats(symbol=symbol, days=30)

                    if stats["total_trades"] < 5:
                        # Если по конкретной монете мало данных, берем общую статистику
                        stats = db.get_signal_performance_stats(days=30)

                    if stats["total_trades"] >= 5:
                        final_win_rate = stats["win_rate"]
                        final_ratio = stats["avg_win_loss_ratio"]
                        logger.info(
                            "📊 [KELLY] Используем статистику из БД для %s: WR=%.2f, Ratio=%.2f",
                            symbol,
                            final_win_rate,
                            final_ratio,
                        )
                except Exception as db_err:
                    logger.debug("⚠️ Не удалось получить статистику из БД для Келли: %s", db_err)

            # Fallback значения если БД недоступна или мало данных
            final_win_rate = final_win_rate or 0.55
            final_ratio = final_ratio or 1.6

            # 1. Базовый расчет по Келли с учетом уверенности
            kelly_info = self.position_sizer.calculate_kelly_position_size(
                balance=self.balance,
                entry_price=entry_price,
                stop_loss_price=stop_loss_price,
                win_rate=final_win_rate,
                avg_win_loss_ratio=final_ratio,
                use_fractional=True,
                kelly_fraction=0.2,  # Консервативный Келли (20%)
                ml_confidence=ml_confidence,
                confidence_score=confidence_score,
            )

            if not kelly_info:
                return {}

            # 2. Применяем множитель режима рынка
            regime_mult = self.regime_multipliers.get(regime, Decimal("1.0"))

            # 3. Корректируем итоговый процент
            final_pos_pct = kelly_info["position_size_pct"] * regime_mult

            # 4. Ограничиваем максимальным лимитом из настроек
            max_pos_pct = self.risk_limits.max_position_size_pct
            final_pos_pct = min(final_pos_pct, max_pos_pct)

            # 5. Если просадка слишком высокая, снижаем риск дополнительно
            if self.current_drawdown > Decimal("10.0"):
                final_pos_pct *= Decimal("0.5")

            # 6. Пересчитываем абсолютные значения
            d_balance = Decimal(str(self.balance))
            d_entry_price = Decimal(str(entry_price))

            margin_used = d_balance * final_pos_pct / Decimal("100")
            position_size = margin_used / d_entry_price if d_entry_price > 0 else Decimal("0")

            # 7. Обновляем информацию в словаре
            kelly_info.update(
                {
                    "position_size": position_size,
                    "margin_used": margin_used,
                    "position_size_pct": final_pos_pct,
                    "regime_multiplier": regime_mult,
                    "current_drawdown": self.current_drawdown,
                    "method": "kelly_intelligent_v2",
                }
            )

            logger.info(
                "🧠 [INTELLIGENT SIZE] %s: conf=%.2f, ml=%.2f, regime=%s → size=%.2f%%",
                symbol,
                confidence_score,
                ml_confidence or 0,
                regime,
                float(final_pos_pct),
            )

            return kelly_info

        except Exception as e:
            logger.error("Ошибка в calculate_intelligent_position_size: %s", e)
            return {}

    def calculate_adaptive_position_size(
        self,
        symbol: str,
        entry_price: Union[float, Decimal],
        stop_loss_price: Union[float, Decimal],
        volatility: Union[float, Decimal] = 0.02,
    ) -> Dict[str, Any]:
        """Вычисляет адаптивный размер позиции"""

        d_entry_price = Decimal(str(entry_price))
        d_stop_loss_price = Decimal(str(stop_loss_price))
        d_volatility = Decimal(str(volatility))

        # Вычисляем адаптивный риск
        adaptive_risk = self.position_sizer.calculate_adaptive_risk(
            self.balance, self.performance_history, d_volatility
        )

        # Вычисляем размер позиции
        position_info = self.position_sizer.calculate_position_size(
            self.balance,
            d_entry_price,
            d_stop_loss_price,
            adaptive_risk,
            self.risk_limits.max_position_size_pct,
        )

        return position_info


# Глобальный экземпляр менеджера рисков
risk_manager = RiskManager()


# Удобные функции для использования в других модулях
def get_portfolio_metrics() -> PortfolioMetrics:
    """Возвращает метрики портфеля"""
    return risk_manager.get_portfolio_metrics()


def check_risk_limits(
    symbol: str, side: str, quantity: Union[float, Decimal], entry_price: Union[float, Decimal]
) -> bool:
    """Проверяет лимиты риска для новой позиции"""
    d_quantity = Decimal(str(quantity))
    d_entry_price = Decimal(str(entry_price))

    position = Position(
        symbol=symbol,
        side=side,
        quantity=d_quantity,
        entry_price=d_entry_price,
        current_price=d_entry_price,
        margin_used=d_quantity * d_entry_price,
    )
    return risk_manager.add_position(position)


def get_risk_report() -> Dict[str, Any]:
    """Возвращает отчет о рисках"""
    return risk_manager.get_risk_report()


def update_balance(new_balance: Union[float, Decimal]):
    """Обновляет баланс"""
    risk_manager.update_balance(new_balance)
