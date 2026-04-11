import asyncio
import httpx
import json
import os
import logging
from pathlib import Path
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("self_curator")

NTFY_URL = os.getenv("NTFY_URL", "")
TG_TOKEN = os.getenv("TG_TOKEN", "")
TG_CHAT_ID = os.getenv("TG_CHAT_ID", "")


async def _ntfy_notify(title: str, body: str) -> None:
    """Отправка в ntfy → Telegram fallback."""
    if NTFY_URL:
        try:
            # trust_env=False — отключаем ALL_PROXY из env (socks5h без httpx-socks даёт gaierror)
            async with httpx.AsyncClient(timeout=10.0, trust_env=False) as c:
                await c.post(NTFY_URL, content=body.encode(),
                             headers={"Title": title, "Priority": "default"})
            logger.info("ntfy отправлено ✅")
            return
        except Exception as e:
            logger.warning("ntfy failed: %s", e)
    if TG_TOKEN and TG_CHAT_ID:
        try:
            tg_url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
            proxy = os.getenv("TG_PROXY", "")
            kw = {"proxy": proxy} if proxy else {}
            async with httpx.AsyncClient(timeout=10.0, **kw) as c:
                await c.post(tg_url, json={
                    "chat_id": TG_CHAT_ID,
                    "text": f"*{title}*\n\n{body[:4000]}",
                    "parse_mode": "Markdown",
                })
            logger.info("Telegram отправлено ✅")
        except Exception as e:
            logger.warning("Telegram failed: %s", e)

ROOT = Path(__file__).resolve().parents[1]
VICTORIA_URL = os.getenv("VICTORIA_URL", "http://0.0.0.0:8010")
REPORTS_DIR = ROOT / "docs" / "curator_reports"
TASKS_FILE = ROOT / "scripts" / "curator_tasks.txt"

async def run_curator():
    """Запуск стандартного кураторского прогона"""
    logger.info("🚀 Запуск кураторского прогона...")
    # Используем системный python3, так как в venv какие-то проблемы с соединением
    cmd = ["python3", str(ROOT / "scripts" / "curator_send_tasks_to_victoria.py"), "--file", str(TASKS_FILE), "--async", "--max-wait", "3600"]
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

                    # Отправляем результат само-анализа в ntfy (подробное уведомление)
                    if analysis and analysis != "Нет ответа.":
                        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                        await _ntfy_notify(
                            f"🧠 Victoria Self-Analysis [{now_str}]",
                            analysis[:4000]
                        )

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
