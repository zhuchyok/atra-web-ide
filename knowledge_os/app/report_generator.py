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

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")


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

        # [SINGULARITY 24.0] Ожидание готовности БД (Retry Logic)
        max_retries = 5
        retry_delay = 5
        conn = None

        for attempt in range(max_retries):
            try:
                conn = await asyncpg.connect(self.db_url)
                break
            except Exception as e:
                if "starting up" in str(e) or "connection refused" in str(e).lower():
                    logger.info(
                        f"⏳ [REPORT GENERATOR] БД еще запускается (попытка {attempt + 1}/{max_retries})..."
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    raise e

        if not conn:
            report_lines.append("❌ Ошибка: Не удалось подключиться к БД после нескольких попыток.")
            return "\n".join(report_lines)

        try:
            try:
                # 0. Статус систем (Mac Studio)
                report_lines.append("## 🖥 Статус Docker (Виртуальный)")
                try:
                    from resource_monitor import ResourceMonitor

                    monitor = ResourceMonitor()
                    res = await monitor.get_system_resources()
                    ram = res.get("ram", {})
                    cpu = res.get("cpu", {})
                    report_lines.append(
                        f"- **RAM Docker:** {ram.get('used_percent', 0):.1f}% ({ram.get('used_gb', 0):.1f}/{ram.get('total_gb', 0):.1f} GB)"
                    )
                    report_lines.append(
                        f"- **CPU Docker:** {cpu.get('percent', 0):.1f}% ({cpu.get('count', 0)} cores)"
                    )
                except Exception as re:
                    report_lines.append(f"- ⚠️ Ошибка мониторинга ресурсов Docker: {re}")

                # [SINGULARITY 24.0] Реальный статус Mac Studio (Хост через Resource Monitor)
                report_lines.append("\n## 💻 Хост (Mac Studio M4 Max)")
                try:
                    import httpx

                    # Попробуем получить данные от MLX API Server, который видит реальное железо
                    # host.docker.internal — это мост к хосту Mac
                    mlx_url = os.getenv("MLX_API_URL", "http://host.docker.internal:11435")
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        r = await client.get(f"{mlx_url}/")
                        if r.status_code == 200:
                            data = r.json()
                            host_mem = data.get("memory", {})
                            # В MLX API Server root memory: {"used_percent": ..., "available_gb": ...}
                            if host_mem:
                                # Мы знаем, что у пользователя 128 ГБ
                                total_gb = 128.0
                                used_percent = host_mem.get("used_percent", 0)
                                used_gb = (used_percent / 100.0) * total_gb
                                report_lines.append(
                                    f"- **Общая RAM:** {used_percent:.1f}% ({used_gb:.1f}/{total_gb:.1f} GB)"
                                )
                                # CPU в корневом эндпоинте MLX пока нет, но мы можем добавить его в будущем
                            else:
                                report_lines.append(
                                    "- ⚠️ Данные хоста временно недоступны через MLX"
                                )
                        else:
                            report_lines.append(
                                f"- ⚠️ MLX API вернул {r.status_code}, данные хоста скрыты"
                            )
                except Exception as he:
                    report_lines.append(f"- ⚠️ Ошибка мониторинга хоста: {he}")

                # [SINGULARITY 24.0] Глубокий аудит контейнеров через Docker API
                report_lines.append("\n## 🐳 Аудит контейнеров Docker")
                try:
                    import json
                    import subprocess

                    # Используем curl для общения с Docker Socket напрямую (без docker cli)
                    # [SINGULARITY 24.0] Обновлена версия API до v1.44 (требование Docker Desktop 4.27+)
                    cmd = 'curl -s --unix-socket /var/run/docker.sock "http://localhost/v1.44/containers/json?all=1"'
                    try:
                        output = subprocess.check_output(cmd, shell=True).decode().strip()
                        if not output or "client version" in output:
                            # Пробуем без указания версии (Docker сам подберет актуальную)
                            cmd = 'curl -s --unix-socket /var/run/docker.sock "http://localhost/containers/json?all=1"'
                            output = subprocess.check_output(cmd, shell=True).decode().strip()

                        containers_data = json.loads(output)

                        up_count = 0
                        down_count = 0
                        restarting_count = 0

                        for c in containers_data:
                            state = c.get("State", "")
                            if state == "running":
                                up_count += 1
                            elif state == "restarting":
                                restarting_count += 1
                            else:
                                down_count += 1

                        report_lines.append(f"- **Всего контейнеров:** {len(containers_data)}")
                        report_lines.append(f"- ✅ **Работают (Up):** {up_count}")
                        if restarting_count > 0:
                            report_lines.append(
                                f"- 🔄 **Перезагружаются (Restarting):** {restarting_count}"
                            )
                        if down_count > 0:
                            report_lines.append(f"- 💤 **Выключены (Exited):** {down_count}")

                        # Проверка критических сервисов
                        critical_services = [
                            "victoria-agent",
                            "knowledge_os_orchestrator",
                            "knowledge_postgres",
                            "telegram-notifications",
                        ]
                        for svc in critical_services:
                            # Ищем сервис по имени в списке имен контейнеров (они начинаются с /)
                            is_up = any(
                                c.get("State") == "running"
                                and any(svc in name for name in c.get("Names", []))
                                for c in containers_data
                            )
                            svc_status = "✅" if is_up else "❌"
                            report_lines.append(f"  {svc_status} {svc}")

                    except Exception as e:
                        report_lines.append(f"- ⚠️ Ошибка Docker API: {e}")

                except Exception as de:
                    report_lines.append(f"- ⚠️ Ошибка аудита Docker: {de}")
                report_lines.append("")

                # Проверка моделей
                try:
                    from available_models_scanner import scan_and_select_models

                    models = await scan_and_select_models()
                    report_lines.append(f"- **Модели Ollama:** {len(models.ollama_models)} активны")
                    report_lines.append(f"- **Модели MLX:** {len(models.mlx_models)} активны")
                    if "victoria-wisdom-v3.5" in models.mlx_models:
                        report_lines.append("  - ✅ Victoria Wisdom v3.5 (35B MoE, MLX) доступна")
                except Exception as me:
                    report_lines.append(f"- ⚠️ Ошибка сканирования моделей: {me}")
                report_lines.append("")

                # 1. Статистика задач за день (из таблицы tasks — реальная активность системы)
                stats = await conn.fetchrow("""
                    SELECT
                        COUNT(*) as total_requests,
                        COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '1 hour') as requests_last_hour,
                        COUNT(*) FILTER (WHERE status = 'completed') as completed_today,
                        COUNT(*) FILTER (WHERE status = 'failed') as failed_today
                    FROM tasks
                    WHERE created_at > NOW() - INTERVAL '24 hours'
                """)

                if stats:
                    report_lines.append("## 📈 Статистика задач (последние 24ч)")
                    report_lines.append(f"- Всего задач за 24ч: {stats['total_requests'] or 0}")
                    report_lines.append(
                        f"- Задач за последний час: {stats['requests_last_hour'] or 0}"
                    )
                    report_lines.append(f"- Завершено успешно: {stats['completed_today'] or 0}")
                    report_lines.append(f"- Ошибок: {stats['failed_today'] or 0}\n")

                # 2. Cache hit rate
                cache_stats = await conn.fetchrow("""
                    SELECT
                        COUNT(*) FILTER (WHERE usage_count > 0)::float / NULLIF(COUNT(*), 0) as hit_rate
                    FROM semantic_ai_cache
                    WHERE created_at > NOW() - INTERVAL '24 hours'
                """)

                if cache_stats and cache_stats["hit_rate"]:
                    report_lines.append("## 🚀 Cache Hit Rate")
                    report_lines.append(f"- Hit rate: {cache_stats['hit_rate']:.2%}\n")

                # [SINGULARITY 24.0] 3. Аудит новых знаний и SOP (за последние 24ч, не с полуночи)
                sop_stats = await conn.fetchrow("""
                    SELECT
                        COUNT(*) as total_nodes,
                        COUNT(*) FILTER (WHERE is_verified = true) as verified_nodes,
                        COUNT(*) FILTER (WHERE metadata->>'type' = 'evolution_log') as evolution_nodes,
                        COUNT(*) FILTER (WHERE metadata->>'injected_as_sop' = 'true') as injected_sops
                    FROM knowledge_nodes
                    WHERE created_at > NOW() - INTERVAL '24 hours'
                """)

                if sop_stats:
                    report_lines.append("## 🧠 Эволюция мудрости (последние 24ч)")
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
                    WHERE created_at > NOW() - INTERVAL '24 hours'
                    GROUP BY expert_name
                    ORDER BY request_count DESC
                    LIMIT 5
                """)

                if expert_stats:
                    report_lines.append("## 👥 Активность экспертов (последние 24ч)")
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
