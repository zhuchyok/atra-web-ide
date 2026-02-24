#!/usr/bin/env python3
"""
🤖 AI ОПТИМИЗАТОР ФИЛЬТРОВ
Автоматически оптимизирует параметры фильтров на основе результатов торговли
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

import numpy as np

from src.shared.utils.datetime_utils import get_utc_now

try:
    from db import Database
except ImportError:
    Database = None

logger = logging.getLogger(__name__)


class AIFilterOptimizer:
    """Оптимизирует параметры фильтров на основе исторических результатов"""

    def __init__(self):
        self.db = None  # ❌ НЕ создаем Database() при __init__!
        self.optimization_interval_hours = 6  # Оптимизация каждые 6 часов
        self.min_trades_for_optimization = 20  # Минимум сделок для оптимизации
        self.lookback_days = 7  # Анализ последних 7 дней

        # Параметры для оптимизации
        self.optimizable_params = {
            # Пороги оценки сигналов
            "soft_score_threshold": {"min": 45, "max": 70, "current": 50},
            "strict_score_threshold": {"min": 50, "max": 75, "current": 55},
            # ADX пороги
            "soft_adx_bb_threshold": {"min": 18, "max": 28, "current": 20},
            "strict_adx_bb_threshold": {"min": 22, "max": 30, "current": 24},
            "soft_adx_entry": {"min": 15, "max": 26, "current": 18},
            "strict_adx_entry": {"min": 18, "max": 28, "current": 21},
            # BB epsilon
            "soft_bb_epsilon": {"min": 0.07, "max": 0.15, "current": 0.11},
            "strict_bb_epsilon": {"min": 0.04, "max": 0.10, "current": 0.07},
            # MTF score (новый параметр)
            "soft_mtf_min": {"min": 50, "max": 75, "current": 60},
            "strict_mtf_min": {"min": 60, "max": 85, "current": 70},
            # Volume ratio (новый параметр)
            "soft_volume_ratio": {"min": 1.1, "max": 1.8, "current": 1.3},
            "strict_volume_ratio": {"min": 1.2, "max": 2.0, "current": 1.5},
            # Confluence (новый параметр)
            "soft_confluence": {"min": 2, "max": 4, "current": 3},
            "strict_confluence": {"min": 3, "max": 5, "current": 4},
            # Volatility range (новый параметр)
            "soft_vol_min": {"min": 0.01, "max": 0.025, "current": 0.015},
            "soft_vol_max": {"min": 0.06, "max": 0.12, "current": 0.08},
            "strict_vol_min": {"min": 0.015, "max": 0.03, "current": 0.02},
            "strict_vol_max": {"min": 0.04, "max": 0.10, "current": 0.06},
        }

        logger.info("🤖 AI оптимизатор фильтров инициализирован")

    async def get_recent_performance(self) -> Dict[str, Any]:
        """Получает метрики производительности за последние дни"""
        # Lazy initialization Database только при первом использовании
        if self.db is None and Database:
            self.db = Database()

        if not self.db:
            return self._get_default_metrics()

        try:
            # Получаем закрытые сделки за последние N дней
            # Нужны только result и net_profit для расчета метрик
            query = """
                SELECT
                    result,
                    net_profit
                FROM signals_log
                WHERE
                    created_at >= datetime('now', ?)
                    AND result IN ('TP1', 'TP2', 'SL', 'TP1_PARTIAL', 'TP2_REACHED', 'SL_BE', 'STOP')
                    AND net_profit IS NOT NULL
                ORDER BY created_at DESC
            """

            # Используем conn.execute напрямую
            with self.db.get_lock():
                cursor = self.db.conn.execute(query, (f"-{self.lookback_days} days",))
                trades = cursor.fetchall()

            if not trades or len(trades) < self.min_trades_for_optimization:
                logger.warning(
                    f"⚠️ Недостаточно сделок для оптимизации: {len(trades) if trades else 0}"
                )
                return self._get_default_metrics()

            # Рассчитываем метрики
            wins = [t for t in trades if t[0] in ("TP1", "TP2", "TP1_PARTIAL", "TP2_REACHED")]
            losses = [t for t in trades if t[0] in ("SL", "SL_BE", "STOP")]

            total_profit = sum(t[1] for t in trades if t[1] is not None)
            total_win_profit = sum(t[1] for t in wins if t[1] is not None and t[1] > 0)
            total_loss_profit = abs(sum(t[1] for t in losses if t[1] is not None and t[1] < 0))

            win_rate = len(wins) / len(trades) if trades else 0
            profit_factor = total_win_profit / total_loss_profit if total_loss_profit > 0 else 0

            # Рассчитываем просадку
            cumulative_pnl = []
            running_pnl = 0
            for trade in reversed(trades):
                if trade[1] is not None:
                    running_pnl += trade[1]
                    cumulative_pnl.append(running_pnl)

            max_drawdown = 0
            if cumulative_pnl:
                peak = cumulative_pnl[0]
                for pnl in cumulative_pnl:
                    if pnl > peak:
                        peak = pnl
                    drawdown = (peak - pnl) / abs(peak) if peak != 0 else 0
                    max_drawdown = max(max_drawdown, drawdown)

            # Sharpe ratio (упрощенный)
            returns = [t[1] for t in trades if t[1] is not None]
            sharpe = 0
            if returns:
                mean_return = np.mean(returns)
                std_return = np.std(returns)
                sharpe = mean_return / std_return if std_return > 0 else 0

            metrics = {
                "trades_count": len(trades),
                "win_rate": win_rate,
                "profit_factor": profit_factor,
                "max_drawdown": max_drawdown,
                "sharpe_ratio": sharpe,
                "total_profit": total_profit,
                "avg_profit_per_trade": total_profit / len(trades) if trades else 0,
            }

            logger.info(
                f"📊 Метрики: WR={win_rate:.1%}, PF={profit_factor:.2f}, DD={max_drawdown:.1%}"
            )
            return metrics

        except Exception as e:
            logger.error(f"❌ Ошибка получения метрик: {e}")
            return self._get_default_metrics()

    def _get_default_metrics(self) -> Dict[str, Any]:
        """Возвращает дефолтные метрики"""
        return {
            "trades_count": 0,
            "win_rate": 0.6,
            "profit_factor": 1.5,
            "max_drawdown": 0.1,
            "sharpe_ratio": 1.0,
            "total_profit": 0,
            "avg_profit_per_trade": 0,
        }

    def calculate_optimization_score(self, metrics: Dict[str, Any]) -> float:
        """Рассчитывает общую оценку производительности (0-1)"""
        win_rate_score = metrics["win_rate"]
        pf_score = min(1.0, metrics["profit_factor"] / 3.0)
        dd_score = max(0, 1.0 - metrics["max_drawdown"])
        sharpe_score = min(1.0, max(0, metrics["sharpe_ratio"] / 2.0))

        # Взвешенная оценка
        score = win_rate_score * 0.3 + pf_score * 0.3 + dd_score * 0.2 + sharpe_score * 0.2

        return score

    def optimize_ml_filter_thresholds(self, current_metrics: Dict[str, Any]) -> Dict[str, float]:
        """
        Оптимизирует пороги ML фильтра на основе текущей производительности.
        Фокус на балансе между точностью (Precision) и частотой сигналов.
        """
        # Базовые пороги
        thresholds = {
            "min_success_prob": 0.45,
            "min_expected_profit": 0.35,
            "min_combined_score": 0.20,
        }

        win_rate = current_metrics.get("win_rate", 0.6)
        trades_count = current_metrics.get("trades_count", 0)

        # Если Win Rate низкий (<60%) -> Ужесточаем ML фильтры
        if win_rate < 0.60:
            thresholds["min_success_prob"] += 0.10
            thresholds["min_expected_profit"] += 0.15
            thresholds["min_combined_score"] += 0.10
            logger.info("🔒 [ML_OPT] WR низкий (%.1f%%) -> Ужесточаем ML фильтры", win_rate * 100)

        # Если Win Rate очень высокий (>80%) и мало сделок -> Ослабляем
        elif win_rate > 0.80 and trades_count < 15:
            thresholds["min_success_prob"] -= 0.05
            thresholds["min_expected_profit"] -= 0.10
            thresholds["min_combined_score"] -= 0.05
            logger.info(
                "🔓 [ML_OPT] WR высокий (%.1f%%), мало сделок -> Ослабляем ML фильтры",
                win_rate * 100,
            )

        # Ограничиваем разумными пределами
        thresholds["min_success_prob"] = max(0.3, min(0.7, thresholds["min_success_prob"]))
        thresholds["min_expected_profit"] = max(0.1, min(1.0, thresholds["min_expected_profit"]))
        thresholds["min_combined_score"] = max(0.05, min(0.5, thresholds["min_combined_score"]))

        return thresholds

    async def get_rejection_stats(self, hours: int = 24) -> Dict[str, int]:
        """Получает статистику отклоненных сигналов"""
        if self.db is None and Database:
            self.db = Database()

        if not self.db:
            return {}

        try:
            query = """
                SELECT filter_name, COUNT(*)
                FROM rejected_signals
                WHERE created_at >= datetime('now', ?)
                GROUP BY filter_name
            """
            # Используем fetch_all_optimized из db.py (он там уже интегрирован в execute_with_retry)
            rows = await self.db.execute_with_retry_async(
                query, (f"-{hours} hours",), is_write=False
            )

            stats = {row[0]: row[1] for row in rows} if rows else {}
            if stats:
                total = sum(stats.values())
                logger.info("🚫 Статистика отклонений (24ч): %s (Всего: %d)", stats, total)
            return stats
        except Exception as e:
            logger.error("❌ Ошибка получения статистики отклонений: %s", e)
            return {}

    async def optimize_parameters(self) -> Dict[str, Any]:
        """Оптимизирует параметры фильтров на основе текущей производительности"""
        logger.info("🔄 Начинаем оптимизацию параметров фильтров...")

        # Получаем текущие метрики и статистику отклонений
        metrics = await self.get_recent_performance()
        rejection_stats = await self.get_rejection_stats()

        if metrics["trades_count"] < self.min_trades_for_optimization:
            logger.warning(
                "⚠️ Недостаточно данных для оптимизации (%d сделок)", metrics["trades_count"]
            )
            return self._get_current_params()

        # Рассчитываем текущую оценку
        current_score = self.calculate_optimization_score(metrics)
        logger.info("📊 Текущая оценка системы: %.2f%%", current_score * 100)

        # Определяем направление оптимизации
        optimized_params = self._adjust_parameters_based_on_metrics(
            metrics, rejection_stats, current_score
        )

        # Сохраняем оптимизированные параметры
        await self._save_optimized_params(optimized_params, metrics)

        logger.info("✅ Оптимизация завершена!")
        return optimized_params

    def _adjust_parameters_based_on_metrics(
        self, metrics: Dict[str, Any], rejection_stats: Dict[str, int], current_score: float
    ) -> Dict[str, Any]:
        """Корректирует параметры на основе метрик и отклонений"""
        adjusted = {}

        # Базовый коэффициент корректировки
        win_rate = metrics["win_rate"]
        trades_count = metrics["trades_count"]

        if win_rate < 0.65:
            logger.info("📉 Win Rate низкий (%.1f%%) → ужесточаем фильтры", win_rate * 100)
            adjust_factor = 1.05
        elif win_rate > 0.80 and trades_count < 30:
            logger.info(
                "📈 Win Rate высокий (%.1f%%), мало сделок → ослабляем фильтры", win_rate * 100
            )
            adjust_factor = 0.95
        elif current_score > 0.75:
            logger.info("✅ Система работает отлично → минимальная корректировка")
            adjust_factor = 1.01
        else:
            logger.info("⚖️ Средняя производительность → стандартная корректировка")
            adjust_factor = 1.02

        total_rejections = sum(rejection_stats.values()) if rejection_stats else 0

        # Корректируем каждый параметр
        for param_name, param_config in self.optimizable_params.items():
            current = param_config["current"]
            min_val = param_config["min"]
            max_val = param_config["max"]

            # Локальный коэффициент для конкретного параметра
            local_factor = adjust_factor

            # Если конкретный фильтр отклоняет слишком много при хорошем WR -> ослабляем его сильнее
            if total_rejections > 50 and win_rate > 0.70:
                # Маппинг параметров на фильтры (упрощенный)
                filter_key = None
                if "volume" in param_name:
                    filter_key = "volume_profile"
                elif "bb_epsilon" in param_name:
                    filter_key = "bollinger"

                if filter_key and rejection_stats.get(filter_key, 0) / total_rejections > 0.3:
                    logger.info(
                        "🔓 Фильтр '%s' слишком строгий (>30%% откл) → ослабляем сильнее",
                        filter_key,
                    )
                    local_factor *= 0.9  # Дополнительное ослабление

            # Применяем корректировку
            if any(
                k in param_name
                for k in ["score_threshold", "adx", "mtf", "confluence", "volume_ratio"]
            ):
                new_value = current * local_factor
            elif "bb_epsilon" in param_name or "vol_max" in param_name:
                new_value = current / local_factor
            elif "vol_min" in param_name:
                new_value = current * local_factor
            else:
                new_value = current

            # Ограничиваем диапазон
            new_value = max(min_val, min(max_val, new_value))
            if "confluence" in param_name:
                new_value = int(round(new_value))

            adjusted[param_name] = round(new_value, 4)

        return adjusted

    def _get_current_params(self) -> Dict[str, Any]:
        """Возвращает текущие параметры"""
        return {name: config["current"] for name, config in self.optimizable_params.items()}

    async def _save_optimized_params(self, params: Dict[str, Any], metrics: Dict[str, Any]):
        """Сохраняет оптимизированные параметры"""
        try:
            data = {
                "timestamp": get_utc_now().isoformat(),
                "parameters": params,
                "metrics": metrics,
                "optimization_score": self.calculate_optimization_score(metrics),
            }

            # Сохраняем в JSON
            with open("ai_learning_data/filter_parameters.json", "w") as f:
                json.dump(data, f, indent=4)

            # Обновляем текущие значения в памяти
            for param_name, value in params.items():
                if param_name in self.optimizable_params:
                    self.optimizable_params[param_name]["current"] = value

            logger.info("💾 Параметры сохранены в filter_parameters.json")

        except Exception as e:
            logger.error(f"❌ Ошибка сохранения параметров: {e}")

    def load_optimized_params(self) -> Dict[str, Any]:
        """Загружает оптимизированные параметры из файла"""
        try:
            with open("ai_learning_data/filter_parameters.json") as f:
                data = json.load(f)

            params = data.get("parameters", {})
            timestamp = data.get("timestamp", "unknown")

            logger.info(f"📂 Загружены параметры от {timestamp}")
            return params

        except FileNotFoundError:
            logger.info("📂 Файл параметров не найден, используем дефолтные")
            return self._get_current_params()
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки параметров: {e}")
            return self._get_current_params()

    async def start_auto_optimization(self):
        """Запускает автоматическую оптимизацию каждые N часов"""
        logger.info(
            f"🚀 Запуск автоматической оптимизации (каждые {self.optimization_interval_hours}ч)"
        )

        while True:
            try:
                await asyncio.sleep(self.optimization_interval_hours * 3600)

                logger.info("⏰ Начинаем плановую оптимизацию...")
                await self.optimize_parameters()

            except Exception as e:
                logger.error(f"❌ Ошибка в автоматической оптимизации: {e}")
                await asyncio.sleep(3600)  # Повтор через час при ошибке


# Singleton instance
_optimizer_instance = None


def get_filter_optimizer():
    """Возвращает singleton экземпляр оптимизатора"""
    global _optimizer_instance
    if _optimizer_instance is None:
        _optimizer_instance = AIFilterOptimizer()
    return _optimizer_instance


if __name__ == "__main__":
    # Тестирование оптимизатора
    logging.basicConfig(level=logging.INFO)

    async def test():
        optimizer = AIFilterOptimizer()

        print("📊 Получаем текущие метрики...")
        metrics = await optimizer.get_recent_performance()
        print(f"Metrics: {metrics}")

        print("\n🔄 Запускаем оптимизацию...")
        optimized = await optimizer.optimize_parameters()
        print("\nОптимизированные параметры:")
        for name, value in optimized.items():
            print(f"  {name}: {value}")

    asyncio.run(test())
