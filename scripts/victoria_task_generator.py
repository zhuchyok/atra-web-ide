"""
victoria_task_generator.py — Замкнутый цикл самогенерации задач.

Victoria читает свои отчёты и сама решает что проверить дальше:
  1. Если нашла ПРОБЛЕМА → добавляет углублённый аудит файла
  2. Если файл ОК → расширяет проверку на соседние файлы в той же директории
  3. Если в отчёте есть листинг директории → добавляет новые .py файлы в очередь
  4. Дедуплицирует против текущего curator_tasks.txt
  5. Дописывает новые задачи (max NEW_TASKS_PER_RUN)
  6. Уведомляет через ntfy

Запуск: python3 scripts/victoria_task_generator.py
        python3 scripts/victoria_task_generator.py --dry-run  # без записи
"""

import asyncio
import httpx
import json
import os
import re
import logging
from pathlib import Path
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s]: %(message)s")
logger = logging.getLogger("task_generator")

ROOT = Path(__file__).resolve().parents[1]
TASKS_FILE = ROOT / "scripts" / "curator_tasks.txt"
REPORTS_DIR = ROOT / "docs" / "curator_reports"

# Сколько новых задач добавлять за один прогон.
# FAST_ACTION_PATH обрабатывает каждую за ~0ms (прямое чтение файла без LLM),
# поэтому 20 задач добавляют ~2-3 секунды к общему времени прогона.
NEW_TASKS_PER_RUN = 20

# Уведомления
NTFY_URL = os.getenv("NTFY_URL", "")
TG_TOKEN = os.getenv("TG_TOKEN", "")
TG_CHAT_ID = os.getenv("TG_CHAT_ID", "")
TG_PROXY = os.getenv("TG_PROXY", "")

# Шаблоны для новых audit-задач по типу файла
AUDIT_TEMPLATES = {
    "pip_check": "проверь файл {path} — есть ли там pip install в рантайме (subprocess pip или os.system pip)? Ответь: ОК или ПРОБЛЕМА + цитата",
    "secret_check": "проверь файл {path} — есть ли там hardcoded секреты или пароли в первых 30 строках? Ответь: ОК или ПРОБЛЕМА + цитата",
    "deep_audit": "прочитай файл {path} — найди потенциальные проблемы: subprocess calls, hardcoded URLs, eval(), exec(). Ответь: ОК или ПРОБЛЕМА + список",
}

# Файлы которые всегда скипаем (слишком большие или нерелевантные)
SKIP_FILES = {
    "victoria_server.py",  # уже проверяем отдельно
    "__init__.py",
    "main.py",  # точка входа, не аудируем
    "config.py",
}

# Приоритетные файлы для расширения (часто меняются)
PRIORITY_PATTERNS = [
    "worker", "executor", "agent", "researcher", "orchestrat",
]


async def notify(text: str) -> None:
    """ntfy → TG fallback."""
    if NTFY_URL:
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                await asyncio.wait_for(
                    c.post(NTFY_URL, content=text.encode(),
                           headers={"Title": "Victoria Task Generator"}),
                    timeout=5.0
                )
            return
        except Exception as e:
            logger.debug("ntfy failed: %s", e)
    if TG_TOKEN and TG_CHAT_ID:
        try:
            kw = {"proxy": TG_PROXY} if TG_PROXY else {}
            async with httpx.AsyncClient(timeout=5.0, **kw) as c:
                await asyncio.wait_for(
                    c.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                           json={"chat_id": TG_CHAT_ID, "text": text[:4000]}),
                    timeout=6.0
                )
        except Exception as e:
            logger.debug("TG failed: %s", e)


