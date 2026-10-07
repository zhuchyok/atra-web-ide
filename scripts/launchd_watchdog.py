"""Watchdog за launchd-джобами ATRA — проверяет, что автоматика жива.

Каждый час (launchd com.atra.watchdog-jobs): для каждой критичной джобы смотрит
launchctl list (последний exit code) и freshness её лога/артефакта. Если джоба
не загружена или падала — создаёт задачу на разбор и шлёт Telegram один раз
за инцидент (state-файл).

Запуск: python3 scripts/launchd_watchdog.py
"""
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


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

REPO = Path(__file__).resolve().parent.parent
STATE_PATH = Path(__file__).resolve().parent.parent / "logs" / "launchd_watchdog_state.json"
WATCH_LIST = {
    # label: (макс. возраст последнего успешного запуска в часах по лог-файлу, лог-файл)
    "com.atra.security-responder": (26, None),
    "com.atra.db-backup": (26, REPO / "logs" / "db_backup.log"),
    "com.atra.dashboard-smoke": (26, REPO / "logs" / "dashboard_smoke_last.log"),
    "com.atra.self-dev": (26, None),
    "com.atra.self-improvement": (24 * 8, None),
    "com.atra.self-dev-digest": (24 * 8, None),
}


def launchctl_status(label: str):
    r = subprocess.run(["launchctl", "list", label], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    out = r.stdout
    pid = None
    last_exit = None
    for line in out.splitlines():
        if '"PID" =' in line:
            pid = line.split("=")[1].strip().rstrip(";")
        if "last exit code" in line:
            try:
                last_exit = int(line.split("=")[1].strip().rstrip(";"))
            except ValueError:
                pass
    return {"loaded": True, "pid": pid, "last_exit": last_exit}


def log_fresh(path: Path, max_hours: float) -> bool:
    if not path.exists():
        return False
    age_h = (datetime.now().timestamp() - path.stat().st_mtime) / 3600
    return age_h <= max_hours


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"alerted": {}}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=1))




def _notify_ntfy(message: str) -> None:
    """Push через ntfy (основной канал — Telegram-маршрут с Mac блокирует провайдер)."""
    try:
        topic = os.environ.get("NTFY_TOPIC", "atra_victoria_curator")
        data = json.dumps({"topic": topic, "message": message[:3500]}).encode()
        req = urllib.request.Request(
            "https://ntfy.sh/" + topic, data=data,
            headers={"Content-Type": "application/json", "Title": "ATRA"},
        )
        urllib.request.urlopen(req, timeout=15)
    except Exception as e:
        print("ntfy error:", e)


def notify(text: str) -> None:
    token, chat_id = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_USER_ID")
    if not token or not chat_id:
        return
    try:
        import urllib.parse

        data = urllib.parse.urlencode({"chat_id": chat_id, "text": text[:3500]}).encode()
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=10
        )
    except Exception as e:
        print(f"telegram error: {e}")


def create_task(problems: str) -> bool:
    import psycopg2

    conn = psycopg2.connect(os.environ.get("ATRA_DB_DSN", "postgresql://admin:secret@127.0.0.1:6432/knowledge_os"))  # pragma: allowlist secret
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tasks (title, description, status, priority, metadata, project_context)
                VALUES (%s, %s, 'pending', 'high', '{"source":"launchd_watchdog"}', 'atra-web-ide')
                """,
                (
                    "🧯 Watchdog: launchd-автоматика нездорова",
                    f"Обнаружены проблемы с launchd-джобами:\n{problems}\n\n"
                    "Требуется: перезагрузить упавшие джобы (launchctl load), найти причину падения, закрыть задачу с отчётом.",
                ),
            )
        conn.commit()
        return True
    except Exception as e:
        print(f"DB error: {e}")
        return False
    finally:
        conn.close()


def main() -> int:
    _load_dotenv()
    state = load_state()
    problems = []
    for label, (max_hours, log_path) in WATCH_LIST.items():
        status = launchctl_status(label)
        if status is None:
            # Самолечение: plist на месте, но джоба выгружена — грузим заново
            plist = Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"
            if plist.exists():
                subprocess.run(["launchctl", "unload", str(plist)], capture_output=True)
                r = subprocess.run(["launchctl", "load", str(plist)], capture_output=True, text=True)
                if r.returncode == 0 and launchctl_status(label) is not None:
                    log_line = f"[{datetime.now(timezone.utc).isoformat()}] SELF-HEAL: {label} перезагружена"
                    print(log_line)
                    (REPO / "logs" / "launchd_watchdog.log").open("a").write(log_line + "\n")
                    continue  # вылечено — не алертим
            problems.append(f"{label}: НЕ ЗАГРУЖЕНА в launchd (автоперезагрузка не удалась)")
            continue
        if status["last_exit"] not in (None, 0):
            problems.append(f"{label}: последний exit code = {status['last_exit']}")
        if log_path is not None and not log_fresh(log_path, max_hours):
            problems.append(f"{label}: лог {log_path.name} старше {max_hours}ч")

    fresh_problems = [p for p in problems if p not in state["alerted"]]
    if not fresh_problems:
        print("Все launchd-джобы в норме." if not problems else "Проблемы повторяются, алерт уже отправлен.")
        return 0

    problems_text = "\n".join(f"• {p}" for p in fresh_problems)
    print("❌ Проблемы:\n" + problems_text)
    if create_task(problems_text):
        notify(
            "🧯 ATRA Watchdog: проблемы с launchd-автоматикой\n"
            + problems_text
            + "\n\nСоздана задача на разбор."
        )
        for p in fresh_problems:
            state["alerted"][p] = datetime.now(timezone.utc).isoformat()
        # держим не более 100 записей
        state["alerted"] = dict(list(state["alerted"].items())[-100:])
        save_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
