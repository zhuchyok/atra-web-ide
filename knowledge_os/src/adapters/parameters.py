#!/usr/bin/env python3
"""
Адаптивный контроллер параметров с AI-регулированием
"""

import asyncio
import json
import logging
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

# Временно отключены - модули не найдены в новой структуре
try:
    from src.ai.adaptive_filter_regulator import get_adaptive_regulator
    from src.ai.filter_optimizer import get_filter_optimizer
except ImportError:
    get_filter_optimizer = None
    get_adaptive_regulator = None


# Заглушки для совместимости (удалены старые заглушки)
@dataclass
class TradeResult:
    symbol: str = ""
    pattern_type: str = ""
    signal_type: str = ""
    entry_price: float = 0.0
    entry_time: float = 0.0
    exit_price: Optional[float] = None
    exit_time: Optional[float] = None
    is_winner: bool = False
    pnl_pct: float = 0.0
    duration_hours: Optional[float] = None
    ai_score: float = 0.0
    volume_usd: float = 0.0
    volatility_pct: float = 0.0
    market_regime: str = "UNKNOWN"
    composite_score: float = 0.0
    composite_confidence: float = 0.0


class PatternEffectivenessAnalyzer:
    def __init__(self):
        self.pattern_stats = {}
        self.trade_results = []

    def add_trade_result(self, trade):
        pass

    def save_data(self):
        pass

    def print_effectiveness_report(self):
        pass


class ParameterOptimizer:
    def __init__(self, analyzer):
        self.analyzer = analyzer
        self.optimization_history = []

    def should_optimize(self):
        return False

    def optimize_parameters(self):
        return None

    def apply_parameters(self, params):
        return True

    def get_current_parameters(self):
        return {}

    def print_optimization_report(self):
        pass


logger = logging.getLogger(__name__)


@dataclass
class SystemPerformanceMetrics:
    """Метрики производительности системы"""

    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl_pct: float = 0.0
    winrate: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    avg_trade_duration_hours: float = 0.0
    signals_per_hour: float = 0.0
    last_updated: float = 0.0


@dataclass
class AIRegulatorState:
    """Состояние AI-регулятора"""

    is_active: bool = True
    learning_mode: bool = True  # Режим обучения (только сбор данных)
    optimization_enabled: bool = False
    last_optimization_time: float = 0.0
    optimization_interval_hours: float = 6.0
    min_trades_for_optimization: int = 50
    max_daily_parameter_change: float = 0.15
    emergency_rollback_enabled: bool = True
    performance_degradation_threshold: float = 0.05  # 5% ухудшение