def load_latest_report() -> dict | None:
    """Загружает последний JSON отчёт куратора."""
    jsons = sorted(REPORTS_DIR.glob("curator_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not jsons:
        logger.warning("Нет JSON отчётов в %s", REPORTS_DIR)
        return None
    report = json.loads(jsons[0].read_text())
    logger.info("Загружен отчёт: %s (%d задач)", jsons[0].name, report.get("tasks_count", 0))
    return report


def load_existing_tasks() -> list[str]:
    """Читает текущий список задач куратора."""
    if not TASKS_FILE.exists():
        return []
    return [t.strip() for t in TASKS_FILE.read_text().splitlines() if t.strip()]


def extract_checked_files(results: list[dict]) -> dict[str, list[str]]:
    """
    Извлекает пути файлов из задач отчёта.
    Возвращает: {container_path: [task_type, ...]}
    """
    checked: dict[str, list[str]] = {}
    path_re = re.compile(r'/(?:app|workspace/atra-web-ide)[^\s,—–]+\.py')

    for r in results:
        goal = r.get("goal", "")
        for m in path_re.finditer(goal):
            path = m.group(0).rstrip(".,?!")
            if path not in checked:
                checked[path] = []
            if "pip install" in goal or "subprocess" in goal:
                checked[path].append("pip_check")
            elif "hardcoded" in goal or "секрет" in goal or "пароль" in goal:
                checked[path].append("secret_check")
            else:
                checked[path].append("other")

    return checked


def extract_problems(results: list[dict]) -> list[str]:
    """Возвращает пути файлов где была ПРОБЛЕМА."""
    problems = []
    path_re = re.compile(r'/(?:app|workspace/atra-web-ide)[^\s,—–]+\.py')

    for r in results:
        output = str(r.get("output_preview", ""))
        if "ПРОБЛЕМА" in output:
            goal = r.get("goal", "")
            for m in path_re.finditer(goal):
                path = m.group(0).rstrip(".,?!")
                if path not in problems:
                    problems.append(path)
    return problems


def extract_listed_files(results: list[dict]) -> list[str]:
    """Извлекает .py файлы из результатов листинга директорий."""
    found = []
    for r in results:
        goal = r.get("goal", "")
        output = str(r.get("output_preview", ""))
        if "список файлов" in goal or "list" in goal.lower():
            # Парсим пути из output
            dir_re = re.compile(r'/(?:app|workspace/atra-web-ide)[^\s\n]+')
            for m in dir_re.finditer(goal):
                base_dir = m.group(0).rstrip(".,)")
                # Ищем .py файлы в output
                for line in output.splitlines():
                    line = line.strip()
                    if line.endswith(".py") and line not in SKIP_FILES:
                        container_path = f"{base_dir}/{line}".replace("//", "/")
                        found.append(container_path)
    return found


def find_neighbor_files(checked_paths: list[str]) -> list[str]:
    """
    Для каждого проверенного контейнерного пути находим соседей.
    Контейнерный путь /app/knowledge_os/app/X.py → хостовый knowledge_os/app/
    """
    candidates = []

    for cpath in checked_paths:
        # Конвертируем контейнерный путь в хостовый
        if cpath.startswith("/app/"):
            host_rel = cpath[5:]  # убираем /app/
        elif cpath.startswith("/workspace/atra-web-ide/"):
            host_rel = cpath[len("/workspace/atra-web-ide/"):]
        else:
            continue

        host_path = ROOT / host_rel
        host_dir = host_path.parent

        if not host_dir.exists():
            continue

        # Соседние .py файлы в той же директории
        for sibling in sorted(host_dir.glob("*.py")):
            if sibling.name in SKIP_FILES:
                continue

            # Строим контейнерный путь для соседа
            rel = sibling.relative_to(ROOT)
            rel_parts = rel.parts
            # knowledge_os/app/X.py → /app/knowledge_os/app/X.py
            # src/agents/bridge/X.py → /app/src/agents/bridge/X.py
            container = "/app/" + "/".join(rel_parts)
            candidates.append(container)

    return candidates


def rank_candidates(candidates: list[str]) -> list[str]:
    """Приоритизирует кандидатов по значимости."""
    def score(path: str) -> int:
        name = Path(path).stem.lower()
        s = 0
        for pattern in PRIORITY_PATTERNS:
            if pattern in name:
                s += 10
        # Аудит-файлы важнее
        if any(x in name for x in ["audit", "security", "secret"]):
            s += 5
        return -s  # меньше = важнее

    return sorted(set(candidates), key=score)


def generate_new_tasks(
    problems: list[str],
    unchecked: list[str],
    existing_tasks: list[str],
    max_new: int,
) -> list[str]:
    """Генерирует список новых задач для добавления."""
    new_tasks = []
    existing_lower = {t.lower() for t in existing_tasks}

    # 1. Для файлов с ПРОБЛЕМА — добавляем углублённый аудит
    for path in problems:
        task = AUDIT_TEMPLATES["deep_audit"].format(path=path)
        if task.lower() not in existing_lower:
            new_tasks.append(task)
            logger.info("+ углублённый аудит (ПРОБЛЕМА): %s", path)

    if len(new_tasks) >= max_new:
        return new_tasks[:max_new]

    # 2. Для непроверенных файлов — pip и secret check (чередуем)
    for i, path in enumerate(unchecked):
        if len(new_tasks) >= max_new:
            break

        tpl_key = "pip_check" if i % 2 == 0 else "secret_check"
        task = AUDIT_TEMPLATES[tpl_key].format(path=path)

        if task.lower() not in existing_lower:
            new_tasks.append(task)
            existing_lower.add(task.lower())  # не дублируем в рамках одного прогона
            logger.info("+ новая задача (%s): %s", tpl_key, Path(path).name)

    return new_tasks[:max_new]


def get_recently_changed_files(hours: int = 48) -> list[str]:
    """
    Возвращает контейнерные пути .py файлов изменённых в git за последние N часов.
    Эти файлы получают приоритет в аудите — любой коммит автоматически под проверку.
    """
    import subprocess
    try:
        result = subprocess.run(
            ["git", "log", f"--since={hours} hours ago", "--name-only",
             "--pretty=format:", "--diff-filter=AM"],
            cwd=ROOT, capture_output=True, text=True, timeout=10
        )
        changed = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.endswith(".py") and Path(ROOT / line).exists():
                name = Path(line).name
                if name in SKIP_FILES:
                    continue
                # Конвертируем в контейнерный путь
                container = "/app/" + line
                changed.append(container)
        return list(dict.fromkeys(changed))  # дедупликация с сохранением порядка
    except Exception as e:
        logger.debug("git log failed: %s", e)
        return []


def get_stable_ok_tasks(existing_tasks: list[str], min_reports: int = 3) -> set[str]:
    """
    Возвращает задачи которые дали ОК в последних min_reports отчётах подряд.
    Эти задачи можно убрать из ежедневной ротации — они «выпускные».
    """
    jsons = sorted(REPORTS_DIR.glob("curator_*.json"),
                   key=lambda p: p.stat().st_mtime, reverse=True)[:min_reports]

    if len(jsons) < min_reports:
        return set()  # Недостаточно истории

    # Для каждой задачи считаем сколько отчётов подряд она была ОК
    task_ok_count: dict[str, int] = {}
    for report_file in jsons:
        data = json.loads(report_file.read_text())
        for r in data.get("results", []):
            goal = r.get("goal", "").strip()
            output = str(r.get("output_preview", ""))
            if goal not in task_ok_count:
                task_ok_count[goal] = 0
            if "ПРОБЛЕМА" not in output and r.get("status") == "success":
                task_ok_count[goal] += 1

    # Задачи ОК во всех min_reports отчётах
    stable = {task for task, count in task_ok_count.items() if count >= min_reports}

    # НЕ ротируем системные (не-аудитные) задачи — они нужны всегда
    keep_always = {"привет", "какой статус проекта", "что ты умеешь", "напиши одну строку"}
    stable = {t for t in stable if not any(k in t.lower() for k in keep_always)}

    return stable


async def main(dry_run: bool = False) -> None:
    report = load_latest_report()
    if not report:
        logger.error("Нет отчёта для анализа")
        return

    results = report.get("results", [])
    existing_tasks = load_existing_tasks()

    # --- РОТАЦИЯ: убираем задачи которые стабильно ОК (3+ отчёта) ---
    stable_ok = get_stable_ok_tasks(existing_tasks, min_reports=3)
    if stable_ok:
        logger.info("Ротация: убираем %d стабильных ОК-задач", len(stable_ok))
        tasks_after_rotation = [t for t in existing_tasks if t not in stable_ok]
    else:
        tasks_after_rotation = existing_tasks

    # Анализируем отчёт
    checked_files = extract_checked_files(results)
    problems = extract_problems(results)
    listed_files = extract_listed_files(results)

    logger.info("Проверено файлов: %d | Проблем: %d | Из листинга: %d",
                len(checked_files), len(problems), len(listed_files))

    # Находим соседей проверенных файлов
    all_checked = list(checked_files.keys()) + listed_files
    neighbors = find_neighbor_files(all_checked)

    # --- GIT DIFF: файлы изменённые за последние 7 дней — приоритет #1 ---
    recently_changed = get_recently_changed_files(hours=168)
    if recently_changed:
        logger.info("Git-изменения за 48ч: %d файлов", len(recently_changed))

    # Убираем уже проверяемые (включая оставшиеся после ротации)
    existing_lower = {t.lower() for t in tasks_after_rotation}
    checked_set = {p.lower() for p in checked_files.keys()}
    unchecked = [
        p for p in rank_candidates(neighbors)
        if p.lower() not in checked_set
        and not any(p.lower() in t.lower() for t in tasks_after_rotation)
    ]

    # Git-изменённые файлы — в начало очереди (не дублируем уже проверяемые)
    git_priority = [
        p for p in recently_changed
        if not any(p.lower() in t.lower() for t in tasks_after_rotation)
    ]
    unchecked = git_priority + [p for p in unchecked if p not in git_priority]

    if git_priority:
        logger.info("Git-приоритет: %d файлов встали первыми в очередь", len(git_priority))

    logger.info("Кандидаты для расширения: %d", len(unchecked))

    # Генерируем новые задачи
    new_tasks = generate_new_tasks(problems, unchecked, tasks_after_rotation, NEW_TASKS_PER_RUN)

    rotated_count = len(existing_tasks) - len(tasks_after_rotation)
    final_tasks = tasks_after_rotation + new_tasks
    total_new = len(new_tasks)
    total_final = len(final_tasks)

    if not new_tasks and not stable_ok:
        logger.info("Новых задач не найдено — все соседи уже покрыты")
        await notify("Victoria Task Generator: все соседи уже покрыты, новых задач нет.")
        return

    logger.info("Ротировано: -%d | Добавлено: +%d | Итого: %d",
                rotated_count, total_new, total_final)
    for t in new_tasks:
        logger.info("  + %s", t[:80])

    if dry_run:
        logger.info("[DRY-RUN] Запись пропущена")
        return

    # Перезаписываем curator_tasks.txt (ротация + новые)
    TASKS_FILE.write_text("\n".join(final_tasks) + "\n")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    summary = "\n".join(
        f"  • {Path(t.split(' — ')[0].split()[-1]).name if '/' in t else t[:60]}"
        for t in new_tasks[:10]
    )
    msg = (
        f"Victoria Task Generator [{now}]\n"
        f"Ротация: -{rotated_count} стабильных ОК\n"
        f"Добавлено: +{total_new} новых задач:\n{summary}\n"
        f"Очередь: {total_final} задач"
    )
    await notify(msg)
    logger.info("Готово. curator_tasks.txt: %d → %d задач (-%d ротировано, +%d новых)",
                len(existing_tasks), total_final, rotated_count, total_new)
    logger.info("Готово. curator_tasks.txt: %d → %d задач",
                len(existing_tasks), len(existing_tasks) + len(new_tasks))


if __name__ == "__main__":
    import sys
    dry = "--dry-run" in sys.argv
    asyncio.run(main(dry_run=dry))
