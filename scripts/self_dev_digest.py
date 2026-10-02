"""Self-Dev Review Digest — еженедельная сводка патчей из auto/dev-loop в Telegram.

Показывает: коммиты ветки за неделю, изменённые файлы, статистику dev_loop-задач
(принято/откатено) — чтобы человеку было легко ревьюить и мержить.
Запуск: launchd com.atra.self-dev-digest (пт 18:00).
"""
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg2

REPO = Path(__file__).resolve().parent.parent
BRANCH = "auto/dev-loop"
DB_DSN = os.environ.get("ATRA_DB_DSN", "postgresql://admin:secret@127.0.0.1:6432/knowledge_os")  # pragma: allowlist secret


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True).stdout.strip()


def collect() -> str:
    lines = ["🧪 Self-Dev: сводка за неделю\n"]
    since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

    commits = git("log", f"main..{BRANCH}", "--oneline", "--no-merges").splitlines()
    main_head = git("merge-base", "main", BRANCH)
    ahead = commits
    lines.append(f"Коммитов в {BRANCH} не в main: {len(ahead)}")
    for c in ahead[:10]:
        lines.append(f"  • {c}")
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