class AdaptiveParameterController:
    """
    Основной AI-регулятор параметров торговой системы

    Функции:
    - Сбор и анализ статистики торговых паттернов
    - Автоматическая оптимизация параметров фильтров
    - Адаптация к изменяющимся рыночным условиям
    - Защита от деградации производительности
    """

    def __init__(
        self,
        state_file: str = "ai_learning_data/ai_regulator_state.json",
        enable_optimization: bool = False,
    ):
        self.state_file = state_file
        self.state = AIRegulatorState()
        self.analyzer = PatternEffectivenessAnalyzer()
        self.optimizer = ParameterOptimizer(self.analyzer)

        # Метрики производительности
        self.current_performance = SystemPerformanceMetrics()
        self.baseline_performance = SystemPerformanceMetrics()
        self.performance_history: List[SystemPerformanceMetrics] = []

        # Управление состоянием
        self.pending_trades: Dict[str, TradeResult] = {}  # Открытые сделки
        self.completed_trades_buffer: List[TradeResult] = []

        # Загружаем состояние
        self.load_state()

        # Устанавливаем режим работы
        if enable_optimization:
            self.enable_optimization_mode()

        logger.info("🧠 AI-регулятор параметров инициализирован")
        logger.info(
            "  📊 Режим обучения: %s", "✅ Включен" if self.state.learning_mode else "❌ Отключен"
        )
        logger.info(
            "  🔧 Оптимизация: %s",
            "✅ Включена" if self.state.optimization_enabled else "❌ Отключена",
        )

    def enable_optimization_mode(self):
        """Включает режим оптимизации (после периода обучения)"""
        self.state.learning_mode = False
        self.state.optimization_enabled = True
        logger.info("🔧 Включен режим оптимизации параметров")

    def disable_optimization_mode(self):
        """Отключает оптимизацию (возврат к режиму обучения)"""
        self.state.optimization_enabled = False
        self.state.learning_mode = True
        logger.info("📚 Возврат к режиму обучения")

    async def start_continuous_optimization(self):
        """
        🆕 НОВОЕ: Запускает непрерывную оптимизацию параметров

        Логика:
        1. Проверка каждые 1 час
        2. Использование AIFilterOptimizer для реальных расчетов
        3. Автоматическое обновление параметров
        """
        logger.info("🚀 Запуск continuous AI optimization")

        optimizer = get_filter_optimizer()
        if not optimizer:
            logger.error("❌ AIFilterOptimizer не найден, оптимизация невозможна")
            return

        while True:
            try:
                await asyncio.sleep(3600)  # Каждый час

                # 1. Запускаем реальную оптимизацию через AIFilterOptimizer
                logger.info("⏰ Запуск ежечасной AI оптимизации...")
                optimized_params = await optimizer.optimize_parameters()

                if optimized_params:
                    logger.info("✅ AI оптимизация завершена, новые параметры получены")

                    # 🆕 СВЯЗКА: Уведомляем AdaptiveFilterRegulator о новых параметрах
                    if get_adaptive_regulator:
                        try:
                            regulator = get_adaptive_regulator()
                            # Передаем метрики для обновления внутренних состояний
                            metrics = await optimizer.get_recent_performance()
                            await regulator.update_from_ai_optimization(metrics=metrics)
                            logger.info(
                                "🧠 Живой регулятор фильтров обновлен новыми параметрами ИИ"
                            )
                        except Exception as reg_err:
                            logger.error("❌ Ошибка уведомления регулятора: %s", reg_err)

                    # Обновляем метрики в текущем объекте для отчетов
                    if not metrics:  # Если еще не получили выше
                        metrics = await optimizer.get_recent_performance()
                    if metrics:
                        self.current_performance = SystemPerformanceMetrics(
                            total_trades=metrics.get("trades_count", 0),
                            winrate=metrics.get("win_rate", 0),
                            profit_factor=metrics.get("profit_factor", 0),
                            total_pnl_pct=metrics.get("total_profit", 0),
                            last_updated=time.time(),
                        )

            except asyncio.CancelledError:
                logger.info("🛑 Continuous optimization остановлен")
                break
            except Exception as e:
                logger.error("❌ Ошибка в continuous optimization: %s", e)
                await asyncio.sleep(60)

    async def process_signal_generation(
        self,
        symbol: str,
        pattern_type: str,
        signal_type: str,
        signal_price: float,
        df: Any = None,
        ai_score: float = 0.0,
        market_regime: str = "UNKNOWN",
        composite_score: float = 0.0,
        composite_confidence: float = 0.0,
        volume_usd: float = 0.0,
        volatility_pct: float = 0.0,
    ) -> str:
        """
        Обрабатывает генерацию сигнала и создает запись для отслеживания

        Returns:
            trade_id: Уникальный ID сделки для последующего отслеживания
        """
        trade_id = f"{symbol}_{int(time.time())}_{signal_type}"

        trade = TradeResult(
            symbol=symbol,
            pattern_type=pattern_type,
            signal_type=signal_type,
            entry_price=signal_price,
            entry_time=time.time(),
            ai_score=ai_score,
            volume_usd=volume_usd,
            volatility_pct=volatility_pct,
            market_regime=market_regime,
            composite_score=composite_score,
            composite_confidence=composite_confidence,
        )

        # Добавляем в буфер ожидающих сделок
        self.pending_trades[trade_id] = trade

        logger.debug("📊 Зарегистрирован сигнал: %s %s (ID: %s)", symbol, signal_type, trade_id)

        return trade_id

    async def process_trade_completion(
        self, trade_id: str, exit_price: float, is_winner: bool, pnl_pct: Optional[float] = None
    ) -> bool:
        """
        Обрабатывает завершение сделки и обновляет статистику

        Returns:
            bool: True если сделка успешно обработана
        """
        if trade_id not in self.pending_trades:
            logger.warning("⚠️ Неизвестный trade_id: %s", trade_id)
            return False

        trade = self.pending_trades[trade_id]

        # Завершаем сделку
        trade.exit_price = exit_price
        trade.exit_time = time.time()
        trade.is_winner = is_winner

        # Рассчитываем PnL если не предоставлен
        if pnl_pct is None:
            if trade.signal_type == "LONG":
                pnl_pct = ((exit_price - trade.entry_price) / trade.entry_price) * 100
            else:  # SHORT
                pnl_pct = ((trade.entry_price - exit_price) / trade.entry_price) * 100

        trade.pnl_pct = pnl_pct

        # Рассчитываем продолжительность
        if trade.exit_time and trade.entry_time:
            trade.duration_hours = (trade.exit_time - trade.entry_time) / 3600

        # Добавляем в анализатор
        self.analyzer.add_trade_result(trade)

        # Добавляем в буфер завершенных сделок
        self.completed_trades_buffer.append(trade)

        # Удаляем из ожидающих
        del self.pending_trades[trade_id]

        logger.info(
            "✅ Завершена сделка %s: %s %.2f%% за %.1f ч",
            trade_id,
            "WIN" if is_winner else "LOSS",
            pnl_pct,
            trade.duration_hours or 0,
        )

        # Обновляем метрики производительности
        await self._update_performance_metrics()

        # Проверяем необходимость оптимизации
        if self.state.optimization_enabled:
            await self._check_optimization_trigger()

        return True

    async def _update_performance_metrics(self):
        """Обновляет метрики производительности системы"""
        # Получаем статистику из анализатора
        all_patterns_stats = list(self.analyzer.pattern_stats.values())

        if not all_patterns_stats:
            return

        # Агрегируем метрики
        total_trades = sum(stats.total_trades for stats in all_patterns_stats)
        winning_trades = sum(stats.winning_trades for stats in all_patterns_stats)
        total_pnl = sum(stats.total_pnl_pct for stats in all_patterns_stats)

        self.current_performance = SystemPerformanceMetrics(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=total_trades - winning_trades,
            total_pnl_pct=total_pnl,
            winrate=winning_trades / total_trades if total_trades > 0 else 0.0,
            last_updated=time.time(),
        )

        # Рассчитываем profit factor
        total_wins = sum(stats.avg_win_pct * stats.winning_trades for stats in all_patterns_stats)
        total_losses = sum(stats.avg_loss_pct * stats.losing_trades for stats in all_patterns_stats)
        self.current_performance.profit_factor = (
            total_wins / total_losses if total_losses > 0 else float("inf")
        )

        # Рассчитываем среднюю продолжительность
        duration_trades = [
            stats.avg_duration_hours for stats in all_patterns_stats if stats.avg_duration_hours > 0
        ]
        if duration_trades:
            self.current_performance.avg_trade_duration_hours = sum(duration_trades) / len(
                duration_trades
            )

        # Сохраняем в историю (каждые 100 сделок)
        if total_trades > 0 and total_trades % 100 == 0:
            self.performance_history.append(self.current_performance)

            # Ограничиваем историю
            if len(self.performance_history) > 50:
                self.performance_history = self.performance_history[-50:]

        logger.debug(
            "📊 Обновлены метрики: %d сделок, WR=%.1f%%, PF=%.2f",
            total_trades,
            self.current_performance.winrate * 100,
            self.current_performance.profit_factor,
        )

    async def _check_optimization_trigger(self) -> bool:
        """Проверяет необходимость запуска оптимизации"""
        current_time = time.time()

        # Проверяем временной интервал
        time_since_last = (current_time - self.state.last_optimization_time) / 3600
        if time_since_last < self.state.optimization_interval_hours:
            return False

        # Проверяем минимальное количество сделок
        if self.current_performance.total_trades < self.state.min_trades_for_optimization:
            logger.debug(
                "🔧 Недостаточно сделок для оптимизации: %d < %d",
                self.current_performance.total_trades,
                self.state.min_trades_for_optimization,
            )
            return False

        # Проверяем деградацию производительности
        if self._detect_performance_degradation():
            logger.warning("⚠️ Обнаружена деградация производительности, запускаем оптимизацию")
            await self._run_optimization()
            return True

        # Регулярная оптимизация
        if self.optimizer.should_optimize():
            logger.info("🔧 Запуск регулярной оптимизации параметров")
            await self._run_optimization()
            return True

        return False

    def _detect_performance_degradation(self) -> bool:
        """Обнаруживает деградацию производительности"""
        if len(self.performance_history) < 2:
            return False

        # Сравниваем текущую производительность с базовой
        if not self.baseline_performance.total_trades:
            # Устанавливаем базовую производительность
            self.baseline_performance = self.performance_history[0]
            return False

        current_pf = self.current_performance.profit_factor
        baseline_pf = self.baseline_performance.profit_factor

        current_wr = self.current_performance.winrate
        baseline_wr = self.baseline_performance.winrate

        # Проверяем значительное ухудшение
        pf_degradation = (baseline_pf - current_pf) / baseline_pf if baseline_pf > 0 else 0
        wr_degradation = (baseline_wr - current_wr) / baseline_wr if baseline_wr > 0 else 0

        if (
            pf_degradation > self.state.performance_degradation_threshold
            or wr_degradation > self.state.performance_degradation_threshold
        ):
            return True

        return False

    async def _run_optimization(self):
        """Запускает процесс оптимизации параметров"""
        try:
            logger.info("🔧 Начинаем оптимизацию параметров...")

            # Запускаем оптимизацию
            optimization_result = self.optimizer.optimize_parameters()

            if optimization_result and optimization_result.validation_passed:
                # Применяем новые параметры
                success = self.optimizer.apply_parameters(optimization_result.new_parameters)

                if success:
                    self.state.last_optimization_time = time.time()

                    # Обновляем базовую производительность при успешной оптимизации
                    if optimization_result.expected_improvement > 0.05:  # Значительное улучшение
                        self.baseline_performance = self.current_performance

                    logger.info(
                        "✅ Оптимизация завершена успешно: %.1f%% улучшение",
                        optimization_result.expected_improvement * 100,
                    )

                    # Сохраняем состояние
                    await self.save_state()
                else:
                    logger.error("❌ Ошибка применения оптимизированных параметров")
            else:
                logger.info("ℹ️ Оптимизация не нашла значимых улучшений")

        except Exception as e:
            logger.error("❌ Ошибка в процессе оптимизации: %s", e)

    def get_current_parameters(self) -> Dict[str, float]:
        """Получает текущие параметры системы"""
        return self.optimizer.get_current_parameters()

    def get_performance_summary(self) -> Dict[str, Any]:
        """Получает сводку производительности"""
        return {
            "current_performance": asdict(self.current_performance),
            "baseline_performance": asdict(self.baseline_performance),
            "total_optimizations": len(self.optimizer.optimization_history),
            "pending_trades": len(self.pending_trades),
            "analyzer_patterns": len(self.analyzer.pattern_stats),
            "state": asdict(self.state),
        }

    async def emergency_rollback(self) -> bool:
        """Экстренный откат параметров при критической деградации"""
        if not self.state.emergency_rollback_enabled:
            return False

        try:
            logger.warning("🚨 ЭКСТРЕННЫЙ ОТКАТ ПАРАМЕТРОВ")

            # Находим последнюю успешную оптимизацию
            successful_optimizations = [
                opt
                for opt in self.optimizer.optimization_history
                if opt.validation_passed and opt.expected_improvement > 0
            ]

            if successful_optimizations:
                # Откатываемся к параметрам последней успешной оптимизации
                last_good_opt = successful_optimizations[-1]
                rollback_params = last_good_opt.old_parameters

                success = self.optimizer.apply_parameters(rollback_params)
                if success:
                    logger.info(
                        "✅ Откат выполнен к параметрам от %s",
                        time.strftime(
                            "%Y-%m-%d %H:%M", time.localtime(last_good_opt.optimization_time)
                        ),
                    )
                    return True

            # Если нет успешных оптимизаций, возвращаемся к дефолтным параметрам
            default_params = {
                "soft_score_threshold": 25.0,
                "strict_score_threshold": 35.0,
                "min_volume_usd": 5_000_000,
                "volume_ratio_threshold": 1.2,
                "min_volatility_pct": 0.005,
                "max_volatility_pct": 0.15,
                "min_quality_score": 0.70,
                "min_pattern_confidence": 0.60,
            }

            success = self.optimizer.apply_parameters(default_params)
            if success:
                logger.info("✅ Откат выполнен к дефолтным параметрам")
                return True

        except Exception as e:
            logger.error("❌ Ошибка экстренного отката: %s", e)

        return False

    async def save_state(self):
        """Сохраняет состояние регулятора"""
        try:
            import os

            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)

            state_data = {
                "regulator_state": asdict(self.state),
                "current_performance": asdict(self.current_performance),
                "baseline_performance": asdict(self.baseline_performance),
                "performance_history": [asdict(perf) for perf in self.performance_history[-10:]],
                "current_parameters": self.get_current_parameters(),
                "last_saved": time.time(),
            }

            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(state_data, f, indent=2, ensure_ascii=False)

            # Также сохраняем данные анализатора
            self.analyzer.save_data()

            logger.debug("💾 Состояние AI-регулятора сохранено")

        except Exception as e:
            logger.error("❌ Ошибка сохранения состояния: %s", e)

    def load_state(self):
        """Загружает состояние регулятора"""
        try:
            with open(self.state_file, encoding="utf-8") as f:
                state_data = json.load(f)

            # Восстанавливаем состояние
            if "regulator_state" in state_data:
                self.state = AIRegulatorState(**state_data["regulator_state"])

            if "current_performance" in state_data:
                self.current_performance = SystemPerformanceMetrics(
                    **state_data["current_performance"]
                )

            if "baseline_performance" in state_data:
                self.baseline_performance = SystemPerformanceMetrics(
                    **state_data["baseline_performance"]
                )

            if "performance_history" in state_data:
                self.performance_history = [
                    SystemPerformanceMetrics(**perf) for perf in state_data["performance_history"]
                ]

            # Восстанавливаем параметры
            if "current_parameters" in state_data:
                self.optimizer.apply_parameters(state_data["current_parameters"])

            logger.info("📊 Состояние AI-регулятора загружено")

        except FileNotFoundError:
            logger.info("📊 Файл состояния не найден, начинаем с чистого состояния")
        except Exception as e:
            logger.error("❌ Ошибка загрузки состояния: %s", e)

    async def print_ai_regulator_report(self):
        """Выводит подробный отчет о работе AI-регулятора"""
        logger.info("🧠 AI PARAMETER REGULATOR REPORT")
        logger.info("=" * 50)

        # Состояние системы
        logger.info("📊 СОСТОЯНИЕ СИСТЕМЫ:")
        logger.info(
            "  🔧 Режим оптимизации: %s",
            "✅ Активен" if self.state.optimization_enabled else "❌ Отключен",
        )
        logger.info(
            "  📚 Режим обучения: %s", "✅ Активен" if self.state.learning_mode else "❌ Отключен"
        )
        logger.info(
            "  ⏰ Последняя оптимизация: %s",
            time.strftime("%Y-%m-%d %H:%M", time.localtime(self.state.last_optimization_time))
            if self.state.last_optimization_time
            else "Никогда",
        )

        # Производительность
        logger.info("📈 ПРОИЗВОДИТЕЛЬНОСТЬ:")
        logger.info("  📊 Всего сделок: %d", self.current_performance.total_trades)
        logger.info(
            "  🎯 Winrate: %.1f%% (%d/%d)",
            self.current_performance.winrate * 100,
            self.current_performance.winning_trades,
            self.current_performance.total_trades,
        )
        logger.info("  💰 Profit Factor: %.2f", self.current_performance.profit_factor)
        logger.info("  📊 Total PnL: %.2f%%", self.current_performance.total_pnl_pct)
        logger.info(
            "  ⏱️ Avg Duration: %.1f hours", self.current_performance.avg_trade_duration_hours
        )

        # Сравнение с базовой производительностью
        if self.baseline_performance.total_trades > 0:
            logger.info("📊 СРАВНЕНИЕ С БАЗОВОЙ ПРОИЗВОДИТЕЛЬНОСТЬЮ:")
            wr_change = (
                (
                    (self.current_performance.winrate - self.baseline_performance.winrate)
                    / self.baseline_performance.winrate
                    * 100
                )
                if self.baseline_performance.winrate > 0
                else 0
            )
            pf_change = (
                (
                    (
                        self.current_performance.profit_factor
                        - self.baseline_performance.profit_factor
                    )
                    / self.baseline_performance.profit_factor
                    * 100
                )
                if self.baseline_performance.profit_factor > 0
                else 0
            )

            logger.info("  🎯 Winrate: %+.1f%% изменение", wr_change)
            logger.info("  💰 Profit Factor: %+.1f%% изменение", pf_change)

        # Текущие параметры
        logger.info("🎛️ ТЕКУЩИЕ ПАРАМЕТРЫ:")
        current_params = self.get_current_parameters()
        for param_name, value in current_params.items():
            logger.info("  • %s: %.3f", param_name, value)

        # Статистика оптимизации
        self.optimizer.print_optimization_report()

        # Статистика паттернов
        self.analyzer.print_effectiveness_report()

        logger.info("=" * 50)

    async def cleanup_old_data(self, max_age_days: int = 30):
        """Очищает старые данные"""
        cutoff_time = time.time() - (max_age_days * 24 * 3600)

        # Очищаем старые результаты сделок
        old_count = len(self.analyzer.trade_results)
        self.analyzer.trade_results = [
            trade for trade in self.analyzer.trade_results if trade.entry_time > cutoff_time
        ]
        new_count = len(self.analyzer.trade_results)

        if old_count != new_count:
            logger.info(
                "🧹 Очищены старые данные: удалено %d сделок старше %d дней",
                old_count - new_count,
                max_age_days,
            )

            # Пересчитываем статистику паттернов
            for pattern in self.analyzer.pattern_stats.keys():
                self.analyzer._recalculate_pattern_metrics(pattern)

    def apply_regime_adjustments(
        self, base_params: Dict[str, Any], regime: str, regime_confidence: float
    ) -> Dict[str, Any]:
        """
        Применяет коррекции параметров на основе рыночного режима

        Args:
            base_params: Базовые параметры
            regime: Название режима (BULL_TREND, BEAR_TREND и т.д.)
            regime_confidence: Уверенность в режиме (0-1)

        Returns:
            Скорректированные параметры
        """
        try:
            adjusted_params = base_params.copy()

            # Множители для порогов score в зависимости от режима
            regime_threshold_multipliers = {
                "BULL_TREND": 0.90,  # -10% (смягчаем фильтры)
                "BEAR_TREND": 1.15,  # +15% (ужесточаем фильтры)
                "HIGH_VOL_RANGE": 1.10,  # +10% (осторожнее)
                "LOW_VOL_RANGE": 0.95,  # -5% (чуть смягчаем)
                "CRASH": 1.50,  # +50% (очень строго!)
            }

            threshold_mult = regime_threshold_multipliers.get(regime, 1.0)

            # Применяем с учетом confidence
            effective_mult = 1.0 + (threshold_mult - 1.0) * regime_confidence

            # Корректируем пороги
            if "soft_score_threshold" in adjusted_params:
                adjusted_params["soft_score_threshold"] *= effective_mult
            if "strict_score_threshold" in adjusted_params:
                adjusted_params["strict_score_threshold"] *= effective_mult

            logger.debug(
                "🎛️ Режим %s (%.0f%%): пороги скорректированы на x%.2f",
                regime,
                regime_confidence * 100,
                effective_mult,
            )

            return adjusted_params

        except Exception as e:
            logger.error("❌ Ошибка применения режимных коррекций: %s", e)
            return base_params


# Глобальный экземпляр AI-регулятора
ai_regulator: Optional[AdaptiveParameterController] = None


def get_ai_regulator(enable_optimization: bool = False) -> AdaptiveParameterController:
    """Получает глобальный экземпляр AI-регулятора"""
    global ai_regulator

    if ai_regulator is None:
        ai_regulator = AdaptiveParameterController(enable_optimization=enable_optimization)

    return ai_regulator
