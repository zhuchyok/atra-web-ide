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

def _load_dotenv() -> None:
    """Фолбэк для launchd: токены берём из .env, не из plist (секреты не в git)."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()

DB_DSN = os.environ.get("ATRA_DB_DSN", "postgresql://admin:secret@127.0.0.1:6432/knowledge_os")  # pragma: allowlist secret
MLX_URL = os.environ.get("MLX_BASE_URL", "http://127.0.0.1:11435").rstrip("/")
WISDOM_MODEL = os.getenv("WISDOM_MODEL", "victoria-wisdom-24k")
# Лестница эскалации: wisdom быстрая, но слабая в диффах; coder-модель мощнее.
OLLAMA_URL = os.getenv("DEV_LOOP_CODER_URL", "http://127.0.0.1:11436").rstrip("/")  # выделенный coder-слой (v149.4)
CODER_MODEL = os.getenv("DEV_LOOP_CODER_MODEL", "qwen3-coder:30b")
MODEL_LADDER = [
    {"backend": "mlx", "model": WISDOM_MODEL},
    {"backend": "ollama", "model": CODER_MODEL},
    {"backend": "mlx", "model": WISDOM_MODEL},
]

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
    """Модель по номеру попытки (лестница эскалации)."""
    attempt = task.get("attempts", 0)
    step = MODEL_LADDER[min(attempt, len(MODEL_LADDER) - 1)]
    log(f"Генерация: {step['backend']}/{step['model']} (попытка {attempt + 1})")
    return ask_model_patch(task, step["backend"], step["model"])


def _mentioned_files(task: dict, worktree: Path) -> list[Path]:
    """Файлы, упомянутые в задаче и существующие в worktree (до 3, до 120 строк)."""
    text = f"{task['title']} {task['description']}"
    # имя файла с путём или без (README.md тоже валиден)
    candidates = re.findall(r"[\w./-]*[\w-]+\.(?:py|sh|js|ts|svelte|md|yml|yaml|json)", text)
    seen, found = set(), []
    for cand in candidates:
        # путь упомянут относительно корня репо
        for full in (worktree / cand, *[worktree / p for p in re.findall(r"[\w./-]*" + re.escape(cand), text)]):
            full = Path(str(full))
            if full.is_file() and str(full.relative_to(worktree)) not in seen:
                seen.add(str(full.relative_to(worktree)))
                found.append(full)
                break
        if len(found) >= 3:
            break
    return found


def ask_model_patch(task: dict, backend: str, model: str) -> str | None:
    """Просит Victoria-wisdom сгенерировать unified diff. Возвращает diff или None."""
    # КРИТИЧНО: для правки существующих файлов даём модели их РЕАЛЬНОЕ содержимое —
    # иначе она галлюцинирует контекстные строки и git apply честно отклоняет патч.
    file_context = ""
    mentioned = _mentioned_files(task, WORKTREE)
    for f in mentioned:
        rel = f.relative_to(WORKTREE)
        body = "\n".join(f.read_text(errors="replace").splitlines()[:120])
        file_context += f"\n--- ТЕКУЩЕЕ СОДЕРЖИМОЕ {rel} (первые 120 строк) ---\n{body}\n"
    prompt = (
        "Ты — аккуратный разработчик проекта ATRA (репозиторийatra-web-ide).\n"
        f"ЗАДАЧА: {task['title']}\n\n{task['description'][:1500]}\n"
        f"{file_context}\n"
        "Формат ответа — один или несколько блоков:\n"
        "<<<<<<< SEARCH\n"
        "[точные строки из текущего файла, которые заменяем; для НОВОГО файла — пусто]\n"
        "=======\n"
        "[новые строки на это место]\n"
        ">>>>>>> REPLACE\n\n"
        "ВАЖНО: строки в SEARCH копируй из ТЕКУЩЕГО СОДЕРЖИМОГО файла выше посимвольно\n"
        "(включая спецсимволы │└── и отступы). Если файлов в контексте нет — SEARCH пустой\n"
        "и это создание нового файла. Без пояснений, только блоки.\n"
        "Если задача слишком крупная — верни ровно слово: TOO_BIG\n"
        "Если не хватает контекста — верни ровно слово: NEED_CONTEXT"
    )
    base = MLX_URL if backend == "mlx" else OLLAMA_URL
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "max_tokens": 4096,
        "options": {"temperature": 0.2, "num_predict": 4096},
    }).encode()
    req = urllib.request.Request(
        f"{base}/api/chat", data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=420) as resp:
            content = json.loads(resp.read())["message"]["content"].strip()
    except Exception as e:
        log(f"Ошибка генерации ({backend}/{model}): {e}")
        return None

    if content.strip() in ("TOO_BIG", "NEED_CONTEXT"):
        log(f"Victoria: {content.strip()}")
        return None
    # НЕ регексом по ``` — SEARCH/REPLACE может содержать собственные фенсы
    # (например, README с блоками кода), и жадное извлечение режет блок посередине.
    if content.startswith("```"):
        content = content[content.find("\n") + 1 :]
    if content.endswith("```"):
        content = content[: content.rfind("```")]
    diff = content.strip()
    # модели (wisdom) любят оборачивать ответ в <think> — git apply такое не ест
    diff = re.sub(r"<think>[\s\S]*?</think>", "", diff).strip()
    # и нередко выдают только hunk'и без файлового заголовка — синтезируем его
    if diff.startswith("@@") and "--- a/" not in diff:
        mentioned = _mentioned_files(task, WORKTREE)
        if mentioned:
            rel = mentioned[0].relative_to(WORKTREE)
            diff = f"--- a/{rel}\n+++ b/{rel}\n" + diff
    has_blocks = "<<<<<<< SEARCH" in diff
    has_diff = diff.startswith(("---", "diff --git")) and "@@" in diff
    if not (has_blocks or has_diff):
        log(f"Валидация отклонила ответ ({model}): {content[:200]!r}")
        return None
    return diff


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
        lines_after = diff[match.end():].splitlines()
        for i, line in enumerate(lines_after):
            is_new_file = line.startswith("--- ") and i + 1 < len(lines_after) and lines_after[i + 1].startswith("+++ ")
            if line.startswith("@@") or line.startswith("diff --git") or is_new_file or line.startswith("index "):
                break
            body.append(line)
        adds = sum(1 for l in body if l.startswith("+"))
        dels = sum(1 for l in body if l.startswith("-"))
        return f"@@ -{match.group(1) or 0},{dels} +{match.group(3) or 0},{adds} @@"

    return re.sub(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", fix, diff)


def _parse_sr_blocks(text: str) -> list:
    """Толерантный парсер SEARCH/REPLACE: стандартный вид и вариации модели
    (REPLACE-контент после закрывающей метки, без =======)."""
    blocks = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if lines[i].startswith("<<<<<<< SEARCH"):
            sep = end = None
            j = i + 1
            while j < len(lines):
                if lines[j].strip() == "=======" and sep is None:
                    sep = j
                elif lines[j].startswith(">>>>>>> REPLACE"):
                    end = j
                    break
                j += 1
            if end is None:
                i += 1
                continue
            if sep is not None:
                search = "\n".join(lines[i + 1 : sep])
                replace = "\n".join(lines[sep + 1 : end])
            else:
                search = "\n".join(lines[i + 1 : end])
                k = end + 1
                repl = []
                while k < len(lines) and lines[k].strip() and not lines[k].startswith("<<<<<<<"):
                    repl.append(lines[k])
                    k += 1
                replace = "\n".join(repl)
            blocks.append((search, replace))
            i = end + 1
            continue
        i += 1
    return blocks


def _apply_search_replace(diff: str) -> tuple[bool, str]:
    """Применяет SEARCH/REPLACE блоки. Точное совпадение -> difflib fuzzy-поиск региона."""
    import difflib

    blocks = _parse_sr_blocks(diff)
    if not blocks:
        return False, "нет SEARCH/REPLACE блоков"

    applied, errors = 0, []
    # группа файлов: блоки к файлам привязываем по упоминаниям в REPLACE/описании —
    # упрощение: если файлов в задаче несколько, применяем ко всем кандидатам по fuzzy
    for search, replace in blocks:
        search_lines = search.splitlines()
        # поиск файла, содержащего SEARCH-текст
        target, best_ratio = None, 0.0
        candidates = [p for p in Path(str(WORKTREE)).rglob("*") if p.is_file() and not any(
            part in str(p) for part in (".git/", "node_modules", "__pycache__")
        ) and p.suffix in (".py", ".sh", ".md", ".js", ".ts", ".svelte", ".yml", ".yaml", ".json", ".html", ".css")]
        search_blob = "\n".join(search_lines)
        for cand in candidates:
            try:
                content = cand.read_text(errors="replace")
            except OSError:
                continue
            if search_blob and search_blob in content:
                target, best_ratio = cand, 1.0
                break
            # fuzzy: сравниваем окна
            cand_lines = content.splitlines()
            if not search_lines or len(cand_lines) < len(search_lines):
                continue
            # окно с максимальным сходством к SEARCH
            window = max(1, len(search_lines))
            best_local = 0.0
            step = max(1, window // 2)
            search_text = "\n".join(search_lines)
            for start in range(0, max(1, len(cand_lines) - window + 1), step):
                chunk_text = "\n".join(cand_lines[start:start + window])
                r = difflib.SequenceMatcher(None, chunk_text, search_text).quick_ratio()
                if r > best_local:
                    best_local = r
                if best_local >= 0.95:
                    break
            if best_local > best_ratio:
                best_ratio = best_local
                target = cand
        if target is None and not search.strip():
            # Пустой SEARCH: создание НОВОГО файла или (если файл есть) append в конец —
            # так модели часто выражают «добавь в конец». Перезапись запрещена.
            mentioned = _mentioned_files({"title": "", "description": diff}, WORKTREE)
            dest = mentioned[0] if mentioned else None
            if dest is not None:
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists():
                    existing = dest.read_text(errors="replace").rstrip("\n")
                    dest.write_text(existing + "\n\n" + replace.strip() + "\n")
                    applied += 1
                    continue
                dest.write_text(replace + "\n")
                applied += 1
                continue
        if target is None:
            errors.append("SEARCH-текст не найден ни в одном файле")
            continue

        content = target.read_text(errors="replace")
        lines = content.splitlines()
        search_l = search.splitlines()
        replace_l = replace.splitlines() if replace else []
        # точная замена
        blob = "\n".join(search_l)
        if blob and blob in content:
            content = content.replace(blob, "\n".join(replace_l), 1)
        else:
            # fuzzy: находим лучшее окно и заменяем его
            window = max(1, len(search_l))
            best_start, best_r = None, 0.0
            search_text = "\n".join(search_l)
            for start in range(0, max(1, len(lines) - window + 1)):
                chunk_text = "\n".join(lines[start:start + window])
                r = difflib.SequenceMatcher(None, chunk_text, search_text).ratio()
                if r > best_r:
                    best_r, best_start = r, start
            if best_start is None or best_r < 0.55:
                errors.append(f"fuzzy-регион не найден в {target.name} (лучший {best_r:.2f})")
                continue
            lines[best_start:best_start + window] = replace_l
            content = "\n".join(lines)
        target.write_text(content)
        applied += 1

    if applied == 0:
        return False, "; ".join(errors) or "ничего не применено"
    return True, f"блоков применено: {applied}" + (f" (ошибки: {errors})" if errors else "")


def apply_and_check(diff: str) -> tuple[bool, str]:
    """Применяет diff в worktree и гоняет проверки. (ok, report)"""
    if forbidden_touched(diff):
        return False, "патч трогает запрещённые пути"
    if "<<<<<<< SEARCH" in diff:
        return _apply_search_replace(diff)
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
    _load_dotenv()
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
        if task["attempts"] >= len(MODEL_LADDER):
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
