import asyncio
import httpx
import json
import os
import logging
from pathlib import Path
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("self_curator")

ROOT = Path(__file__).resolve().parents[1]
VICTORIA_URL = os.getenv("VICTORIA_URL", "http://0.0.0.0:8010")
REPORTS_DIR = ROOT / "docs" / "curator_reports"
TASKS_FILE = ROOT / "scripts" / "curator_tasks.txt"

async def run_curator():
    """Запуск стандартного кураторского прогона"""
    logger.info("🚀 Запуск кураторского прогона...")
    # Используем системный python3, так как в venv какие-то проблемы с соединением
    cmd = ["python3", str(ROOT / "scripts" / "curator_send_tasks_to_victoria.py"), "--file", str(TASKS_FILE), "--async", "--quick"]
    process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await process.communicate()

    logger.info(f"STDOUT: {stdout.decode()}")
    logger.info(f"STDERR: {stderr.decode()}")

    if process.returncode != 0:
        logger.error(f"❌ Ошибка прогона (code {process.returncode})")
        return None

    # Находим последний отчет
    reports = sorted(REPORTS_DIR.glob("curator_*.json"), key=os.path.getmtime, reverse=True)
    if not reports:
        return None
    return reports[0]

async def ask_victoria_to_analyze(report_path: Path):
    """Просим Викторию проанализировать собственный отчет"""
    with open(report_path, "r", encoding="utf-8") as f:
        report_data = json.load(f)

    # Упрощаем отчет для промпта
    summary = []
    for res in report_data.get("results", []):
        output_preview = res.get("output_preview") or ""
        summary.append({
            "goal": res["goal"],
            "status": res["status"],
            "output": output_preview[:500]
        })

    prompt = f"""
### ЗАДАЧА: САМО-АУДИТ (Self-Curator)
Ты — Виктория, Team Lead. Проанализируй результаты своего последнего кураторского прогона.

РЕЗУЛЬТАТЫ:
{json.dumps(summary, indent=2, ensure_ascii=False)}

ЗАДАНИЕ:
1. Оцени качество своих ответов (точность, тон, соответствие стандартам).
2. Найди слабые места или галлюцинации.
3. Предложи конкретные правки для эталонов в docs/curator_reports/standards/ или новых узлов знаний.
4. Напиши план действий "Умнее, Быстрее, Лучше".

Отвечай как Team Lead корпорации ATRA.
"""

    logger.info("🧠 Отправка отчета Виктории на само-анализ...")
    # Используем стриминг для предотвращения ReadError при долгой генерации
    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            async with client.stream(
                "POST",
                f"{VICTORIA_URL}/stream",
                json={
                    "goal": prompt,
                    "project_context": "self-audit",
                    "max_steps": 50
                }
            ) as response:
                if response.status_code == 200:
                    full_content = ""
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            try:
                                data = json.loads(line[6:])
                                if data.get("type") == "chunk":
                                    full_content += data.get("content", "")
                            except:
                                pass

                    analysis = full_content.strip() or "Нет ответа."

                    # Сохраняем анализ
                    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
                    analysis_path = REPORTS_DIR / f"self_analysis_{ts}.md"
                    analysis_path.write_text(f"# Само-анализ Виктории ({ts})\n\n{analysis}", encoding="utf-8")
                    logger.info(f"✅ Анализ сохранен: {analysis_path}")
                    return analysis
                else:
                    logger.error(f"❌ Ошибка API: {response.status_code}")
                    return None
        except Exception as e:
            logger.error(f"❌ Ошибка при анализе: {e}")
            return None

async def main():
    report = await run_curator()
    if report:
        await ask_victoria_to_analyze(report)
    else:
        logger.error("❌ Не удалось получить отчет.")

if __name__ == "__main__":
    asyncio.run(main())
