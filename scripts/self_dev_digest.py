"""Self-Dev Review Digest — еженедельная сводка патчей из auto/dev-loop в Telegram.

Показывает: коммиты ветки за неделю, изменённые файлы, статистику dev_loop-задач
(принято/откатено) — чтобы человеку было легко ревьюить и мержить.
Запуск: launchd com.atra.self-dev-digest (пт 18:00).
"""
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import psycopg2

MLX_URL = os.environ.get("MLX_BASE_URL", "http://127.0.0.1:11435").rstrip("/")
WISDOM_MODEL = os.environ.get("WISDOM_MODEL", "victoria-wisdom-24k")

REPO = Path(__file__).resolve().parent.parent
BRANCH = "auto/dev-loop"

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


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True).stdout.strip()


def review_patch_text(patch_text: str, title: str) -> str:
    """Вердикт Victoria по тексту патча."""
    body = json.dumps({
        "model": WISDOM_MODEL,
        "messages": [{"role": "user", "content": (
            f"Ты — строгий код-ревьюер. Автопатч «{title}»:\n```\n{patch_text}\n```\n"
            "Оцени: можно ли безопасно применить в main? Ответь ровно:\n"
            "VERDICT: ok | risky\nПОЧЕМУ: одна короткая строка."
        )}],
        "stream": False,
        "max_tokens": 200,
        "options": {"temperature": 0.1, "num_predict": 200},
    }).encode()
    req = urllib.request.Request(
        f"{MLX_URL}/api/chat", data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            content = json.loads(resp.read())["message"]["content"].strip()
        verdict = "risky" if "risky" in content.lower() else ("ok" if "ok" in content.lower() else "?")
        why = content.split("ПОЧЕМУ:")[-1].strip().splitlines()[0][:150] if "ПОЧЕМУ" in content else content[:150]
        return f"[{verdict.upper()}] {why}"
    except Exception as e:
        return f"[SKIP] ревью не удалось: {e}"


def review_commit(commit_hash: str, diff_stat: str) -> str:
    """Просит Victoria оценить риск патча: VERDICT: ok|-risky + одна строка почему."""
    diff = git("show", commit_hash, "--format=", "--unified=1")[:6000]
    body = json.dumps({
        "model": WISDOM_MODEL,
        "messages": [{"role": "user", "content": (
            "Ты — строгий код-ревьюер. Вот diff автопатча (тема: "
            f"{git('log', '-1', '--format=%s', commit_hash)}).\n"
            f"Файлы: {diff_stat}\n```\n{diff}\n```\n"
            "Оцени: можно ли безопасно мержить в main? Ответь ровно в формате:\n"
            "VERDICT: ok | risky\nПОЧЕМУ: одна короткая строка."
        )}],
        "stream": False,
        "max_tokens": 200,
        "options": {"temperature": 0.1, "num_predict": 200},
    }).encode()
    req = urllib.request.Request(
        f"{MLX_URL}/api/chat", data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            content = json.loads(resp.read())["message"]["content"].strip()
        verdict = "risky" if "risky" in content.lower() else ("ok" if "ok" in content.lower() else "?")
        why = content.split("ПОЧЕМУ:")[-1].strip().splitlines()[0][:150] if "ПОЧЕМУ" in content else content[:150]
        return f"[{verdict.upper()}] {why}"
    except Exception as e:
        return f"[SKIP] ревью не удалось: {e}"


def collect() -> str:
    lines = ["🧪 Self-Dev: сводка за неделю\n"]

    # Первоисточник — файлы патчей (ветку в общем репо сбрасывают синхронизаторы)
    patches_dir = REPO / "logs" / "self_dev_patches"
    metas = sorted(patches_dir.glob("*.json"))
    lines.append(f"Готовых патчей на ревью: {len(metas)}")
    reviewed = 0
    for mf in metas[:10]:
        try:
            meta = json.loads(mf.read_text())
        except ValueError:
            continue
        lines.append(f"  • [{mf.stem.split('_')[0]}] {meta.get('title','?')[:70]}")
        # AI-ревью до 5 патчей за прогон (не жечь модели)
        if reviewed < 5:
            patch_text = (patches_dir / (mf.stem + ".patch")).read_text()[:4000]
            verdict = review_patch_text(patch_text, meta.get("title", ""))
            lines.append(f"      🤖 ревью: {verdict}")
            reviewed += 1
    lines.append("Применить: git am logs/self_dev_patches/<файл>.patch")


    conn = psycopg2.connect(DB_DSN)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT status, count(*) FROM tasks
                   WHERE metadata->>'source'='dev_loop'
                     AND created_at > NOW() - INTERVAL '7 days'
                   GROUP BY 1"""
            )
            stats = cur.fetchall()
            if stats:
                lines.append(
                    "\ndev_loop-задачи за неделю: " + ", ".join(f"{s}={n}" for s, n in stats)
                )
    finally:
        conn.close()

    lines.append("\nMerge в main — только вручную после ревью: git checkout main && git merge " + BRANCH)
    return "\n".join(lines)


def main() -> int:
    _load_dotenv()
    text = collect()
    print(text)
    token, chat_id = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_USER_ID")
    if token and chat_id:
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": text[:4000]}).encode()
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=10
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
