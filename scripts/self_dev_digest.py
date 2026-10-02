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
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg2

MLX_URL = os.environ.get("MLX_BASE_URL", "http://127.0.0.1:11435").rstrip("/")
WISDOM_MODEL = os.environ.get("WISDOM_MODEL", "victoria-wisdom-24k")

REPO = Path(__file__).resolve().parent.parent
BRANCH = "auto/dev-loop"
DB_DSN = os.environ.get("ATRA_DB_DSN", "postgresql://admin:secret@127.0.0.1:6432/knowledge_os")  # pragma: allowlist secret


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True).stdout.strip()


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
    since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

    commits = git("log", f"main..{BRANCH}", "--oneline", "--no-merges").splitlines()
    main_head = git("merge-base", "main", BRANCH)
    ahead = commits
    lines.append(f"Коммитов в {BRANCH} не в main: {len(ahead)}")
    reviewed = 0
    for c in ahead[:10]:
        lines.append(f"  • {c}")
        # AI-ревью до 5 патчей за прогон (не жечь модели)
        if reviewed < 5:
            chash = c.split()[0]
            stat = git("diff", "--stat", f"{chash}~1..{chash}").splitlines()[-1]
            verdict = review_commit(chash, stat)
            lines.append(f"      🤖 ревью: {verdict}")
            reviewed += 1
    if len(ahead) > 10:
        lines.append(f"  … и ещё {len(ahead) - 10}")

    diff_stat = git("diff", "--stat", f"{main_head}..{BRANCH}").splitlines()
    if diff_stat:
        lines.append("\nСуммарный diff против main:")
        lines += ["  " + l for l in diff_stat[-5:]]

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
