"""Self-Dev Loop — замкнутый контур саморазработки ATRA.

Цикл (запуск launchd каждые 2 часа или вручную):
  1. Берёт из tasks задачу с metadata->>'source'='dev_loop' (status=pending).
  2. Просит Victoria-wisdom сгенерировать unified diff для задачи.
  3. Применяет патч в ISOLIRОВАННОМ git-worktree на ветке auto/dev-loop
     (рабочая копия main неприкосновенна — урок с App.svelte).
  4. Прогоняет проверки: синтаксис py, vite build (если трогали frontend),
     compile всех изменённых .py.
  5. Зелёный  -> коммит в auto/dev-loop + Telegram «готово к ревью»,
     Красный   -> откат ветки + честный отчёт.

Merge в main — ТОЛЬКО человеком. Скрипт никогда не пушит и не мержит.

Запуск: python3 scripts/self_dev_loop.py [--task-id <uuid>]
"""
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import psycopg2

REPO = Path(__file__).resolve().parent.parent
BRANCH = "auto/dev-loop"
WORKTREE = REPO / ".selfdev-worktree"
STATE_PATH = REPO / "logs" / "self_dev_state.json"
DB_DSN = os.environ.get("ATRA_DB_DSN", "postgresql://admin:secret@127.0.0.1:6432/knowledge_os")  # pragma: allowlist secret
MLX_URL = os.environ.get("MLX_BASE_URL", "http://127.0.0.1:11435").rstrip("/")
WISDOM_MODEL = os.getenv("WISDOM_MODEL", "victoria-wisdom-24k")

# Пути, которые автономному патчеру трогать запрещено
FORBIDDEN_PREFIXES = (
    ".env", ".github/", "infrastructure/launchd/", "certs/", "logs/",
    "frontend/node_modules", ".git", "scripts/security_incident_responder.py",
    "scripts/self_dev_loop.py",
)


def log(line: str) -> None:
    print(line, flush=True)


def notify_telegram(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_USER_ID")
    if not token or not chat_id:
        return
    try:
        import urllib.parse

        data = urllib.parse.urlencode({"chat_id": chat_id, "text": text[:3500]}).encode()
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=10
        )
    except Exception as e:
        log(f"telegram error: {e}")


def db_fetch_task(task_id: str | None) -> dict | None:
    conn = psycopg2.connect(DB_DSN)
    try:
        with conn.cursor() as cur:
            if task_id:
                cur.execute(
                    """SELECT id, title, description, COALESCE(metadata->>'patch_attempts','0') FROM tasks
                       WHERE id=%s AND metadata->>'source'='dev_loop' AND status='pending'""",
                    (task_id,),
                )
            else:
                cur.execute(
                    """SELECT id, title, description, COALESCE(metadata->>'patch_attempts','0') FROM tasks
                       WHERE metadata->>'source'='dev_loop' AND status='pending'
                       ORDER BY created_at ASC LIMIT 1"""
                )
            row = cur.fetchone()
            return {"id": str(row[0]), "title": row[1], "description": row[2], "attempts": int(row[3] or 0)} if row else None
    finally:
        conn.close()


def db_finish_task(task_id: str, status: str, result: str) -> None:
    conn = psycopg2.connect(DB_DSN)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE tasks SET status=%s, result=%s, updated_at=NOW() WHERE id=%s",
                (status, result[:5000], task_id),
            )
        conn.commit()
    finally:
        conn.close()


def git(*args: str, cwd: Path = REPO) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args[:2])}: {r.stderr.strip()[:300]}")
    return r.stdout.strip()


def ensure_worktree() -> Path:
    """Отдельный worktree на ветке auto/dev-loop; main неприкосновенен."""
    if WORKTREE.exists():
        return WORKTREE
    branches = git("branch", "--list", BRANCH)
    if BRANCH in branches:
        git("worktree", "add", str(WORKTREE), BRANCH)
    else:
        git("worktree", "add", "-b", BRANCH, str(WORKTREE))
    return WORKTREE


def reset_worktree() -> None:
    git("checkout", "--", ".", cwd=WORKTREE)
    git("reset", "--hard", "main", cwd=WORKTREE)


