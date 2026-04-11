"""
ATRA Daily Summary Report
Собирает метрики за последние 7 отчётов и отправляет дайджест в NTFY.
Сгенерировано: Victoria (victoria-wisdom-v3.5) via Ollama — руки выполнили работу.
"""
from pathlib import Path
import json
import os
import httpx
from collections import Counter
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "docs" / "curator_reports"
PATCHES_FILE = ROOT / "trusted_patches_applied.jsonl"
TASKS_FILE = ROOT / "scripts" / "curator_tasks.txt"
NTFY_URL = os.getenv("NTFY_URL", "")


def get_last_reports() -> list:
    """Получает отчёты за последние 3 дня (не более 10)."""
    if not REPORTS_DIR.exists():
        return []
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=3)
    files = sorted(
        REPORTS_DIR.glob("curator_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    # Берём не старше 3 дней, максимум 10
    recent = [f for f in files if datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc) >= cutoff]
    return recent[:10] if recent else files[:3]  # fallback — хотя бы 3 последних


def analyze_reports(files: list) -> tuple:
    """Извлекает метрики из отчётов."""
    tasks_done = 0
    problems = 0
    files_modified: Counter = Counter()

    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)

            # Формат v1: явные поля tasks_completed / problems_found
            if "tasks_completed" in data:
                tasks_done += data.get("tasks_completed", 0)
                problems += data.get("problems_found", 0)
            else:
                # Формат v2 (текущий): считаем из results[].status
                for r in data.get("results", []):
                    st = r.get("status", "")
                    if st == "success":
                        tasks_done += 1
                    elif st in ("error", "failed"):
                        problems += 1

            for fname in data.get("modified_files", []):
                files_modified[fname] += 1
        except (json.JSONDecodeError, IOError):
            continue

    top_files = files_modified.most_common(3)
    return tasks_done, problems, top_files


def count_patches() -> int:
    """Считает применённые патчи из журнала (если есть) или из FINDINGS-файлов."""
    if PATCHES_FILE.exists():
        count = 0
        with open(PATCHES_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    count += 1
        return count
    # Fallback: считаем количество FINDINGS-файлов как прокси "работы сделано"
    findings_dir = ROOT / "docs" / "curator_reports"
    return len(list(findings_dir.glob("FINDINGS_*.md")))


def count_queue() -> int:
    """Считает задачи в очереди куратора."""
    if not TASKS_FILE.exists():
        return 0
    with open(TASKS_FILE, "r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip() and not line.startswith("#"))


def generate_digest() -> str:
    """Формирует текстовый дайджест для отправки."""
    reports = get_last_reports()
    tasks_done, problems, top_files = analyze_reports(reports)
    patches = count_patches()
    queue = count_queue()

    top_str = ", ".join(Path(f[0]).name for f in top_files) if top_files else "—"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"📊 ATRA Daily Summary ({now})",
        f"📈 Задач выполнено (success): {tasks_done}",
        f"🐛 Ошибок в задачах (error): {problems}",
        f"📋 Findings/патчей: {patches}",
        f"⏳ Очередь задач: {queue}",
        f"📁 Топ файлов: {top_str}",
        f"📂 Отчётов проанализировано: {len(reports)}",
    ]

    # Детали последнего отчёта
    if reports:
        try:
            with open(reports[0], "r", encoding="utf-8") as fp:
                last = json.load(fp)
            last_results = last.get("results", [])
            if last_results:
                last_ok = sum(1 for r in last_results if r.get("status") == "success")
                last_err = sum(1 for r in last_results if r.get("status") in ("error", "failed"))
                last_ts = last.get("ts", "?")
                lines.append(f"\n🕐 Последний прогон [{last_ts}]:")
                lines.append(f"   ✅ {last_ok} успешных / ❌ {last_err} ошибок из {len(last_results)}")
        except Exception:
            pass

    # Добавляем последние FINDINGS если есть
    findings_dir = ROOT / "docs" / "curator_reports"
    findings_files = sorted(
        findings_dir.glob("FINDINGS_*.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )[:2]
    if findings_files:
        lines.append("")
        lines.append("🔍 Последние находки:")
        for f in findings_files:
            try:
                content = f.read_text(encoding="utf-8").strip()
                first_lines = [ln for ln in content.splitlines() if ln.strip()][:3]
                lines.append(f"  [{f.name}]")
                for ln in first_lines:
                    lines.append(f"  {ln[:120]}")
            except Exception:
                pass

    return "\n".join(lines)


def send_report(msg: str) -> None:
    """Отправляет отчёт в NTFY или выводит в stdout."""
    if NTFY_URL:
        try:
            # trust_env=False — отключаем ALL_PROXY из env (socks5h без httpx-socks даёт gaierror)
            with httpx.Client(trust_env=False, timeout=5.0) as client:
                client.post(
                    NTFY_URL,
                    content=msg.encode(),
                    headers={"Title": "ATRA Daily Summary", "Priority": "default"},
                )
            print(f"Отчёт отправлен в {NTFY_URL}")
        except Exception as e:
            print(f"NTFY недоступен ({e}), вывожу в stdout:")
            print(msg)
    else:
        print(msg)


if __name__ == "__main__":
    digest = generate_digest()
    send_report(digest)
