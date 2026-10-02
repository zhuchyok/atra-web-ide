"""Security Incident Responder — автоматическая реакция на инциденты безопасности.

Периодически проверяет anomaly_detection_logs на новые high/critical-инциденты
(prompt_injection, data_leak и т.п.) и на каждый новый:
  1. Создаёт задачу в tasks (status=pending, metadata.source=security_responder)
     — её разбирает экспертная система (как обычную работу оркестратора).
  2. Пишет строку в logs/security_alerts.log.

Состояние (id обработанных инцидентов) хранит logs/security_responder_state.json.
Запуск: python3 scripts/security_incident_responder.py
Повторение: cron/launchd каждые 5–15 минут.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg2

STATE_PATH = Path(__file__).resolve().parent.parent / "logs" / "security_responder_state.json"
ALERT_LOG = Path(__file__).resolve().parent.parent / "logs" / "security_alerts.log"

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
LOOKBACK_HOURS = 24
MIN_SEVERITY = {"high", "critical"}


def load_state() -> dict:
    """При первом запуске (нет state-файла) существующий backlog считается
    принятым: реагируем только на инциденты, появившиеся ПОСЛЕ первой проверки."""
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"processed": [], "first_run": True}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    # храним последние 500 id, чтобы файл не рос бесконечно
    state["processed"] = state["processed"][-500:]
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=1))


def log_alert(line: str) -> None:
    ALERT_LOG.parent.mkdir(parents=True, exist_ok=True)
    ALERT_LOG.open("a").write(line + "\n")


def notify_telegram(text: str) -> None:
    """Пуш владельцу. Не критично к ошибкам: уведомление не должно ломать реакцию."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_USER_ID") or os.environ.get("TG_CHAT_ID")
    if not token or not chat_id:
        return
    try:
        import urllib.parse
        import urllib.request

        data = urllib.parse.urlencode({"chat_id": chat_id, "text": text[:3500]}).encode()
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=10
        )
    except Exception as e:
        log_alert(f"[{datetime.now(timezone.utc).isoformat()}] TELEGRAM ERROR: {e}")


def fetch_new_incidents() -> list:
    conn = psycopg2.connect(DB_DSN)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, anomaly_type, severity, description, detected_at
                FROM anomaly_detection_logs
                WHERE detected_at > NOW() - INTERVAL '%s hours'
                  AND severity = ANY(%s)
                ORDER BY detected_at ASC
                """,
                (LOOKBACK_HOURS, list(MIN_SEVERITY)),
            )
            return [
                {
                    "id": str(r[0]),
                    "anomaly_type": r[1],
                    "severity": r[2],
                    "details": (r[3] or "")[:500],
                    "detected_at": r[4].isoformat() if r[4] else None,
                }
                for r in cur.fetchall()
            ]
    finally:
        conn.close()


def create_response_task(incident: dict) -> bool:
    conn = psycopg2.connect(DB_DSN)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tasks (title, description, status, priority, metadata, project_context)
                VALUES (%s, %s, 'pending', 'high', %s, 'atra-web-ide')
                """,
                (
                    f"🛡️ Security: разбор инцидента {incident['anomaly_type']} #{incident['id']} ({incident['severity']})",
                    (
                        f"Инцидент #{incident['id']} от {incident['detected_at']}.\n"
                        f"Детали: {incident['details']}\n\n"
                        "Требуется: определить источник, оценить ущерб, предложить и применить меры "
                        "(карантин источника / правила фильтрации). После разбора закрыть задачу с результатом."
                    ),
                    json.dumps({"source": "security_responder", "incident_id": incident["id"]}),
                ),
            )
        conn.commit()
        return True
    except Exception as e:
        log_alert(f"[{datetime.now(timezone.utc).isoformat()}] DB ERROR: {e}")
        return False
    finally:
        conn.close()


def main() -> int:
    _load_dotenv()
    state = load_state()
    incidents = fetch_new_incidents()
    first_run = state.pop("first_run", False)
    fresh = [i for i in incidents if i["id"] not in state["processed"]]
    if first_run and fresh:
        # Backlog не конвертируем в задачи — только фиксируем в логе.
        for incident in fresh:
            state["processed"].append(incident["id"])
            log_alert(
                f"[{datetime.now(timezone.utc).isoformat()}] BACKLOG: {incident['severity'].upper()} "
                f"{incident['anomaly_type']} #{incident['id']} @ {incident['detected_at']}"
            )
        save_state(state)
        print(f"Первый запуск: backlog {len(fresh)} инцидентов зафиксирован в {ALERT_LOG.name}, задачи не создавались.")
        return 0
    if not fresh:
        print("Новых high/critical инцидентов нет.")
        return 0

    created = 0
    for incident in fresh:
        if create_response_task(incident):
            created += 1
            state["processed"].append(incident["id"])
            log_alert(
                f"[{datetime.now(timezone.utc).isoformat()}] {incident['severity'].upper()} "
                f"{incident['anomaly_type']} #{incident['id']} @ {incident['detected_at']} — "
                f"создана задача на разбор"
            )
            print(f"🛡️ Реакция: {incident['anomaly_type']} ({incident['severity']}) — задача создана")
            notify_telegram(
                f"🛡️ ATRA Security [{incident['severity'].upper()}]\n"
                f"{incident['anomaly_type']} #{incident['id']} @ {incident['detected_at']}\n"
                f"Создана задача на разбор (высокий приоритет)."
            )
        else:
            print(f"⚠️ Не удалось создать задачу для #{incident['id']} — повторится при следующем запуске")

    save_state(state)
    print(f"Итог: новых инцидентов {len(fresh)}, задач создано {created}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
