#!/usr/bin/env python3
"""
Мега-дебаты: совет всех экспертов (до 86+) по одной теме.
Каждый эксперт даёт один аргумент ЗА и один ПРОТИВ; результаты агрегируются по отделам и в общую сводку.

Запуск:
  python scripts/mega_debate.py "Принцип: все ответы и доработки только через экспертов"
  python scripts/mega_debate.py "Внедрение семи доработок из PRINCIPLE_EXPERTS_FIRST" --max 20
"""
import asyncio
import os
import sys
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

# Добавляем путь к app
APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")


async def get_all_experts(limit: int = 86):
    """Получить всех активных экспертов (до limit)."""
    try:
        import asyncpg
    except ImportError:
        logger.error("asyncpg не установлен")
        return []
    conn = await asyncpg.connect(DB_URL)
    try:
        rows = await conn.fetch("""
            SELECT id, name, role, department, system_prompt
            FROM experts
            WHERE (is_active IS NULL OR is_active = TRUE)
            ORDER BY department, name
            LIMIT $1
        """, limit)
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def ask_expert_for_against(expert: dict, topic: str) -> dict:
    """Один эксперт: один аргумент ЗА и один ПРОТИВ по теме."""
    name = expert.get("name", "Эксперт")
    role = expert.get("role", "")
    department = expert.get("department", "")
    prompt = f"""Вы {name}, {role} (отдел: {department}).

ТЕМА ДЕБАТОВ: {topic}

Дайте строго в формате:
ЗА: [одно предложение — ваш главный аргумент за]
ПРОТИВ: [одно предложение — ваш главный аргумент против]

Без вступлений, только две строки ЗА: и ПРОТИВ:."""

    try:
        from ai_core import run_smart_agent_async
        out = await run_smart_agent_async(
            prompt,
            expert_name=name,
            category="reasoning",
        )
    except Exception as e:
        logger.debug("ask_expert %s: %s", name, e)
        try:
            from local_router import LocalAIRouter
            router = LocalAIRouter()
            res = await router.run_local_llm(prompt, category="reasoning")
            out = (res[0] if isinstance(res, tuple) and res else res) if res else None
        except Exception:
            out = None
    if not out:
        return {"name": name, "role": role, "department": department, "pro": "", "against": ""}
    pro, against = "", ""
    for line in (out or "").split("\n"):
        line = line.strip()
        if line.upper().startswith("ЗА:") or line.upper().startswith("ЗА "):
            pro = line.split(":", 1)[-1].strip() if ":" in line else line[2:].strip()
        elif line.upper().startswith("ПРОТИВ:") or line.upper().startswith("ПРОТИВ "):
            against = line.split(":", 1)[-1].strip() if ":" in line else line[6:].strip()
    return {"name": name, "role": role, "department": department or "General", "pro": pro or out[:200], "against": against or ""}


