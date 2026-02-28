"""
Report Generator
Генерация автоматических отчетов (ежедневных/еженедельных)
Singularity 8.0: Monitoring and Analytics
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import asyncpg

# Fix: Ensure Any is defined for older python or specific environments
if "Any" not in globals():
    from typing import Any

logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")


class ReportGenerator:
    """
    Генератор автоматических отчетов.
    Создает ежедневные и еженедельные отчеты о работе системы.
    """

    def __init__(self, db_url: str = DB_URL):
        """
        Args:
            db_url: URL базы данных
        """
        self.db_url = db_url

    async def generate_daily_report(self) -> str:
        """
        Генерирует ежедневный отчет.
        [SINGULARITY 24.0] Включает аудит SOP, инсайтов и системные метрики.
        """
        report_lines = []
        report_lines.append("# 📊 Ежедневный отчет Singularity 24.0")
        report_lines.append(f"Дата: {datetime.now().strftime('%Y-%m-%d')}\n")

        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # 0. Статус систем (Mac Studio)
                report_lines.append("## 🖥 Статус систем (Mac Studio)")
                try:
                    from resource_monitor import ResourceMonitor

                    monitor = ResourceMonitor()
                    res = await monitor.get_system_resources()
                    ram = res.get("ram", {})
                    cpu = res.get("cpu", {})
                    report_lines.append(
                        f"- **RAM:** {ram.get('used_percent', 0):.1f}% ({ram.get('used_gb', 0):.1f}/{ram.get('total_gb', 0):.1f} GB)"
                    )
                    report_lines.append(
                        f"- **CPU:** {cpu.get('percent', 0):.1f}% ({cpu.get('count', 0)} cores)"
                    )
                    if res.get("temperature"):
                        report_lines.append(f"- **Температура:** {res['temperature']}°C")
                except Exception as re:
                    report_lines.append(f"- ⚠️ Ошибка мониторинга ресурсов: {re}")

                # Проверка моделей
                try:
                    from available_models_scanner import scan_models

                    models = await scan_models()
                    report_lines.append(f"- **Модели Ollama:** {len(models.ollama_models)} активны")
                    report_lines.append(f"- **Модели MLX:** {len(models.mlx_models)} активны")
                    if "victoria-wisdom-30b" in models.mlx_models:
                        report_lines.append("  - ✅ Victoria Wisdom 30B (MLX) доступна")
                except Exception as me:
                    report_lines.append(f"- ⚠️ Ошибка сканирования моделей: {me}")
                report_lines.append("")

                # 1. Статистика запросов за день
                stats = await conn.fetchrow("""
                    SELECT
                        COUNT(*) as total_requests,
                        COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '1 hour') as requests_last_hour
                    FROM semantic_ai_cache
                    WHERE created_at > CURRENT_DATE
                """)

                if stats:
                    report_lines.append("## 📈 Статистика запросов")
                    report_lines.append(f"- Всего запросов за день: {stats['total_requests'] or 0}")
                    report_lines.append(
                        f"- Запросов за последний час: {stats['requests_last_hour'] or 0}\n"
                    )

                # 2. Cache hit rate
                cache_stats = await conn.fetchrow("""
                    SELECT
                        COUNT(*) FILTER (WHERE usage_count > 0)::float / NULLIF(COUNT(*), 0) as hit_rate
                    FROM semantic_ai_cache
                    WHERE created_at > CURRENT_DATE
                """)

                if cache_stats and cache_stats["hit_rate"]:
                    report_lines.append("## 🚀 Cache Hit Rate")
                    report_lines.append(f"- Hit rate: {cache_stats['hit_rate']:.2%}\n")

                # [SINGULARITY 24.0] 3. Аудит новых знаний и SOP
                sop_stats = await conn.fetchrow("""
                    SELECT
                        COUNT(*) as total_nodes,
                        COUNT(*) FILTER (WHERE is_verified = true) as verified_nodes,
                        COUNT(*) FILTER (WHERE metadata->>'type' = 'evolution_log') as evolution_nodes,
                        COUNT(*) FILTER (WHERE metadata->>'injected_as_sop' = 'true') as injected_sops
                    FROM knowledge_nodes
                    WHERE created_at > CURRENT_DATE
                """)

                if sop_stats:
                    report_lines.append("## 🧠 Эволюция мудрости")
                    report_lines.append(f"- Новых узлов знаний: {sop_stats['total_nodes']}")
                    report_lines.append(
                        f"- Верифицировано экспертами: {sop_stats['verified_nodes']}"
                    )
                    report_lines.append(
                        f"- Логи эволюции (Evolution): {sop_stats['evolution_nodes']}"
                    )
                    report_lines.append(f"- Новых SOP внедрено: {sop_stats['injected_sops']}\n")

                # 4. Топ эксперты
                expert_stats = await conn.fetch("""
                    SELECT expert_name, COUNT(*) as request_count
                    FROM semantic_ai_cache
                    WHERE created_at > CURRENT_DATE
                    GROUP BY expert_name
                    ORDER BY request_count DESC
                    LIMIT 5
                """)

                if expert_stats:
                    report_lines.append("## 👥 Активность экспертов")
                    for row in expert_stats:
                        report_lines.append(f"- {row['expert_name']}: {row['request_count']} задач")
                    report_lines.append("")

                # 5. Ошибки и аномалии (из логов аудитора)
                report_lines.append("## 🛡 Самодиагностика")
                try:
                    # Ищем последний отчет аудитора
                    import glob

                    audit_files = sorted(glob.glob("docs/log_audit_*.md"), reverse=True)
                    if audit_files:
                        with open(audit_files[0]) as f:
                            audit_content = f.read()
                            # Берем только краткое саммари (первые 5 строк после заголовка)
                            summary = "\n".join(audit_content.split("\n")[2:7])
                            report_lines.append(f"Последний аудит логов:\n{summary}")
                    else:
                        report_lines.append("- Критических ошибок в логах не обнаружено.")
                except Exception:
                    report_lines.append("- Статус аудита логов недоступен.")

            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"❌ [REPORT GENERATOR] Ошибка генерации ежедневного отчета: {e}")
            report_lines.append(f"⚠️ Ошибка генерации отчета: {e}")

        return "\n".join(report_lines)

    async def generate_weekly_report(self) -> str:
        """
        Генерирует еженедельный отчет с трендами.

        Returns:
            Текст отчета в Markdown формате
        """
        report_lines = []
        report_lines.append("# 📊 Еженедельный отчет Singularity 8.0")
        report_lines.append(f"Период: {datetime.now() - timedelta(days=7)} - {datetime.now()}\n")

        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # 1. Тренды запросов
                daily_stats = await conn.fetch("""
                    SELECT
                        DATE(created_at) as date,
                        COUNT(*) as requests
                    FROM semantic_ai_cache
                    WHERE created_at > NOW() - INTERVAL '7 days'
                    GROUP BY DATE(created_at)
                    ORDER BY date
                """)

                if daily_stats:
                    report_lines.append("## 📈 Тренды запросов")
                    for row in daily_stats:
                        report_lines.append(f"- {row['date']}: {row['requests']} запросов")
                    report_lines.append("")

                # 2. Рекомендации по улучшению
                report_lines.append("## 💡 Рекомендации")
                report_lines.append("- Продолжать мониторинг производительности")
                report_lines.append("- Анализировать паттерны использования")
                report_lines.append("")

            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"❌ [REPORT GENERATOR] Ошибка генерации еженедельного отчета: {e}")
            report_lines.append(f"⚠️ Ошибка генерации отчета: {e}")

        return "\n".join(report_lines)

    async def send_report_to_telegram(self, report_text: str, report_type: str = "daily"):
        """
        Отправляет отчет в Telegram.

        Args:
            report_text: Текст отчета
            report_type: Тип отчета ('daily' или 'weekly')
        """
        try:
            from telegram_alerter import get_telegram_alerter

            alerter = get_telegram_alerter()
            await alerter.send_alert(
                report_text, priority="low", source=f"Report Generator ({report_type})"
            )
        except Exception as e:
            logger.error(f"❌ [REPORT GENERATOR] Ошибка отправки отчета: {e}")

    async def start_periodic_reports(self):
        """
        Запускает периодическую генерацию отчетов (Singularity 8.0).
        Ежедневные отчеты в 8:00, еженедельные в понедельник в 9:00.
        """
        logger.info("📊 [REPORT GENERATOR] Запуск периодической генерации отчетов...")

        # [SINGULARITY 24.0] Сразу шлем тестовый отчет при запуске, чтобы убедиться в работе
        try:
            logger.info("📊 [REPORT GENERATOR] Отправка стартового отчета...")
            daily_report = await self.generate_daily_report()
            await self.send_report_to_telegram(daily_report, "startup")
        except Exception as se:
            logger.error(f"❌ [REPORT GENERATOR] Ошибка стартового отчета: {se}")

        while True:
            try:
                from datetime import datetime

                now = datetime.now()
                current_hour = now.hour
                current_weekday = now.weekday()  # 0 = понедельник

                # Ежедневный отчет в 8:00
                if current_hour == 8:
                    logger.info("📊 [REPORT GENERATOR] Генерация ежедневного отчета...")
                    daily_report = await self.generate_daily_report()
                    await self.send_report_to_telegram(daily_report, "daily")
                    logger.info("✅ [REPORT GENERATOR] Ежедневный отчет отправлен")
                    # Ждем до следующего дня (чтобы не отправлять несколько раз в час)
                    await asyncio.sleep(3600)

                # Еженедельный отчет в понедельник в 9:00
                elif current_hour == 9 and current_weekday == 0:
                    logger.info("📊 [REPORT GENERATOR] Генерация еженедельного отчета...")
                    weekly_report = await self.generate_weekly_report()
                    await self.send_report_to_telegram(weekly_report, "weekly")
                    logger.info("✅ [REPORT GENERATOR] Еженедельный отчет отправлен")
                    # Ждем до следующего дня
                    await asyncio.sleep(3600)

                # Проверяем каждый час
                await asyncio.sleep(3600)

            except Exception as e:
                logger.error(f"❌ [REPORT GENERATOR] Ошибка в периодической генерации отчетов: {e}")
                await asyncio.sleep(3600)


# Singleton instance
_report_generator_instance: Optional[ReportGenerator] = None


def get_report_generator(db_url: str = DB_URL) -> ReportGenerator:
    """Получить singleton экземпляр генератора отчетов"""
    global _report_generator_instance
    if _report_generator_instance is None:
        _report_generator_instance = ReportGenerator(db_url=db_url)
    return _report_generator_instance
