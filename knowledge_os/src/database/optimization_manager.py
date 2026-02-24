"""
Менеджер оптимизаций базы данных.
Объединяет все оптимизации в единую систему управления.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.shared.utils.datetime_utils import get_utc_now

logger = logging.getLogger(__name__)


class DatabaseOptimizationManager:
    """Менеджер всех оптимизаций БД"""

    def __init__(self, db):
        """
        Args:
            db: Экземпляр Database
        """
        self.db = db
        self.optimizations_status: Dict[str, bool] = {}
        self.optimization_metrics: Dict[str, Any] = {}

    def apply_all_optimizations(self, force: bool = False) -> Dict[str, Any]:
        """
        Применяет все оптимизации к базе данных.

        Args:
            force: Принудительное применение (даже если уже применено)

        Returns:
            Словарь с результатами применения
        """
        results = {
            "timestamp": get_utc_now().isoformat(),
            "optimizations": {},
            "success_count": 0,
            "failed_count": 0,
            "total_time": 0.0,
        }

        import time

        start_time = time.time()

        logger.info("🚀 Применение всех оптимизаций БД...")

        # 1. CHECK constraints (триггеры валидации)
        try:
            if hasattr(self.db, "_add_validation_triggers"):
                self.db._add_validation_triggers()
                results["optimizations"]["check_constraints"] = {"status": "success"}
                results["success_count"] += 1
            else:
                results["optimizations"]["check_constraints"] = {
                    "status": "skipped",
                    "reason": "Method not found",
                }
        except Exception as e:
            results["optimizations"]["check_constraints"] = {"status": "failed", "error": str(e)}
            results["failed_count"] += 1

        # 2. Суррогатные ключи
        try:
            if hasattr(self.db, "_add_surrogate_time_keys"):
                self.db._add_surrogate_time_keys()
                results["optimizations"]["surrogate_keys"] = {"status": "success"}
                results["success_count"] += 1
            else:
                results["optimizations"]["surrogate_keys"] = {
                    "status": "skipped",
                    "reason": "Method not found",
                }
        except Exception as e:
            results["optimizations"]["surrogate_keys"] = {"status": "failed", "error": str(e)}
            results["failed_count"] += 1

        # 3. Частичные индексы
        try:
            if hasattr(self.db, "_create_partial_indexes"):
                self.db._create_partial_indexes()
                results["optimizations"]["partial_indexes"] = {"status": "success"}
                results["success_count"] += 1
            else:
                results["optimizations"]["partial_indexes"] = {
                    "status": "skipped",
                    "reason": "Method not found",
                }
        except Exception as e:
            results["optimizations"]["partial_indexes"] = {"status": "failed", "error": str(e)}
            results["failed_count"] += 1

        # 4. Материализованные представления
        try:
            from src.database.materialized_views import create_common_materialized_views

            self.db.materialized_views = create_common_materialized_views(self.db)
            results["optimizations"]["materialized_views"] = {"status": "success"}
            results["success_count"] += 1
        except Exception as e:
            results["optimizations"]["materialized_views"] = {"status": "failed", "error": str(e)}
            results["failed_count"] += 1

        results["total_time"] = time.time() - start_time

        logger.info(
            "✅ Оптимизации применены: %d успешно, %d ошибок, время: %.2f сек",
            results["success_count"],
            results["failed_count"],
            results["total_time"],
        )

        return results

    def get_optimization_status(self) -> Dict[str, Any]:
        """
        Возвращает статус всех оптимизаций.

        Returns:
            Словарь со статусом оптимизаций
        """
        status = {
            "check_constraints": False,
            "surrogate_keys": False,
            "partial_indexes": False,
            "materialized_views": False,
            "archive_manager": False,
            "index_auditor": False,
            "query_optimizer": False,
            "table_maintenance": False,
            "adaptive_chunking": False,
        }

        try:
            # Проверяем CHECK constraints (триггеры)
            triggers = self.db.execute_with_retry(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'validate_%'",
                (),
                is_write=False,
            )
            status["check_constraints"] = len(triggers) >= 4

            # Проверяем суррогатные ключи (индексы)
            surrogate_indexes = self.db.execute_with_retry(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE '%surrogate%'",
                (),
                is_write=False,
            )
            status["surrogate_keys"] = len(surrogate_indexes) >= 3

            # Проверяем частичные индексы
            partial_indexes = self.db.execute_with_retry(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE '%priority%'",
                (),
                is_write=False,
            )
            status["partial_indexes"] = len(partial_indexes) >= 4

            # Проверяем модули
            try:
                from src.database.archive_manager import ArchiveManager

                status["archive_manager"] = True
            except:
                pass

            try:
                from src.database.index_auditor import IndexAuditor

                status["index_auditor"] = True
            except:
                pass

            try:
                from src.database.query_optimizer import QueryOptimizer

                status["query_optimizer"] = True
            except:
                pass

            try:
                from src.database.table_maintenance import TableMaintenance

                status["table_maintenance"] = True
            except:
                pass

            try:
                from src.database.fetch_optimizer import _calculate_adaptive_batch_size

                status["adaptive_chunking"] = True
            except:
                pass

            # Проверяем материализованные представления
            views = self.db.execute_with_retry(
                "SELECT name FROM sqlite_master WHERE type='view' AND name LIKE 'v_%'",
                (),
                is_write=False,
            )
            status["materialized_views"] = len(views) > 0 or hasattr(self.db, "materialized_views")

        except Exception as e:
            logger.warning("⚠️ [OptimizationManager] Ошибка проверки статуса: %s", e)

        return status

    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Возвращает метрики производительности после оптимизаций.

        Returns:
            Словарь с метриками
        """
        metrics = {
            "database_size_mb": 0.0,
            "index_count": 0,
            "table_count": 0,
            "total_rows": 0,
            "optimization_applied": [],
        }

        try:
            import os

            if os.path.exists(self.db.db_path):
                metrics["database_size_mb"] = os.path.getsize(self.db.db_path) / (1024 * 1024)

            # Подсчитываем индексы
            indexes = self.db.execute_with_retry(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'",
                (),
                is_write=False,
            )
            metrics["index_count"] = indexes[0][0] if indexes else 0

            # Подсчитываем таблицы
            tables = self.db.execute_with_retry(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'",
                (),
                is_write=False,
            )
            metrics["table_count"] = tables[0][0] if tables else 0

            # Проверяем примененные оптимизации
            status = self.get_optimization_status()
            metrics["optimization_applied"] = [name for name, applied in status.items() if applied]

        except Exception as e:
            logger.warning("⚠️ [OptimizationManager] Ошибка получения метрик: %s", e)

        return metrics

    def generate_optimization_report(self) -> str:
        """
        Генерирует отчет о примененных оптимизациях.

        Returns:
            Текстовый отчет
        """
        status = self.get_optimization_status()
        metrics = self.get_performance_metrics()

        report = []
        report.append("=" * 60)
        report.append("📊 ОТЧЕТ ОБ ОПТИМИЗАЦИЯХ БАЗЫ ДАННЫХ")
        report.append("=" * 60)
        report.append(f"Дата: {get_utc_now().isoformat()}")
        report.append("")

        report.append("📈 МЕТРИКИ:")
        report.append(f"  • Размер БД: {metrics['database_size_mb']:.2f} MB")
        report.append(f"  • Таблиц: {metrics['table_count']}")
        report.append(f"  • Индексов: {metrics['index_count']}")
        report.append("")

        report.append("✅ ПРИМЕНЕННЫЕ ОПТИМИЗАЦИИ:")
        applied = [name for name, applied in status.items() if applied]
        for opt_name in applied:
            report.append(f"  ✅ {opt_name}")

        report.append("")
        report.append("❌ НЕ ПРИМЕНЕННЫЕ ОПТИМИЗАЦИИ:")
        not_applied = [name for name, applied in status.items() if not applied]
        if not_applied:
            for opt_name in not_applied:
                report.append(f"  ❌ {opt_name}")
        else:
            report.append("  (нет)")

        report.append("")
        report.append("=" * 60)

        return "\n".join(report)