def ask_victoria_patch(task: dict) -> str | None:
    """Просит Victoria-wisdom сгенерировать unified diff. Возвращает diff или None."""
    prompt = (
        "Ты — аккуратный разработчик проекта ATRA (репозиторийatra-web-ide).\n"
        f"ЗАДАЧА: {task['title']}\n\n{task['description'][:1500]}\n\n"
        "Ответь ТОЛЬКО одним unified diff (формат git apply: строки @@ -a,b +c,d @@).\n"
        "Без пояснений, без markdown-блоков, только сам diff.\n"
        "Если задача слишком крупная — верни ровно слово: TOO_BIG\n"
        "Если не хватает контекста — верни ровно слово: NEED_CONTEXT"
    )
    body = json.dumps({
        "model": WISDOM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "max_tokens": 2048,
        "options": {"temperature": 0.2, "num_predict": 2048},
    }).encode()
    req = urllib.request.Request(
        f"{MLX_URL}/api/chat", data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=420) as resp:
            content = json.loads(resp.read())["message"]["content"].strip()
    except Exception as e:
        log(f"MLX ошибка: {e}")
        return None

    if content.strip() in ("TOO_BIG", "NEED_CONTEXT"):
        log(f"Victoria: {content.strip()}")
        return None
    m = re.search(r"```(?:diff)?\s*\n(.*?)\n```", content, re.DOTALL)
    diff = (m.group(1) if m else content).strip()
    return diff if diff.startswith("---") or "@@" in diff else None


def forbidden_touched(diff: str) -> bool:
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:].strip()
            if any(path == p or path.startswith(p) for p in FORBIDDEN_PREFIXES):
                log(f"❌ Патч трогает запрещённый путь: {path}")
                return True
    return False


