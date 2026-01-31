#!/usr/bin/env python3
"""
Ежедневная автоматическая проверка проекта PM
Проверяет метрики, качество кода, производительность и генерирует отчёт
"""

import asyncio
import json
import logging
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Добавляем корень проекта в путь
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from observability.tracing import get_tracer
from order_audit_log import get_audit_log

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ProjectManager:
    """Автоматизированный PM для управления проектом"""
    
    def __init__(self, db_path: str = "trading.db"):
        self.db_path = db_path
        self.tracer = get_tracer()
        self.audit_log = get_audit_log()
        self.report: Dict = {
            "date": datetime.utcnow().isoformat(),
            "metrics": {},
            "issues": [],
            "recommendations": [],
            "status": "unknown"
        }
    
    async def run_daily_check(self) -> Dict:
        """Запускает полную ежедневную проверку"""
        trace = self.tracer.start(
            agent="project_manager",
            mission="daily_check",
            metadata={"date": self.report["date"]}
        )
        
        try:
            trace.record(step="think", name="check_started")
            
            # 1. Финансовые метрики
            await self._check_financial_metrics(trace)
            
            # 2. Операционные метрики
            await self._check_operational_metrics(trace)
            
            # 3. Качество кода
            await self._check_code_quality(trace)
            
            # 4. Риски и проблемы
            await self._check_risks(trace)
            
            # 5. Генерация рекомендаций
            await self._generate_recommendations(trace)
            
            # 6. Определение общего статуса
            self._determine_status()
            
            trace.record(step="observe", name="check_completed", metadata={"status": self.report["status"]})
            trace.finish(status="success")
            
            return self.report
            
        except Exception as e:
            logger.error(f"❌ Ошибка при выполнении ежедневной проверки: {e}", exc_info=True)
            trace.record(step="observe", name="check_failed", status="error", metadata={"error": str(e)})
            trace.finish(status="error", metadata={"error": str(e)})
            self.report["status"] = "error"
            self.report["error"] = str(e)
            return self.report
    
    async def _check_financial_metrics(self, trace) -> None:
        """Проверяет финансовые метрики"""
        logger.info("📊 Проверка финансовых метрик...")
        trace.record(step="act", name="check_financial_metrics")
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            
            # Получаем сделки за последние 24 часа
            since = datetime.utcnow() - timedelta(hours=24)
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN net_pnl_usd > 0 THEN 1 ELSE 0 END) as winning_trades,
                    SUM(net_pnl_usd) as total_pnl,
                    AVG(net_pnl_usd) as avg_pnl,
                    AVG(pnl_percent) as avg_pnl_pct
                FROM trades
                WHERE datetime(entry_time) >= datetime(?)
            """, (since.isoformat(),))
            
            row = cursor.fetchone()
            if row:
                total_trades = row['total_trades'] or 0
                winning_trades = row['winning_trades'] or 0
                total_pnl = row['total_pnl'] or 0.0
                avg_pnl = row['avg_pnl'] or 0.0
                avg_pnl_pct = row['avg_pnl_pct'] or 0.0
                
                win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
                
                self.report["metrics"]["financial"] = {
                    "total_trades_24h": total_trades,
                    "winning_trades": winning_trades,
                    "win_rate_pct": round(win_rate, 2),
                    "total_pnl_usd": round(total_pnl, 2),
                    "avg_pnl_usd": round(avg_pnl, 2),
                    "avg_pnl_pct": round(avg_pnl_pct, 2)
                }
                
                # Проверка целевых значений
                if win_rate < 55:
                    self.report["issues"].append({
                        "type": "financial",
                        "severity": "medium",
                        "message": f"Win rate ниже целевого: {win_rate:.1f}% < 55%",
                        "recommendation": "Проанализировать фильтры сигналов, улучшить качество входа"
                    })
                
                if avg_pnl_pct < 1.5:
                    self.report["issues"].append({
                        "type": "financial",
                        "severity": "medium",
                        "message": f"Средняя прибыль ниже целевой: {avg_pnl_pct:.2f}% < 1.5%",
                        "recommendation": "Оптимизировать TP уровни, улучшить тайминг выхода"
                    })
                
                logger.info(f"✅ Финансовые метрики: {total_trades} сделок, win rate {win_rate:.1f}%, PnL {total_pnl:.2f} USD")
            else:
                logger.warning("⚠️ Нет данных о сделках за последние 24 часа")
                self.report["metrics"]["financial"] = {"status": "no_data"}
            
            conn.close()
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки финансовых метрик: {e}")
            self.report["issues"].append({
                "type": "system",
                "severity": "high",
                "message": f"Ошибка проверки финансовых метрик: {e}"
            })
    
    async def _check_operational_metrics(self, trace) -> None:
        """Проверяет операционные метрики"""
        logger.info("⚙️ Проверка операционных метрик...")
        trace.record(step="act", name="check_operational_metrics")
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            
            # Проверка качества исполнения ордеров
            since = datetime.utcnow() - timedelta(hours=24)
            cursor = conn.execute("""
                SELECT 
                    order_type,
                    status,
                    COUNT(*) as count
                FROM order_audit_log
                WHERE datetime(created_at) >= datetime(?)
                  AND order_type IN ('limit', 'market')
                GROUP BY order_type, status
            """, (since.isoformat(),))
            
            orders = cursor.fetchall()
            limit_created = 0
            limit_filled = 0
            limit_timeout = 0
            market_filled = 0
            
            for row in orders:
                if row['order_type'] == 'limit':
                    if row['status'] == 'created':
                        limit_created += row['count']
                    elif row['status'] == 'filled':
                        limit_filled += row['count']
                    elif row['status'] == 'timeout':
                        limit_timeout += row['count']
                elif row['order_type'] == 'market' and row['status'] == 'filled':
                    market_filled += row['count']
            
            total_limit = limit_created
            limit_fill_rate = (limit_filled / total_limit * 100) if total_limit > 0 else 0
            timeout_rate = (limit_timeout / total_limit * 100) if total_limit > 0 else 0
            market_fallback_rate = (market_filled / total_limit * 100) if total_limit > 0 else 0
            
            self.report["metrics"]["operational"] = {
                "limit_orders_created": limit_created,
                "limit_orders_filled": limit_filled,
                "limit_fill_rate_pct": round(limit_fill_rate, 2),
                "limit_timeout_rate_pct": round(timeout_rate, 2),
                "market_fallback_rate_pct": round(market_fallback_rate, 2)
            }
            
            # Проверка целевых значений
            if limit_fill_rate < 90:
                self.report["issues"].append({
                    "type": "operational",
                    "severity": "medium",
                    "message": f"Fill rate лимитов ниже целевого: {limit_fill_rate:.1f}% < 90%",
                    "recommendation": "Оптимизировать цены лимитов, увеличить TTL"
                })
            
            if timeout_rate > 10:
                self.report["issues"].append({
                    "type": "operational",
                    "severity": "high",
                    "message": f"Timeout rate выше целевого: {timeout_rate:.1f}% > 10%",
                    "recommendation": "Улучшить динамический спред, оптимизировать цены лимитов"
                })
            
            if market_fallback_rate > 5:
                self.report["issues"].append({
                    "type": "operational",
                    "severity": "medium",
                    "message": f"Fallback на market выше целевого: {market_fallback_rate:.1f}% > 5%",
                    "recommendation": "Снизить timeout rate, улучшить ликвидность инструментов"
                })
            
            logger.info(f"✅ Операционные метрики: fill rate {limit_fill_rate:.1f}%, timeout {timeout_rate:.1f}%")
            
            conn.close()
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки операционных метрик: {e}")
            self.report["issues"].append({
                "type": "system",
                "severity": "high",
                "message": f"Ошибка проверки операционных метрик: {e}"
            })
    
    async def _check_code_quality(self, trace) -> None:
        """Проверяет качество кода"""
        logger.info("🔍 Проверка качества кода...")
        trace.record(step="act", name="check_code_quality")
        
        try:
            # Проверка линтера (упрощённая версия)
            import subprocess
            result = subprocess.run(
                ["python3", "-m", "pylint", "--errors-only", "auto_execution.py", "signal_live.py"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            error_count = result.stdout.count("error:")
            self.report["metrics"]["code_quality"] = {
                "pylint_errors": error_count,
                "status": "ok" if error_count == 0 else "needs_attention"
            }
            
            if error_count > 0:
                self.report["issues"].append({
                    "type": "code_quality",
                    "severity": "low",
                    "message": f"Найдено {error_count} ошибок линтера",
                    "recommendation": "Исправить ошибки линтера для улучшения качества кода"
                })
            
            logger.info(f"✅ Качество кода: {error_count} ошибок линтера")
            
        except Exception as e:
            logger.debug(f"⚠️ Не удалось проверить качество кода: {e}")
            self.report["metrics"]["code_quality"] = {"status": "check_failed"}
    
    async def _check_risks(self, trace) -> None:
        """Проверяет риски и проблемы"""
        logger.info("⚠️ Проверка рисков...")
        trace.record(step="act", name="check_risks")
        
        try:
            # Проверка открытых позиций без SL/TP
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            
            cursor = conn.execute("""
                SELECT COUNT(*) as count
                FROM active_positions
                WHERE status = 'open'
            """)
            
            open_positions = cursor.fetchone()['count'] or 0
            
            # Проверка убыточных сделок за последние 24 часа
            since = datetime.utcnow() - timedelta(hours=24)
            cursor = conn.execute("""
                SELECT COUNT(*) as count, SUM(net_pnl_usd) as total_loss
                FROM trades
                WHERE datetime(entry_time) >= datetime(?)
                  AND net_pnl_usd < 0
            """, (since.isoformat(),))
            
            row = cursor.fetchone()
            losing_trades = row['count'] or 0
            total_loss = abs(row['total_loss'] or 0.0)
            
            self.report["metrics"]["risks"] = {
                "open_positions": open_positions,
                "losing_trades_24h": losing_trades,
                "total_loss_24h_usd": round(total_loss, 2)
            }
            
            if losing_trades > 10:
                self.report["issues"].append({
                    "type": "risk",
                    "severity": "high",
                    "message": f"Много убыточных сделок за 24ч: {losing_trades}",
                    "recommendation": "Проанализировать причины, улучшить фильтры сигналов"
                })
            
            if total_loss > 100:
                self.report["issues"].append({
                    "type": "risk",
                    "severity": "high",
                    "message": f"Большой убыток за 24ч: {total_loss:.2f} USD",
                    "recommendation": "Проверить риск-менеджмент, уменьшить размер позиций"
                })
            
            logger.info(f"✅ Риски: {open_positions} открытых позиций, {losing_trades} убыточных сделок")
            
            conn.close()
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки рисков: {e}")
    
    async def _generate_recommendations(self, trace) -> None:
        """Генерирует рекомендации на основе анализа"""
        logger.info("💡 Генерация рекомендаций...")
        trace.record(step="think", name="generate_recommendations")
        
        # Рекомендации на основе найденных проблем
        for issue in self.report["issues"]:
            if issue.get("recommendation"):
                self.report["recommendations"].append({
                    "priority": issue.get("severity", "medium"),
                    "action": issue["recommendation"],
                    "related_issue": issue["message"]
                })
        
        # Дополнительные рекомендации на основе метрик
        financial = self.report["metrics"].get("financial", {})
        if financial.get("win_rate_pct", 0) < 50:
            self.report["recommendations"].append({
                "priority": "high",
                "action": "Улучшить качество сигналов: увеличить порог direction_confidence, добавить дополнительные фильтры",
                "related_issue": "Низкий win rate"
            })
        
        operational = self.report["metrics"].get("operational", {})
        if operational.get("limit_timeout_rate_pct", 0) > 15:
            self.report["recommendations"].append({
                "priority": "high",
                "action": "Оптимизировать лимитные ордера: улучшить динамический спред, увеличить TTL до 60 секунд",
                "related_issue": "Высокий timeout rate"
            })
    
    def _determine_status(self) -> None:
        """Определяет общий статус проекта"""
        issues_high = sum(1 for issue in self.report["issues"] if issue.get("severity") == "high")
        issues_medium = sum(1 for issue in self.report["issues"] if issue.get("severity") == "medium")
        
        if issues_high > 0:
            self.report["status"] = "needs_attention"
        elif issues_medium > 3:
            self.report["status"] = "needs_attention"
        elif len(self.report["issues"]) == 0:
            self.report["status"] = "healthy"
        else:
            self.report["status"] = "good"
    
    def save_report(self, output_path: Optional[Path] = None) -> Path:
        """Сохраняет отчёт в файл"""
        if output_path is None:
            output_path = PROJECT_ROOT / "docs" / "project_management" / "daily_reports" / f"daily_report_{datetime.utcnow().strftime('%Y%m%d')}.json"
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(self.report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ Отчёт сохранён: {output_path}")
        return output_path
    
    def print_summary(self) -> None:
        """Выводит краткую сводку отчёта"""
        print("\n" + "="*60)
        print("📊 ЕЖЕДНЕВНЫЙ ОТЧЁТ PM")
        print("="*60)
        print(f"📅 Дата: {self.report['date']}")
        print(f"📈 Статус: {self.report['status'].upper()}")
        print()
        
        if "financial" in self.report["metrics"]:
            fin = self.report["metrics"]["financial"]
            print("💰 ФИНАНСОВЫЕ МЕТРИКИ:")
            print(f"  • Сделок за 24ч: {fin.get('total_trades_24h', 0)}")
            print(f"  • Win rate: {fin.get('win_rate_pct', 0):.1f}%")
            print(f"  • PnL: {fin.get('total_pnl_usd', 0):.2f} USD")
            print()
        
        if "operational" in self.report["metrics"]:
            op = self.report["metrics"]["operational"]
            print("⚙️ ОПЕРАЦИОННЫЕ МЕТРИКИ:")
            print(f"  • Fill rate: {op.get('limit_fill_rate_pct', 0):.1f}%")
            print(f"  • Timeout rate: {op.get('limit_timeout_rate_pct', 0):.1f}%")
            print(f"  • Market fallback: {op.get('market_fallback_rate_pct', 0):.1f}%")
            print()
        
        if self.report["issues"]:
            print("⚠️ ПРОБЛЕМЫ:")
            for issue in self.report["issues"][:5]:  # Показываем первые 5
                print(f"  • [{issue.get('severity', 'unknown').upper()}] {issue['message']}")
            print()
        
        if self.report["recommendations"]:
            print("💡 РЕКОМЕНДАЦИИ:")
            for rec in self.report["recommendations"][:5]:  # Показываем первые 5
                print(f"  • [{rec.get('priority', 'medium').upper()}] {rec['action']}")
            print()
        
        print("="*60 + "\n")


async def main():
    """Главная функция"""
    pm = ProjectManager()
    report = await pm.run_daily_check()
    pm.save_report()
    pm.print_summary()
    return report


if __name__ == "__main__":
    asyncio.run(main())

