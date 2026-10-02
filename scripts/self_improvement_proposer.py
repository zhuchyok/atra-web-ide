"""Self-Improvement Proposer — система сама предлагает, что в себе улучшить.

Раз в неделю (launchd, вс 11:00):
  1. Собирает сигналы: недавние инциденты безопасности, повторяющиеся
     SOP-фиксы из логов, результаты self-check, свежие failed/cancelled задачи.
  2. Отправляет сводку Victoria-wisdom: какие 1–3 улучшения worthy dev_loop-задач.
  3. Для каждой рекомендации создаёт dev_loop-задачу (source=dev_loop) —
     их подхватит self_dev_loop и подготовит патч в auto/dev-loop.
  4. Telegram: «система предлагает улучшить себя — вот список».

Человек в цикле остаётся: задачи становятся pending и патчи ждут ревью,
auto-merge в main не происходит.
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import psycopg2

REPO = Path(__file__).resolve().parent.parent
DB_DSN = os.environ.get("ATRA_DB_DSN", "postgresql://admin:secret@127.0.0.1:6432/knowledge_os")  # pragma: allowlist secret
MLX_URL = os.environ.get("MLX_BASE_URL", "http://127.0.0.1:11435").rstrip("/")
WISDOM_MODEL = os.getenv("WISDOM_MODEL", "victoria-wisdom-24k")
MAX_TASKS_PER_RUN = 3


def fetch_signals() -> str:
    """Собирает объективные сигналы о здоровье/болях системы за неделю."""
    conn = psycopg2.connect(DB_DSN)
    parts = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT anomaly_type, count(*) FROM anomaly_detection_logs
                   WHERE detected_at > NOW() - INTERVAL '7 days'
                   GROUP BY 1 ORDER BY 2 DESC LIMIT 5"""
            )
            rows = cur.fetchall()
            if rows:
                parts.append(
                    "Инциденты безопасности за неделю: "
                    + "; ".join(f"{t} x{c}" for t, c in rows)
                )
            cur.execute(
                """SELECT left(title, 80), count(*) FROM tasks
                   WHERE status IN ('failed','cancelled')
                     AND created_at > NOW() - INTERVAL '7 days'
                   GROUP BY 1 ORDER BY 2 DESC LIMIT 5"""
            )
            rows = cur.fetchall()
            if rows:
                parts.append(
                    "Частые failed/cancelled задачи за неделю: "
                    + "; ".join(f"«{t}» x{c}" for t, c in rows)
                )
            cur.execute(
                """SELECT count(*) FROM tasks
                   WHERE metadata->>'source'='dev_loop'
                     AND created_at > NOW() - INTERVAL '7 days'"""
            )
            n = cur.fetchone()[0]
            parts.append(f"dev_loop-задач за неделю: {n}")
    finally:
        conn.close()
    return "\n".join(parts) or "Сигналов за неделю не найдено — система тихая."


def ask_victoria(signal_text: str) -> list[dict]:
    """Просит Victoria предложить до 3 улучшений в строгом JSON."""
    prompt = (
        "Ты — архитектор системы ATRA. Вот объективные сигналы о проблемах за неделю:\n"
        f"{signal_text}\n\n"
        "Предложи до 3 КОНКРЕТНЫХ малых улучшений кода/конфигов, которые можно "
        "оформить маленьким unified diff (файл-два). Не предлагай: изменения БД-схемы, "
        "новые микросервисы, миграции, секреты, CI.\n"
        "Ответь СТРОГО валидным JSON-массивом объектов:\n"
        '[{"title":"короткий заголовок задачи","description":"что сделать и в каком файле"}]\n'
        "Только JSON, без текста вокруг."
    )
    body = json.dumps({
        "model": WISDOM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "max_tokens": 1200,
        "options": {"temperature": 0.3, "num_predict": 1200},
    }).encode()
    req = urllib.request.Request(
        f"{MLX_URL}/api/chat", data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=420) as resp:
        content = json.loads(resp.read())["message"]["content"].strip()
    m = __import__("re").search(r"\[.*\]", content, __import__("re").DOTALL)
    if not m:
        return []
    try:
        items = json.loads(m.group(0))
        return [i for i in items if isinstance(i, dict) and i.get("title")][:MAX_TASKS_PER_RUN]
    except json.JSONDecodeError:
        return []


def create_dev_loop_task(item: dict) -> bool:
    conn = psycopg2.connect(DB_DSN)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tasks (title, description, status, priority, metadata, project_context)
                VALUES (%s, %s, 'pending', 'low', %s, 'atra-web-ide')
                """,
                (
                    f"self-dev: {item['title'][:120]}",
                    item.get("description", "")[:4000],
                    json.dumps({"source": "dev_loop", "origin": "self_improvement_proposer"}),
                ),
            )
        conn.commit()
        return True
    except Exception as e:
        print(f"DB error: {e}")
        return False
    finally:
        conn.close()


def notify(text: str) -> None:
    token, chat_id = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_USER_ID")
    if not token or not chat_id:
        return
    try:
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": text[:3500]}).encode()
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=10
        )
    except Exception as e:
        print(f"telegram error: {e}")


def main() -> int:
    print("=== Self-Improvement Proposer ===")
    signals = fetch_signals()
    print(f"Сигналы:\n{signals}\n")
    proposals = ask_victoria(signals)
    if not proposals:
        print("Victoria не предложила валидных улучшений — ок, бывает тихая неделя.")
        return 0
    created = []
    for p in proposals:
        if create_dev_loop_task(p):
            created.append(p["title"])
    if created:
        notify(
            "🌱 Self-improvement: система предложила улучшить себя:\n"
            + "\n".join(f"• {t}" for t in created)
            + "\n\nПатчи подготовит self-dev loop и положит в auto/dev-loop на ревью."
        )
    print(f"Создано dev_loop-задач: {len(created)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
