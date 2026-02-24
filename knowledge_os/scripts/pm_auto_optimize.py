#!/usr/bin/env python3
"""
Автоматическая оптимизация параметров на основе данных
Анализирует производительность и автоматически корректирует параметры стратегии
"""

import asyncio
import json
import logging
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from src.shared.utils.datetime_utils import get_utc_now

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from observability.tracing import get_tracer

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class AutoOptimizer:
    """Автоматическая оптимизация параметров стратегии"""

    def __init__(self, db_path: str = "trading.db"):
        self.db_path = db_path
        self.tracer = get_tracer()
        self.optimizations: List[Dict] = []

    async def run_optimization(self) -> Dict:
        """Запускает автоматическую оптимизацию"""
        trace = self.tracer.start(
            agent="auto_optimizer",
            mission="parameter_optimization",
            metadata={"date": get_utc_now().isoformat()},
        )

        try:
            trace.record(step="think", name="optimization_started")

            # 1. Анализ производительности
            performance = await self._analyze_performance(trace)

            # 2. Оптимизация параметров сигналов
            signal_optimizations = await self._optimize_signal_parameters(performance, trace)

            # 3. Оптимизация параметров исполнения
            execution_optimizations = await self._optimize_execution_parameters(performance, trace)

            # 4. Оптимизация риск-менеджмента
            risk_optimizations = await self._optimize_risk_parameters(performance, trace)

            # 5. Генерация рекомендаций
            recommendations = self._generate_optimization_recommendations(
                signal_optimizations, execution_optimizations, risk_optimizations
            )

            result = {
                "date": get_utc_now().isoformat(),
                "performance": performance,
                "optimizations": {
                    "signals": signal_optimizations,
                    "execution": execution_optimizations,
                    "risk": risk_optimizations,
                },
                "recommendations": recommendations,
            }

            trace.record(step="observe", name="optimization_completed")
            trace.finish(status="success")

            return result

        except Exception as e:
            logger.error(f"❌ Ошибка при оптимизации: {e}", exc_info=True)
            trace.record(
                step="observe",
                name="optimization_failed",
                status="error",
                metadata={"error": str(e)},
            )
            trace.finish(status="error")
            return {"error": str(e)}

    async def _analyze_performance(self, trace) -> Dict:
        """Анализирует производительность за последние 7 дней"""
        logger.info("📊 Анализ производительности...")
        trace.record(step="act", name="analyze_performance")

        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row

            since = get_utc_now() - timedelta(days=7)
            cursor = conn.execute(
                """
                SELECT
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN net_pnl_usd > 0 THEN 1 ELSE 0 END) as winning_trades,
                    SUM(net_pnl_usd) as total_pnl,
                    AVG(pnl_percent) as avg_pnl_pct,
                    AVG(CASE WHEN net_pnl_usd > 0 THEN pnl_percent ELSE NULL END) as avg_win_pct,
                    AVG(CASE WHEN net_pnl_usd < 0 THEN pnl_percent ELSE NULL END) as avg_loss_pct
                FROM trades
                WHERE datetime(entry_time) >= datetime(?)
            """,
                (since.isoformat(),),
            )

            row = cursor.fetchone()
            if row:
                total_trades = row["total_trades"] or 0
                winning_trades = row["winning_trades"] or 0
                win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

                performance = {
                    "total_trades_7d": total_trades,
                    "win_rate_pct": round(win_rate, 2),
                    "total_pnl_usd": round(row["total_pnl"] or 0.0, 2),
                    "avg_pnl_pct": round(row["avg_pnl_pct"] or 0.0, 2),
                    "avg_win_pct": round(row["avg_win_pct"] or 0.0, 2),
                    "avg_loss_pct": round(row["avg_loss_pct"] or 0.0, 2),
                    "profit_factor": abs(
                        (row["avg_win_pct"] or 0.0) / (row["avg_loss_pct"] or 1.0)
                    ),
                }

                logger.info(
                    f"✅ Производительность: {total_trades} сделок, win rate {win_rate:.1f}%"
                )
                conn.close()
                return performance
            else:
                conn.close()
                return {"status": "no_data"}

        except Exception as e:
            logger.error(f"❌ Ошибка анализа производительности: {e}")
            return {"error": str(e)}

    async def _optimize_signal_parameters(self, performance: Dict, trace) -> List[Dict]:
        """Оптимизирует параметры генерации сигналов"""
        logger.info("🎯 Оптимизация параметров сигналов...")
        trace.record(step="act", name="optimize_signals")

        optimizations = []

        # Если win rate низкий, увеличиваем строгость фильтров
        if performance.get("win_rate_pct", 0) < 50:
            optimizations.append(
                {
                    "parameter": "direction_confidence_min",
                    "current_value": "3/4",
                    "recommended_value": "4/4",
                    "reason": f"Win rate низкий ({performance.get('win_rate_pct', 0):.1f}%), требуется более строгая фильтрация",
                    "priority": "high",
                }
            )

        # Если profit factor низкий, улучшаем TP/SL соотношение
        if performance.get("profit_factor", 0) < 1.5:
            optimizations.append(
                {
                    "parameter": "tp_sl_ratio",
                    "current_value": "2:1",
                    "recommended_value": "2.5:1",
                    "reason": f"Profit factor низкий ({performance.get('profit_factor', 0):.2f}), улучшаем TP/SL",
                    "priority": "medium",
                }
            )

        return optimizations

    async def _optimize_execution_parameters(self, performance: Dict, trace) -> List[Dict]:
        """Оптимизирует параметры исполнения"""
        logger.info("⚙️ Оптимизация параметров исполнения...")
        trace.record(step="act", name="optimize_execution")

        optimizations = []

        # Анализ timeout rate из order_audit_log
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row

            since = get_utc_now() - timedelta(days=7)
            cursor = conn.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE status = 'timeout') as timeouts,
                    COUNT(*) FILTER (WHERE order_type = 'limit') as total_limits
                FROM order_audit_log
                WHERE datetime(created_at) >= datetime(?)
                  AND order_type = 'limit'
            """,
                (since.isoformat(),),
            )

            row = cursor.fetchone()
            if row:
                timeouts = row["timeouts"] or 0
                total_limits = row["total_limits"] or 0
                timeout_rate = (timeouts / total_limits * 100) if total_limits > 0 else 0

                if timeout_rate > 15:
                    optimizations.append(
                        {
                            "parameter": "limit_order_ttl",
                            "current_value": "45s",
                            "recommended_value": "60s",
                            "reason": f"Timeout rate высокий ({timeout_rate:.1f}%), увеличиваем TTL",
                            "priority": "high",
                        }
                    )

                if timeout_rate > 20:
                    optimizations.append(
                        {
                            "parameter": "limit_price_spread",
                            "current_value": "0.1%",
                            "recommended_value": "0.15%",
                            "reason": f"Timeout rate очень высокий ({timeout_rate:.1f}%), увеличиваем спред",
                            "priority": "high",
                        }
                    )

            conn.close()

        except Exception as e:
            logger.debug(f"⚠️ Ошибка анализа timeout rate: {e}")

        return optimizations

    async def _optimize_risk_parameters(self, performance: Dict, trace) -> List[Dict]:
        """Оптимизирует параметры риск-менеджмента"""
        logger.info("🛡️ Оптимизация параметров риск-менеджмента...")
        trace.record(step="act", name="optimize_risk")

        optimizations = []

        # Если средний убыток большой, уменьшаем размер позиций
        if abs(performance.get("avg_loss_pct", 0)) > 2.0:
            optimizations.append(
                {
                    "parameter": "max_position_size_pct",
                    "current_value": "15%",
                    "recommended_value": "12%",
                    "reason": f"Средний убыток большой ({abs(performance.get('avg_loss_pct', 0)):.2f}%), уменьшаем размер позиций",
                    "priority": "high",
                }
            )

        # Если win rate низкий, уменьшаем риск на сделку
        if performance.get("win_rate_pct", 0) < 50:
            optimizations.append(
                {
                    "parameter": "risk_per_trade_pct",
                    "current_value": "2%",
                    "recommended_value": "1.5%",
                    "reason": f"Win rate низкий ({performance.get('win_rate_pct', 0):.1f}%), уменьшаем риск",
                    "priority": "medium",
                }
            )

        return optimizations

    def _generate_optimization_recommendations(
        self, signal_opt: List[Dict], execution_opt: List[Dict], risk_opt: List[Dict]
    ) -> List[Dict]:
        """Генерирует рекомендации по оптимизации"""
        all_optimizations = signal_opt + execution_opt + risk_opt

        # Сортируем по приоритету
        high_priority = [opt for opt in all_optimizations if opt.get("priority") == "high"]
        medium_priority = [opt for opt in all_optimizations if opt.get("priority") == "medium"]

        recommendations = []

        if high_priority:
            recommendations.append(
                {
                    "priority": "high",
                    "message": f"Найдено {len(high_priority)} критических оптимизаций",
                    "actions": high_priority,
                }
            )

        if medium_priority:
            recommendations.append(
                {
                    "priority": "medium",
                    "message": f"Найдено {len(medium_priority)} рекомендуемых оптимизаций",
                    "actions": medium_priority,
                }
            )

        return recommendations

    def save_optimizations(self, result: Dict, output_path: Optional[Path] = None) -> Path:
        """Сохраняет результаты оптимизации"""
        if output_path is None:
            output_path = (
                PROJECT_ROOT
                / "docs"
                / "project_management"
                / "optimizations"
                / f"optimization_{get_utc_now().strftime('%Y%m%d')}.json"
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ Результаты оптимизации сохранены: {output_path}")
        return output_path

    def print_summary(self, result: Dict) -> None:
        """Выводит краткую сводку оптимизации"""
        print("\n" + "=" * 60)
        print("🔧 АВТОМАТИЧЕСКАЯ ОПТИМИЗАЦИЯ")
        print("=" * 60)

        if "performance" in result:
            perf = result["performance"]
            print("📊 ПРОИЗВОДИТЕЛЬНОСТЬ (7 дней):")
            print(f"  • Сделок: {perf.get('total_trades_7d', 0)}")
            print(f"  • Win rate: {perf.get('win_rate_pct', 0):.1f}%")
            print(f"  • Profit factor: {perf.get('profit_factor', 0):.2f}")
            print()

        if "optimizations" in result:
            opt = result["optimizations"]
            total = (
                len(opt.get("signals", []))
                + len(opt.get("execution", []))
                + len(opt.get("risk", []))
            )
            print(f"💡 НАЙДЕНО ОПТИМИЗАЦИЙ: {total}")
            print()

            if opt.get("signals"):
                print("🎯 СИГНАЛЫ:")
                for o in opt["signals"]:
                    print(f"  • {o['parameter']}: {o['current_value']} → {o['recommended_value']}")
                print()

            if opt.get("execution"):
                print("⚙️ ИСПОЛНЕНИЕ:")
                for o in opt["execution"]:
                    print(f"  • {o['parameter']}: {o['current_value']} → {o['recommended_value']}")
                print()

            if opt.get("risk"):
                print("🛡️ РИСК-МЕНЕДЖМЕНТ:")
                for o in opt["risk"]:
                    print(f"  • {o['parameter']}: {o['current_value']} → {o['recommended_value']}")
                print()

        print("=" * 60 + "\n")


async def main():
    """Главная функция"""
    optimizer = AutoOptimizer()
    result = await optimizer.run_optimization()
    optimizer.save_optimizations(result)
    optimizer.print_summary(result)
    return result


if __name__ == "__main__":
    asyncio.run(main())