def _normalize_diff(diff: str) -> str:
    """Чинит типичные дефекты LLM-диффов: хвост без \n и неверные счётчики hunk."""
    if not diff.endswith("\n"):
        diff += "\n"

    def fix(match: re.Match) -> str:
        body: list[str] = []
        for line in diff[match.end():].splitlines():
            if line.startswith(("@@", "diff --git", "--- ", "+++ ", "index ")):
                break
            body.append(line)
        adds = sum(1 for l in body if l.startswith("+"))
        dels = sum(1 for l in body if l.startswith("-"))
        return f"@@ -{match.group(1) or 0},{dels} +{match.group(3) or 0},{adds} @@"

    return re.sub(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", fix, diff)


def apply_and_check(diff: str) -> tuple[bool, str]:
    """Применяет diff в worktree и гоняет проверки. (ok, report)"""
    if forbidden_touched(diff):
        return False, "патч трогает запрещённые пути"
    diff = _normalize_diff(diff)
    # LLM-диффы часто врут в номерах строк — сначала строгий apply, затем --recount
    attempts = [
        ["git", "apply", "--whitespace=nowarn", "-"],
        ["git", "apply", "--whitespace=nowarn", "--recount", "-"],
    ]
    errors = []
    applied = False
    for cmd in attempts:
        p = subprocess.run(cmd, input=diff, cwd=WORKTREE, capture_output=True, text=True, timeout=60)
        if p.returncode == 0:
            applied = True
            break
        errors.append(p.stderr.strip()[:200])
    if not applied:
        return False, f"git apply не применился: {'; '.join(errors[:2])}"

    changed = git("status", "--porcelain", cwd=WORKTREE).splitlines()
    changed_paths = [c[3:] for c in changed]
    if not changed_paths:
        return False, "патч не изменил ни одного файла"

    # проверки
    py_files = [f for f in changed_paths if f.endswith(".py") and (WORKTREE / f).exists()]
    for f in py_files:
        r = subprocess.run(
            [sys.executable, "-m", "py_compile", str(WORKTREE / f)],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            return False, f"py_compile {f}: {r.stderr.strip()[:200]}"

    if any(f.startswith("frontend/") for f in changed_paths):
        r = subprocess.run(
            ["npm", "run", "build"], cwd=REPO / "frontend", capture_output=True, text=True, timeout=300
        )
        if r.returncode != 0:
            return False, f"vite build сломался: {r.stderr.strip()[-300:]}"

    return True, f"файлов изменено: {len(changed_paths)} ({', '.join(changed_paths[:5])})"


def process(task: dict) -> None:
    log(f"\n=== Задача {task['id'][:8]}: {task['title']} ===")
    try:
        ensure_worktree()
    except RuntimeError as e:
        db_finish_task(task["id"], "failed", f"worktree: {e}")
        return
    reset_worktree()

    diff = ask_victoria_patch(task)
    if not diff:
        db_finish_task(task["id"], "completed", "Victoria не смогла сгенерировать применимый diff (TOO_BIG/NEED_CONTEXT/ошибка). Задача требует человеческой оценки.")
        notify_telegram(f"🧪 Self-dev: не смог сгенерировать патч для «{task['title'][:80]}» — передано человеку.")
        return

    ok, report = apply_and_check(diff)
    if not ok:
        reset_worktree()
        conn = psycopg2.connect(DB_DSN)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE tasks SET metadata = COALESCE(metadata,'{}'::jsonb)
                       || jsonb_build_object('patch_attempts', (%s)::int) WHERE id=%s""",
                    (task["attempts"] + 1, task["id"]),
                )
            conn.commit()
        finally:
            conn.close()
        db_finish_task(task["id"], "pending", f"Попытка #{task['attempts'] + 1}: {report}. Патч откачен, main не тронут.")
        notify_telegram(f"🧯 Self-dev: патч для «{task['title'][:80]}» не прошёл проверки ({report[:120]}). Откат выполнен.")
        log("❌ Проверки не пройдены, откат")
        return

    git("add", "-A", cwd=WORKTREE)
    # --no-verify: pre-commit-хуки ссылаются на хостовые пути, которых нет в worktree;
    # проверки уже выполнены в apply_and_check, merge всё равно gated ревью.
    git(
        "commit", "--no-verify", "-m",
        f"self-dev: {task['title'][:70]}\n\nАвтопатч по задаче {task['id']}\nПроверки: {report}\n\nMerge в main — только по человеческому ревью.",
        cwd=WORKTREE,
    )
    # Бронежилет: агентские "runtime sync" сбрасывали ветку и стирали патчи.
    # Каждый принятый патч дублируем файлом .patch — он переживёт что угодно.
    patches_dir = REPO / "logs" / "self_dev_patches"
    patches_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    commit_hash = git("rev-parse", "HEAD", cwd=WORKTREE)
    patch_file = patches_dir / f"{commit_hash[:10]}_{stamp}.patch"
    patch_file.write_text(git("format-patch", "-1", "HEAD", "--stdout", cwd=WORKTREE))
    meta_file = patches_dir / f"{commit_hash[:10]}_{stamp}.json"
    meta_file.write_text(json.dumps({
        "task_id": task["id"], "title": task["title"], "commit": commit_hash,
        "report": report, "created": datetime.now(timezone.utc).isoformat(),
    }, ensure_ascii=False, indent=1))

    db_finish_task(task["id"], "completed", f"✅ Патч применён и прошёл проверки ({report}). Ветка {BRANCH}, копия: {patch_file.name}. Merge в main — после ревью.")
    notify_telegram(
        f"🧪 Self-dev: патч для «{task['title'][:80]}» готов и прошёл проверки.\n"
        f"Ветка {BRANCH}, {report}. Ждёт ревью перед merge в main."
    )
    log(f"✅ Закоммичено в {BRANCH}: {report}")


def night_battle_window() -> bool:
    """Ночь (01:00–06:00) — время ночных battles/learners; self-dev ждёт утра,
    чтобы не конкурировать за модели."""
    return 1 <= datetime.now().hour < 6


def mlx_busy() -> bool:
    """True, если MLX перегружен (очередь/обработка) — патчер подождёт, чтобы
    не отбирать модели у ночных battles и текущих задач экспертов."""
    try:
        with urllib.request.urlopen(f"{MLX_URL}/queue/stats", timeout=5) as resp:
            stats = json.loads(resp.read())
        return bool(stats.get("is_processing")) or int(stats.get("queue_size", 0)) > 0
    except Exception as e:
        log(f"queue/stats недоступен ({e}) — пробуем всё равно")
        return False


def main() -> int:
    task_id = None
    if "--task-id" in sys.argv:
        task_id = sys.argv[sys.argv.index("--task-id") + 1]
    lock = REPO / "logs" / "self_dev.lock"
    if lock.exists():
        log("Цикл уже запущен (lock).")
        return 0
    try:
        lock.parent.mkdir(exist_ok=True)
        lock.write_text(str(os.getpid()))
        task = db_fetch_task(task_id)
        if not task:
            log("Нет задач dev_loop в очереди.")
            return 0
        if task["attempts"] >= 3:
            db_finish_task(task["id"], "completed",
                           "3 попытки автопатча не прошли проверки. Задача передана человеку — требует ручного решения.")
            notify_telegram(f"🧪 Self-dev: «{task['title'][:80]}» — 3 неудачных попытки, передано человеку.")
            return 0
        if night_battle_window():
            log("Ночное окно battles (01:00–06:00) — self-dev ждёт утра.")
            return 0
        if mlx_busy():
            log("MLX занят (battles/эксперты) — переносим патч на следующий цикл.")
            return 0
        process(task)
    finally:
        lock.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
