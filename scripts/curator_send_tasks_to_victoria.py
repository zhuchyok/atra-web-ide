#!/usr/bin/env python3
"""
Куратор Victoria: отправить список задач Victoria, сохранить ответы и трассировку для анализа.

Использование:
  python3 scripts/curator_send_tasks_to_victoria.py
  python3 scripts/curator_send_tasks_to_victoria.py --tasks "привет" "статус проекта"
  python3 scripts/curator_send_tasks_to_victoria.py --file scripts/curator_tasks.txt
  python3 scripts/curator_send_tasks_to_victoria.py --max-wait 120

Результат: docs/curator_reports/curator_YYYY-MM-DD_HH-MM-SS.json (и .md превью).
Cursor-агент может читать отчёт и писать выводы в FINDINGS.

Таймаут среды запуска (VERIFICATION §3, §5): при запуске из IDE/CI/runner с ограничением
времени задавать timeout не меньше: для --quick ≥ 10 мин (600000 ms), для полного прогона
(5 задач) ≥ 30 мин. Иначе процесс будет убит по внешнему лимиту до завершения. См. CURATOR_RUNBOOK §1.
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import requests
except ImportError:
    print("pip install requests")
    sys.exit(1)

VICTORIA_URL = os.getenv("VICTORIA_URL", "http://localhost:8010")
REPORTS_DIR = ROOT / "docs" / "curator_reports"
SYNC_TIMEOUT = int(os.getenv("CURATOR_SYNC_TIMEOUT", "300"))
# Таймаут первого POST /run при async: до 202 Victoria выполняет стратегию и understand_goal (LLM); холодный старт может 3–5 мин
POST_RUN_TIMEOUT = int(os.getenv("CURATOR_POST_RUN_TIMEOUT", "300"))
POLL_INTERVAL = 2.5
DEFAULT_TASKS = [
    "привет",
    "какой статус проекта?",
    "покажи список файлов в корне проекта",
    "что ты умеешь?",
]


def check_health(url: str) -> bool:
    try:
        r = requests.get(f"{url}/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def run_sync(url: str, goal: str, project_context: str = "atra-web-ide", max_steps: int = 50) -> dict:
    """Синхронный POST /run (без async_mode). Возвращает полный ответ с correlation_id и knowledge."""
    payload = {"goal": goal, "max_steps": max_steps, "project_context": project_context}
    try:
        r = requests.post(f"{url}/run", json=payload, params={"async_mode": "false"}, timeout=SYNC_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.Timeout:
        return {"status": "error", "error": "timeout", "output": None, "knowledge": None, "correlation_id": None}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "error": str(e), "output": None, "knowledge": None, "correlation_id": None}
    except Exception as e:
        return {"status": "error", "error": str(e), "output": None, "knowledge": None, "correlation_id": None}


def run_async_poll(url: str, goal: str, project_context: str, max_steps: int, max_wait: float) -> dict:
    """POST async_mode=true, затем опрос GET /run/status/{task_id}. Возвращает тот же формат что и sync."""
    payload = {"goal": goal, "max_steps": max_steps, "project_context": project_context}
    try:
        r = requests.post(f"{url}/run", json=payload, params={"async_mode": "true"}, timeout=POST_RUN_TIMEOUT)
        if r.status_code != 202:
            r.raise_for_status()
        data = r.json()
        task_id = data.get("task_id")
        correlation_id = data.get("correlation_id")
        if not task_id:
            return {"status": "error", "error": "202 without task_id", "output": None, "knowledge": None, "correlation_id": correlation_id}
        deadline = time.monotonic() + max_wait
        poll_get_retries = 3  # повторы GET при connection reset, чтобы не терять задачу
        last_log = 0.0
        while time.monotonic() < deadline:
            s = None
            last_err = None
            for _ in range(poll_get_retries):
                try:
                    s = requests.get(f"{url}/run/status/{task_id}", timeout=10)
                    last_err = None
                    break
                except requests.exceptions.RequestException as e:
                    last_err = e
                    err_str = str(e).lower()
                    if "connection" in err_str or "reset" in err_str or "aborted" in err_str:
                        time.sleep(2)
                        continue
                    raise
            if last_err is not None:
                raise last_err
            if s.status_code != 200:
                time.sleep(POLL_INTERVAL)
                continue
            rec = s.json()
            st = rec.get("status", "")
            # Прогресс раз в 15 сек, чтобы видеть что не зависли
            now = time.monotonic()
            if now - last_log >= 15.0:
                elapsed = int(deadline - now)
                print(f"      ... ждём Victoria (status={st}, осталось ~{elapsed}s)")
                last_log = now
            if st == "completed":
                out = rec.get("output") or ""
                know = rec.get("knowledge") or {}
                if correlation_id is None:
                    correlation_id = rec.get("correlation_id")
                return {"status": "success", "output": out, "knowledge": know, "correlation_id": correlation_id}
            if st == "failed":
                return {"status": "error", "error": rec.get("error", "failed"), "output": None, "knowledge": rec.get("knowledge"), "correlation_id": correlation_id}
            time.sleep(POLL_INTERVAL)
        return {"status": "error", "error": "poll timeout", "output": None, "knowledge": None, "correlation_id": correlation_id}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "error": str(e), "output": None, "knowledge": None, "correlation_id": None}
    except Exception as e:
        return {"status": "error", "error": str(e), "output": None, "knowledge": None, "correlation_id": None}


def main():
    import argparse
    p = argparse.ArgumentParser(description="Куратор: отправить задачи Victoria и сохранить отчёт")
    p.add_argument("--tasks", nargs="*", help="Цели (по одной); если не задано — встроенный список")
    p.add_argument("--file", type=str, help="Файл с целями (одна на строку)")
    p.add_argument("--async", dest="async_mode", action="store_true", help="Использовать async 202 + poll")
    p.add_argument("--max-wait", type=float, default=360.0, help="Макс. сек ожидания при async (по умолчанию 360)")
    p.add_argument("--quick", action="store_true", help="Быстрый прогон: только 2 задачи, max-wait 180 с (для проверки)")
    p.add_argument("--project", type=str, default=os.getenv("PROJECT_CONTEXT", "atra-web-ide"), help="project_context")
    args = p.parse_args()

    if args.quick:
        args.max_wait = 180.0

    if args.file:
        path = Path(args.file)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            print(f"❌ Файл не найден: {path}")
            sys.exit(1)
        tasks = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not tasks:
            print("❌ В файле нет непустых строк с задачами.")
            sys.exit(1)
    elif args.tasks:
        tasks = args.tasks
    else:
        tasks = DEFAULT_TASKS

    if args.quick and len(tasks) > 2:
        tasks = tasks[:2]
        print("--quick: только первые 2 задачи, max-wait 180 с")

    print(f"Задач: {len(tasks)}, макс. ожидание на задачу: {args.max_wait:.0f} с (одна задача ~1–5 мин на Mac Studio)")
    if args.async_mode:
        print("Режим: async (202 + опрос /run/status каждые 2.5 с, прогресс раз в 15 с)")

    if not check_health(VICTORIA_URL):
        print(f"❌ Victoria недоступна: {VICTORIA_URL}")
        print("   Запустите: docker compose -f knowledge_os/docker-compose.yml up -d victoria-agent")
        sys.exit(1)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    report_json = REPORTS_DIR / f"curator_{ts}.json"
    report_md = REPORTS_DIR / f"curator_{ts}.md"

    results = []
    for i, goal in enumerate(tasks, 1):
        print(f"[{i}/{len(tasks)}] {goal[:60]}...")
        start = time.perf_counter()
        if args.async_mode:
            out = run_async_poll(VICTORIA_URL, goal, args.project, max_steps=50, max_wait=args.max_wait)
        else:
            out = run_sync(VICTORIA_URL, goal, args.project, max_steps=50)
        # До двух повторов при обрыве соединения или read timeout (холодный старт Victoria)
        for _retry in range(2):
            if out.get("status") != "error" or not out.get("error"):
                break
            err_str = str(out.get("error")).lower()
            if "connection" not in err_str and "reset" not in err_str and "aborted" not in err_str and "timed out" not in err_str:
                break
            print("    повтор через 3 с (обрыв соединения или таймаут)...")
            time.sleep(3)
            if args.async_mode:
                out = run_async_poll(VICTORIA_URL, goal, args.project, max_steps=50, max_wait=args.max_wait)
            else:
                out = run_sync(VICTORIA_URL, goal, args.project, max_steps=50)
        elapsed = time.perf_counter() - start
        trace = (out.get("knowledge") or {}).get("execution_trace") or (out.get("knowledge") or {})
        rec = {
            "goal": goal,
            "status": out.get("status"),
            "error": out.get("error"),
            "output_preview": (out.get("output") or "")[:500] if out.get("output") else None,
            "output_length": len(out.get("output") or ""),
            "correlation_id": out.get("correlation_id"),
            "execution_trace": trace,
            "elapsed_seconds": round(elapsed, 2),
        }
        results.append(rec)
        print(f"    -> {rec['status']} ({elapsed:.1f}s) correlation_id={ (rec.get('correlation_id') or '')[:8]}")

    report = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "victoria_url": VICTORIA_URL,
        "project_context": args.project,
        "async_mode": args.async_mode,
        "tasks_count": len(tasks),
        "results": results,
    }
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        f"# Кураторский прогон {ts}",
        "",
        f"- Victoria: {VICTORIA_URL}",
        f"- Задач: {len(tasks)}",
        "",
        "## Результаты",
        "",
    ]
    for r in results:
        md_lines.append(f"### {r['goal'][:80]}")
        md_lines.append(f"- **Статус:** {r['status']}")
        md_lines.append(f"- **Время:** {r['elapsed_seconds']} с")
        if r.get("correlation_id"):
            md_lines.append(f"- **correlation_id:** {r['correlation_id']}")
        if r.get("execution_trace"):
            md_lines.append(f"- **Трассировка:** `{json.dumps(r['execution_trace'], ensure_ascii=False)[:200]}...`")
        if r.get("output_preview"):
            md_lines.append(f"- **Превью ответа:** {r['output_preview'][:300]}...")
        md_lines.append("")
    report_md.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"\n✅ Отчёт сохранён: {report_json}")
    print(f"   Превью: {report_md}")
    print("   Куратор (Cursor) может проанализировать отчёт и записать выводы в docs/curator_reports/FINDINGS_*.md")


if __name__ == "__main__":
    main()
