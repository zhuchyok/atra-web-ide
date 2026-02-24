#!/usr/bin/env python3
"""
Оптимизатор параметров на основе анализа эффективности паттернов
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np
from pattern_effectiveness_analyzer import PatternEffectivenessAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class ParameterRange:
    """Диапазон значений параметра для оптимизации"""

    min_value: float
    max_value: float
    current_value: float
    step_size: float
    parameter_type: str  # "threshold", "ratio", "percentage"


@dataclass
class OptimizationResult:
    """Результат оптимизации параметров"""

    old_parameters: Dict[str, float]
    new_parameters: Dict[str, float]
    expected_improvement: float
    confidence_score: float
    optimization_time: float
    validation_passed: bool
    reason: str


class ParameterOptimizer:
    """Оптимизатор параметров торговой системы на основе ML-подходов"""

    def __init__(self, analyzer: PatternEffectivenessAnalyzer):
        self.analyzer = analyzer
        self.parameter_ranges = self._initialize_parameter_ranges()
        self.optimization_history: List[OptimizationResult] = []
        self.last_optimization_time = 0.0
        self.min_optimization_interval = 3600  # 1 час между оптимизациями

    def _initialize_parameter_ranges(self) -> Dict[str, ParameterRange]:
        """Инициализирует диапазоны параметров для оптимизации"""
        return {
            # Пороги AI-скора
            "soft_score_threshold": ParameterRange(
                min_value=10.0,
                max_value=60.0,
                current_value=25.0,
                step_size=2.5,
                parameter_type="threshold",
            ),
            "strict_score_threshold": ParameterRange(
                min_value=20.0,
                max_value=80.0,
                current_value=35.0,
                step_size=2.5,
                parameter_type="threshold",
            ),
            # Объемные фильтры
            "min_volume_usd": ParameterRange(
                min_value=1_000_000,
                max_value=20_000_000,
                current_value=5_000_000,
                step_size=500_000,
                parameter_type="threshold",
            ),
            "volume_ratio_threshold": ParameterRange(
                min_value=0.8,
                max_value=2.0,
                current_value=1.2,
                step_size=0.1,
                parameter_type="ratio",
            ),
            # Фильтры волатильности
            "min_volatility_pct": ParameterRange(
                min_value=0.001,
                max_value=0.02,
                current_value=0.005,
                step_size=0.001,
                parameter_type="percentage",
            ),
            "max_volatility_pct": ParameterRange(
                min_value=0.05,
                max_value=0.30,
                current_value=0.15,
                step_size=0.02,
                parameter_type="percentage",
            ),
            # Качественные фильтры
            "min_quality_score": ParameterRange(
                min_value=0.5,
                max_value=0.95,
                current_value=0.70,
                step_size=0.05,
                parameter_type="ratio",
            ),
            "min_pattern_confidence": ParameterRange(
                min_value=0.3,
                max_value=0.9,
                current_value=0.60,
                step_size=0.05,
                parameter_type="ratio",
            ),
        }

    def should_optimize(self) -> bool:
        """Определяет, нужно ли запускать оптимизацию"""
        current_time = time.time()

        # Проверяем временной интервал
        if current_time - self.last_optimization_time < self.min_optimization_interval:
            return False

        # Проверяем наличие достаточных данных
        total_trades = sum(stats.total_trades for stats in self.analyzer.pattern_stats.values())
        if total_trades < 50:  # Минимум для оптимизации
            logger.debug("🔧 Недостаточно сделок для оптимизации: %d < 50", total_trades)
            return False

        # Проверяем, есть ли паттерны с плохой производительностью
        poor_patterns = self._identify_poor_performing_patterns()
        if poor_patterns:
            logger.info("🔧 Обнаружены неэффективные паттерны: %s", poor_patterns)
            return True

        # Проверяем общую производительность системы
        overall_performance = self._calculate_overall_performance()
        if overall_performance["profit_factor"] < 1.1 or overall_performance["winrate"] < 0.55:
            logger.info(
                "🔧 Общая производительность требует оптимизации: PF=%.2f, WR=%.1f%%",
                overall_performance["profit_factor"],
                overall_performance["winrate"] * 100,
            )
            return True

        return False

    def _identify_poor_performing_patterns(self) -> List[str]:
        """Выявляет паттерны с плохой производительностью"""
        poor_patterns = []

        for pattern, stats in self.analyzer.pattern_stats.items():
            if stats.total_trades >= 10:  # Достаточно данных для оценки
                if stats.profit_factor < 1.0 or stats.winrate < 0.45 or stats.sharpe_ratio < -0.5:
                    poor_patterns.append(pattern)

        return poor_patterns

    def _calculate_overall_performance(self) -> Dict[str, float]:
        """Рассчитывает общую производительность системы"""
        all_trades = []
        total_pnl = 0.0
        winning_trades = 0

        for stats in self.analyzer.pattern_stats.values():
            if stats.total_trades > 0:
                all_trades.extend([stats] * stats.total_trades)
                total_pnl += stats.total_pnl_pct
                winning_trades += stats.winning_trades

        if not all_trades:
            return {"profit_factor": 0.0, "winrate": 0.0, "total_pnl": 0.0}

        total_trades_count = len(all_trades)
        winrate = winning_trades / total_trades_count if total_trades_count > 0 else 0.0

        # Упрощенный расчет profit factor
        total_wins = sum(
            stats.avg_win_pct * stats.winning_trades
            for stats in self.analyzer.pattern_stats.values()
        )
        total_losses = sum(
            stats.avg_loss_pct * stats.losing_trades
            for stats in self.analyzer.pattern_stats.values()
        )
        profit_factor = total_wins / total_losses if total_losses > 0 else float("inf")

        return {"profit_factor": profit_factor, "winrate": winrate, "total_pnl": total_pnl}

    def optimize_parameters(self) -> Optional[OptimizationResult]:
        """Выполняет оптимизацию параметров"""
        start_time = time.time()
        logger.info("🔧 Начинаем оптимизацию параметров...")

        try:
            # Получаем текущие параметры
            current_params = {
                name: param_range.current_value
                for name, param_range in self.parameter_ranges.items()
            }

            # Анализируем корреляции между параметрами и производительностью
            correlations = self._analyze_parameter_correlations()

            # Генерируем кандидатов для оптимизации
            optimization_candidates = self._generate_optimization_candidates(correlations)

            # Выбираем лучшего кандидата
            best_candidate = self._select_best_candidate(optimization_candidates)

            if not best_candidate:
                logger.info("🔧 Оптимизация не нашла улучшений")
                return None

            # Валидируем улучшение
            validation_passed = self._validate_improvement(best_candidate)

            optimization_time = time.time() - start_time
            self.last_optimization_time = time.time()

            result = OptimizationResult(
                old_parameters=current_params.copy(),
                new_parameters=best_candidate["parameters"],
                expected_improvement=best_candidate["expected_improvement"],
                confidence_score=best_candidate["confidence"],
                optimization_time=optimization_time,
                validation_passed=validation_passed,
                reason=best_candidate["reason"],
            )

            self.optimization_history.append(result)

            logger.info(
                "🔧 Оптимизация завершена за %.2f сек. Ожидаемое улучшение: %.1f%%",
                optimization_time,
                best_candidate["expected_improvement"] * 100,
            )

            return result

        except Exception as e:
            logger.error("❌ Ошибка оптимизации параметров: %s", e)
            return None

    def _analyze_parameter_correlations(self) -> Dict[str, Dict[str, float]]:
        """Анализирует корреляции между параметрами и производительностью"""
        correlations = {}

        # Для каждого параметра анализируем его влияние на производительность
        for param_name, _ in self.parameter_ranges.items():
            correlations[param_name] = {
                "performance_correlation": 0.0,
                "frequency_impact": 0.0,
                "quality_impact": 0.0,
                "confidence": 0.0,
            }

            # Анализируем исторические данные оптимизации
            if len(self.optimization_history) >= 3:
                param_changes = []
                performance_changes = []

                for i in range(1, len(self.optimization_history)):
                    prev_opt = self.optimization_history[i - 1]
                    curr_opt = self.optimization_history[i]

                    if (
                        param_name in prev_opt.new_parameters
                        and param_name in curr_opt.old_parameters
                    ):
                        param_change = (
                            curr_opt.old_parameters[param_name]
                            - prev_opt.new_parameters[param_name]
                        )
                        performance_change = curr_opt.expected_improvement

                        param_changes.append(param_change)
                        performance_changes.append(performance_change)

                # Рассчитываем корреляцию
                if len(param_changes) >= 3:
                    correlation = np.corrcoef(param_changes, performance_changes)[0, 1]
                    correlations[param_name]["performance_correlation"] = (
                        correlation if not np.isnan(correlation) else 0.0
                    )
                    correlations[param_name]["confidence"] = min(len(param_changes) / 10.0, 1.0)

        return correlations

    def _generate_optimization_candidates(
        self, correlations: Dict[str, Dict[str, float]]
    ) -> List[Dict[str, Any]]:
        """Генерирует кандидатов для оптимизации"""
        candidates = []

        # Стратегия 1: Повышение порогов для плохих паттернов
        poor_patterns = self._identify_poor_performing_patterns()
        if poor_patterns:
            candidate = self._create_threshold_increase_candidate(poor_patterns)
            if candidate:
                candidates.append(candidate)

        # Стратегия 2: Снижение порогов для хороших паттернов
        good_patterns = self._identify_good_performing_patterns()
        if good_patterns:
            candidate = self._create_threshold_decrease_candidate(good_patterns)
            if candidate:
                candidates.append(candidate)

        # Стратегия 3: Оптимизация на основе корреляций
        for param_name, corr_data in correlations.items():
            if corr_data["confidence"] > 0.5:
                candidate = self._create_correlation_based_candidate(param_name, corr_data)
                if candidate:
                    candidates.append(candidate)

        # Стратегия 4: Адаптация к режиму рынка
        market_regime_candidate = self._create_market_regime_candidate()
        if market_regime_candidate:
            candidates.append(market_regime_candidate)

        return candidates

    def _identify_good_performing_patterns(self) -> List[str]:
        """Выявляет хорошо работающие паттерны"""
        good_patterns = []

        for pattern, stats in self.analyzer.pattern_stats.items():
            if stats.total_trades >= 10:
                if stats.profit_factor > 1.3 and stats.winrate > 0.60 and stats.sharpe_ratio > 0.5:
                    good_patterns.append(pattern)

        return good_patterns

    def _create_threshold_increase_candidate(
        self, poor_patterns: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Создает кандидата с повышением порогов для плохих паттернов"""
        new_params = {
            name: param_range.current_value for name, param_range in self.parameter_ranges.items()
        }

        # Повышаем пороги, чтобы отфильтровать плохие сигналы
        adjustments_made = 0

        if "soft_score_threshold" in new_params:
            old_value = new_params["soft_score_threshold"]
            new_value = min(
                old_value + 5.0, self.parameter_ranges["soft_score_threshold"].max_value
            )
            if new_value != old_value:
                new_params["soft_score_threshold"] = new_value
                adjustments_made += 1

        if "min_volume_usd" in new_params:
            old_value = new_params["min_volume_usd"]
            new_value = min(old_value * 1.2, self.parameter_ranges["min_volume_usd"].max_value)
            if new_value != old_value:
                new_params["min_volume_usd"] = new_value
                adjustments_made += 1

        if adjustments_made == 0:
            return None

        # Оцениваем ожидаемое улучшение
        expected_improvement = len(poor_patterns) * 0.05  # 5% за каждый плохой паттерн

        return {
            "parameters": new_params,
            "expected_improvement": expected_improvement,
            "confidence": 0.7,
            "reason": f"Повышение порогов для фильтрации {len(poor_patterns)} неэффективных паттернов",
        }

    def _create_threshold_decrease_candidate(
        self, good_patterns: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Создает кандидата со снижением порогов для хороших паттернов"""
        new_params = {
            name: param_range.current_value for name, param_range in self.parameter_ranges.items()
        }

        # Снижаем пороги, чтобы получить больше хороших сигналов
        adjustments_made = 0

        if "soft_score_threshold" in new_params:
            old_value = new_params["soft_score_threshold"]
            new_value = max(
                old_value - 3.0, self.parameter_ranges["soft_score_threshold"].min_value
            )
            if new_value != old_value:
                new_params["soft_score_threshold"] = new_value
                adjustments_made += 1

        if "min_volatility_pct" in new_params:
            old_value = new_params["min_volatility_pct"]
            new_value = max(old_value * 0.8, self.parameter_ranges["min_volatility_pct"].min_value)
            if new_value != old_value:
                new_params["min_volatility_pct"] = new_value
                adjustments_made += 1

        if adjustments_made == 0:
            return None

        # Оцениваем ожидаемое улучшение
        expected_improvement = len(good_patterns) * 0.03  # 3% за каждый хороший паттерн

        return {
            "parameters": new_params,
            "expected_improvement": expected_improvement,
            "confidence": 0.8,
            "reason": f"Снижение порогов для увеличения частоты {len(good_patterns)} эффективных паттернов",
        }

    def _create_correlation_based_candidate(
        self, param_name: str, corr_data: Dict[str, float]
    ) -> Optional[Dict[str, Any]]:
        """Создает кандидата на основе корреляционного анализа"""
        new_params = {
            name: param_range.current_value for name, param_range in self.parameter_ranges.items()
        }

        param_range = self.parameter_ranges[param_name]
        correlation = corr_data["performance_correlation"]

        # Определяем направление изменения
        if correlation > 0.3:  # Положительная корреляция
            new_value = min(
                param_range.current_value + param_range.step_size, param_range.max_value
            )
        elif correlation < -0.3:  # Отрицательная корреляция
            new_value = max(
                param_range.current_value - param_range.step_size, param_range.min_value
            )
        else:
            return None  # Слабая корреляция

        if new_value == param_range.current_value:
            return None  # Нет изменений

        new_params[param_name] = new_value

        expected_improvement = abs(correlation) * corr_data["confidence"] * 0.1

        return {
            "parameters": new_params,
            "expected_improvement": expected_improvement,
            "confidence": corr_data["confidence"],
            "reason": f"Корреляционная оптимизация {param_name} (корр: {correlation:.2f})",
        }

    def _create_market_regime_candidate(self) -> Optional[Dict[str, Any]]:
        """Создает кандидата для адаптации к текущему режиму рынка"""
        # Анализируем производительность по режимам рынка
        regime_performance = {}

        for _, stats in self.analyzer.pattern_stats.items():
            if stats.market_regime_performance:
                for regime, winrate in stats.market_regime_performance.items():
                    if regime not in regime_performance:
                        regime_performance[regime] = []
                    regime_performance[regime].append(winrate)

        if not regime_performance:
            return None

        # Определяем доминирующий режим
        avg_performance = {
            regime: np.mean(winrates) for regime, winrates in regime_performance.items()
        }

        best_regime = max(avg_performance, key=avg_performance.get)
        worst_regime = min(avg_performance, key=avg_performance.get)

        new_params = {
            name: param_range.current_value for name, param_range in self.parameter_ranges.items()
        }

        # Адаптируем параметры под лучший режим
        if best_regime == "TREND":
            # В трендовом рынке можем быть менее строгими к волатильности
            new_params["max_volatility_pct"] = min(
                new_params["max_volatility_pct"] * 1.1,
                self.parameter_ranges["max_volatility_pct"].max_value,
            )
        elif best_regime == "RANGE":
            # В боковом рынке нужна большая точность
            new_params["soft_score_threshold"] = min(
                new_params["soft_score_threshold"] + 2.0,
                self.parameter_ranges["soft_score_threshold"].max_value,
            )

        expected_improvement = (avg_performance[best_regime] - avg_performance[worst_regime]) * 0.5

        return {
            "parameters": new_params,
            "expected_improvement": expected_improvement,
            "confidence": 0.6,
            "reason": f"Адаптация к режиму рынка {best_regime} (производительность: {avg_performance[best_regime]:.1%})",
        }

    def _select_best_candidate(self, candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Выбирает лучшего кандидата из списка"""
        if not candidates:
            return None

        # Сортируем по ожидаемому улучшению с учетом уверенности
        scored_candidates = []
        for candidate in candidates:
            score = candidate["expected_improvement"] * candidate["confidence"]
            scored_candidates.append((score, candidate))

        scored_candidates.sort(key=lambda x: x[0], reverse=True)

        # Возвращаем лучшего кандидата, если улучшение значимо
        best_score, best_candidate = scored_candidates[0]
        if best_score > 0.02:  # Минимальное улучшение 2%
            return best_candidate

        return None

    def _validate_improvement(self, candidate: Dict[str, Any]) -> bool:
        """Валидирует ожидаемое улучшение"""
        # Простая валидация: проверяем, что параметры в допустимых диапазонах
        for param_name, new_value in candidate["parameters"].items():
            if param_name in self.parameter_ranges:
                param_range = self.parameter_ranges[param_name]
                if not (param_range.min_value <= new_value <= param_range.max_value):
                    logger.warning(
                        "🔧 Параметр %s вне допустимого диапазона: %.3f", param_name, new_value
                    )
                    return False

        # Проверяем, что изменения не слишком радикальные
        for param_name, new_value in candidate["parameters"].items():
            if param_name in self.parameter_ranges:
                current_value = self.parameter_ranges[param_name].current_value
                change_pct = (
                    abs(new_value - current_value) / current_value if current_value != 0 else 0
                )

                if change_pct > 0.3:  # Максимальное изменение 30%
                    logger.warning(
                        "🔧 Слишком большое изменение параметра %s: %.1f%%",
                        param_name,
                        change_pct * 100,
                    )
                    return False

        return True

    def apply_parameters(self, new_parameters: Dict[str, float]) -> bool:
        """Применяет новые параметры"""
        try:
            for param_name, new_value in new_parameters.items():
                if param_name in self.parameter_ranges:
                    self.parameter_ranges[param_name].current_value = new_value
                    logger.info("🔧 Обновлен параметр %s: %.3f", param_name, new_value)

            logger.info("✅ Применены новые параметры: %d изменений", len(new_parameters))
            return True

        except Exception as e:
            logger.error("❌ Ошибка применения параметров: %s", e)
            return False

    def get_current_parameters(self) -> Dict[str, float]:
        """Получает текущие параметры"""
        return {
            name: param_range.current_value for name, param_range in self.parameter_ranges.items()
        }

    def print_optimization_report(self):
        """Выводит отчет об оптимизации"""
        if not self.optimization_history:
            logger.info("📊 История оптимизации пуста")
            return

        logger.info("🔧 ОТЧЕТ ОБ ОПТИМИЗАЦИИ ПАРАМЕТРОВ:")
        logger.info("  📈 Всего оптимизаций: %d", len(self.optimization_history))

        successful_optimizations = [
            opt for opt in self.optimization_history if opt.validation_passed
        ]
        if successful_optimizations:
            avg_improvement = np.mean(
                [opt.expected_improvement for opt in successful_optimizations]
            )
            logger.info(
                "  ✅ Успешных оптимизаций: %d (среднее улучшение: %.1f%%)",
                len(successful_optimizations),
                avg_improvement * 100,
            )

        # Последняя оптимизация
        last_opt = self.optimization_history[-1]
        logger.info("  🕒 Последняя оптимизация:")
        logger.info("    • Время: %.2f сек", last_opt.optimization_time)
        logger.info("    • Улучшение: %.1f%%", last_opt.expected_improvement * 100)
        logger.info("    • Уверенность: %.1f%%", last_opt.confidence_score * 100)
        logger.info("    • Причина: %s", last_opt.reason)
        logger.info(
            "    • Валидация: %s", "✅ Пройдена" if last_opt.validation_passed else "❌ Не пройдена"
        )

        # Текущие параметры
        logger.info("  🎛️ Текущие параметры:")
        for param_name, param_range in self.parameter_ranges.items():
            logger.info(
                "    • %s: %.3f (диапазон: %.3f - %.3f)",
                param_name,
                param_range.current_value,
                param_range.min_value,
                param_range.max_value,
            )