async def run_mega_debate(topic: str, max_experts: int = 86, batch_size: int = 10):
    """Запуск мега-дебатов: все эксперты по теме, батчами."""
    experts = await get_all_experts(limit=max_experts)
    if not experts:
        logger.error("Нет экспертов в БД. Проверьте DATABASE_URL.")
        return None
    logger.info("Совет из %d экспертов. Тема: %s", len(experts), topic)
    results = []
    sem = asyncio.Semaphore(batch_size)
    async def ask_with_sem(e):
        async with sem:
            return await ask_expert_for_against(e, topic)
    for i in range(0, len(experts), batch_size):
        batch = experts[i : i + batch_size]
        batch_results = await asyncio.gather(*[ask_with_sem(e) for e in batch], return_exceptions=True)
        for r in batch_results:
            if isinstance(r, Exception):
                logger.warning("Ошибка в батче: %s", r)
                continue
            results.append(r)
        logger.info("Обработано %d / %d", min(i + batch_size, len(experts)), len(experts))
    # Агрегация по отделам
    by_dept = {}
    for r in results:
        dept = r.get("department") or "General"
        if dept not in by_dept:
            by_dept[dept] = []
        by_dept[dept].append(r)
    all_pros = [r["pro"] for r in results if r.get("pro")]
    all_against = [r["against"] for r in results if r.get("against")]
    summary = {
        "topic": topic,
        "total_experts": len(results),
        "by_department": by_dept,
        "all_pros": all_pros,
        "all_against": all_against,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    # Итоговый синтез: вердикт совета по балансу ЗА/ПРОТИВ
    synthesis = ""
    try:
        pros_text = "\n".join(f"- {p}" for p in all_pros[:30] if p)
        against_text = "\n".join(f"- {a}" for a in all_against[:30] if a)
        synthesis_prompt = f"""Тема: {topic}

Аргументы ЗА ({len(all_pros)}):
{pros_text}

Аргументы ПРОТИВ ({len(all_against)}):
{against_text}

Дай краткий вердикт совета экспертов (2–4 предложения): общий баланс ЗА/ПРОТИВ и одну рекомендацию. Без вступлений."""
        from ai_core import run_smart_agent_async
        synthesis = await run_smart_agent_async(synthesis_prompt, expert_name="Виктория", category="reasoning") or ""
    except Exception as e:
        logger.debug("Synthesis skip: %s", e)
    summary["synthesis"] = (synthesis or "").strip()
    return summary


def write_mega_debate_md(summary: dict, out_path: Path):
    """Записать мега-дебаты в Markdown."""
    lines = [
        "# Мега-дебаты: совет экспертов",
        "",
        f"**Тема:** {summary['topic']}",
        f"**Участников:** {summary['total_experts']}",
        f"**Дата:** {summary['timestamp'][:19]}",
        "",
        "---",
        "",
        "## По отделам: ЗА и ПРОТИВ",
        "",
    ]
    for dept, experts in sorted(summary.get("by_department", {}).items()):
        lines.append(f"### {dept}")
        lines.append("")
        for r in experts:
            lines.append(f"- **{r['name']}** ({r['role']}):")
            if r.get("pro"):
                lines.append(f"  - ЗА: {r['pro']}")
            if r.get("against"):
                lines.append(f"  - ПРОТИВ: {r['against']}")
            lines.append("")
        lines.append("")
    lines.extend([
        "---",
        "",
        "## Сводка: все аргументы ЗА",
        "",
    ])
    for p in summary.get("all_pros", [])[:50]:
        if p:
            lines.append(f"- {p}")
    lines.extend(["", "## Сводка: все аргументы ПРОТИВ", ""])
    for a in summary.get("all_against", [])[:50]:
        if a:
            lines.append(f"- {a}")
    if summary.get("synthesis"):
        lines.extend(["", "---", "", "## Вердикт совета", "", summary["synthesis"], ""])
    lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Записано: %s", out_path)


def main():
    import argparse
    p = argparse.ArgumentParser(description="Мега-дебаты: совет всех экспертов")
    p.add_argument("topic", nargs="?", default="Принцип «всё через экспертов»: ответы и доработки только силами экспертов с знаниями, скиллами и интернетом.", help="Тема дебатов")
    p.add_argument("--max", type=int, default=86, help="Макс. число экспертов (по умолчанию 86)")
    p.add_argument("--batch", type=int, default=10, help="Размер батча параллельных вызовов")
    p.add_argument("--out", default=None, help="Путь к выходному .md (по умолчанию knowledge_os/docs/MEGA_DEBATE_<date>.md)")
    args = p.parse_args()
    summary = asyncio.run(run_mega_debate(args.topic, max_experts=args.max, batch_size=args.batch))
    if not summary:
        return 1
    out = args.out
    if not out:
        date = datetime.now().strftime("%Y%m%d_%H%M")
        out = Path(__file__).resolve().parents[1] / "docs" / f"MEGA_DEBATE_{date}.md"
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_mega_debate_md(summary, out)
    # JSON для программного использования
    json_path = out.with_suffix(".json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    logger.info("JSON: %s", json_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
