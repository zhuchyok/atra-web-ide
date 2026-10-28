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
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import urllib.request

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
DB_CONNECT_RETRIES = int(os.environ.get("ATRA_DB_CONNECT_RETRIES", "3"))
DB_CONNECT_BACKOFF_SEC = float(os.environ.get("ATRA_DB_CONNECT_BACKOFF_SEC", "1.5"))


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


def _db_connect():
    """Подключение к БД с коротким retry для сглаживания флапов pgbouncer."""
    last_exc = None
    for attempt in range(1, DB_CONNECT_RETRIES + 1):
        try:
            return psycopg2.connect(DB_DSN)
        except Exception as e:
            last_exc = e
            if attempt < DB_CONNECT_RETRIES:
                time.sleep(DB_CONNECT_BACKOFF_SEC * attempt)
    raise last_exc




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
        # [v150.22] Телега заблокирована провайдером (api.telegram.org unreachable,
        # 1040× Errno-65, traceroute обрыв на хопе 3) — критический алерт не должен
        # теряться: дублируем в ntfy (доступен, проверено живьём).
        try:
            import urllib.request as _ur

            _rq = _ur.Request(
                "https://ntfy.sh/atra_victoria_curator",
                data=text[:3500].encode(),
                headers={"Title": "ATRA (tg-down)", "Priority": "high", "Tags": "warning"},
            )
            _ur.urlopen(_rq, timeout=10)
        except Exception:
            pass


def fetch_new_incidents() -> list:
    conn = _db_connect()
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
    conn = _db_connect()
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


def _recent_security_task_exists(cur) -> bool:
    """[v150.16] Рейт-лимит: была ли уже сводная security-задача за последний час."""
    try:
        cur.execute(
            """
            SELECT 1 FROM tasks
            WHERE title LIKE '🛡️ Security:%'
              AND created_at > NOW() - INTERVAL '1 hour'
            LIMIT 1
            """
        )
        return cur.fetchone() is not None
    except Exception as e:
        # если схемы/колонки нет — не блокируем реакцию на инциденты
        log_alert(f"[{datetime.now(timezone.utc).isoformat()}] RATELIMIT CHECK ERROR: {e}")
        return False


def _incidents_hash(incidents: list) -> str:
    """[v150.29] SHA256-хеш содержимого инцидентов (не только IDs)."""
    normalized = []
    for incident in incidents:
        normalized.append(
            "|".join(
                [
                    str(incident.get("id", "")),
                    str(incident.get("anomaly_type", "")),
                    str(incident.get("severity", "")),
                    str(incident.get("detected_at", "")),
                    str(incident.get("details", "")),
                ]
            )
        )
    payload = "\n".join(sorted(normalized))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def create_response_task_consolidated(incidents: list, top_types: str):
    """Одна сводная задача на партию инцидентов (анти-спам).
    [v150.16] Возвращает True (создана), False (ошибка), 'skipped' (рейт-лимит).
    [v150.28] Кэш повторов: идентичное/≥90% совпадающее множество ID НЕ создаёт
    новую задачу — обновляется metadata последней + короткий ntfy."""
    sample_ids = ", ".join("#" + i["id"] for i in incidents[:5])
    conn = _db_connect()
    try:
        with conn.cursor() as cur:
            # [v150.28] Security-кэш: сравнить множество ID с последней сводной задачей
            new_hash = _incidents_hash(incidents)
            new_ids = {str(i["id"]) for i in incidents}
            try:
                cur.execute(
                    """
                    SELECT id, metadata FROM tasks
                    WHERE title LIKE '🛡️ Security:%'
                      AND metadata->>'consolidated' = 'true'
                    ORDER BY created_at DESC LIMIT 1
                    """
                )
                last = cur.fetchone()
            except Exception as e:
                log_alert(f"[{datetime.now(timezone.utc).isoformat()}] CACHE LOOKUP ERROR: {e}")
                last = None

            if last is not None:
                last_meta = last[1] or {}
                old_ids = set(last_meta.get("incident_ids") or [])
                old_hash = last_meta.get("incident_hash")
                if old_hash == new_hash:
                    # Идентичное множество → задача не создаётся, обновляем metadata
                    try:
                        meta = dict(last_meta)
                        meta["incident_count"] = len(incidents)
                        meta["updated_at"] = datetime.now(timezone.utc).isoformat()
                        cur.execute(
                            "UPDATE tasks SET metadata = %s WHERE id = %s",
                            (json.dumps(meta, ensure_ascii=False), last[0]),
                        )
                        conn.commit()
                    except Exception:
                        pass
                    _notify_ntfy(f"🛡️ Security: без изменений ({len(incidents)} инцидентов)")
                    return "cached"
                if old_ids:
                    overlap = len(new_ids & old_ids) / max(1, len(old_ids))
                    if overlap >= 0.9:
                        only_new = [i for i in incidents if str(i["id"]) not in old_ids]
                        # Есть новинки (<10% diff) — задача только для НОВЫХ инцидентов
                        incidents = only_new
                        sample_ids = ", ".join("#" + i["id"] for i in incidents[:5])
                        if not incidents:
                            _notify_ntfy(
                                f"🛡️ Security: без изменений (overlap {overlap:.0%})"
                            )
                            return "cached"
                        top_types = f"{top_types} (из них {len(incidents)} новых)"
                        # Важно: после урезания до новых инцидентов пересчитать хеш/ids.
                        new_hash = _incidents_hash(incidents)
                        new_ids = {str(i["id"]) for i in incidents}

            # [v150.16] дедуп: не чаще 1 сводной задачи в час по префиксу title.
            # Применяется только после cache-check: identical/overlap проходят как "cached".
            if _recent_security_task_exists(cur):
                log_alert(
                    f"[{datetime.now(timezone.utc).isoformat()}] RATELIMIT: сводная security-задача "
                    f"за последний час уже существует — пропуск ({len(incidents)} инцидентов, {top_types[:80]})"
                )
                return "skipped"

            # [v150.32] Если уже есть открытая сводная security-задача,
            # не создаём новую каждый час, а обновляем текущую.
            cur.execute(
                """
                SELECT id, metadata
                FROM tasks
                WHERE status IN ('pending', 'in_progress')
                  AND metadata->>'source' = 'security_responder'
                  AND metadata->>'consolidated' = 'true'
                ORDER BY updated_at DESC
                LIMIT 1
                """
            )
            open_row = cur.fetchone()
            if open_row is not None:
                open_id, open_meta = open_row
                merged_meta = dict(open_meta or {})
                merged_meta.update(
                    {
                        "incident_hash": new_hash,
                        "incident_ids": sorted(new_ids),
                        "incident_count": len(incidents),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                        "last_error": None,
                    }
                )
                cur.execute(
                    """
                    UPDATE tasks
                    SET title = %s,
                        description = %s,
                        metadata = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (
                        f"🛡️ Security: {len(incidents)} инцидентов ({top_types[:80]})",
                        (
                            f"Период: последние {LOOKBACK_HOURS}ч. Инциденты: {sample_ids}.\n"
                            "Требуется: групповой анализ кампании атак (источники, паттерны), "
                            "усиление фильтров, отчёт с мерами."
                        ),
                        json.dumps(merged_meta, ensure_ascii=False),
                        open_id,
                    ),
                )
                conn.commit()
                return "updated_open"

            cur.execute(
                """
                INSERT INTO tasks (title, description, status, priority, metadata, project_context)
                VALUES (%s, %s, 'pending', 'high', %s, 'atra-web-ide')
                """,
                (
                    f"🛡️ Security: {len(incidents)} инцидентов ({top_types[:80]})",
                    (
                        f"Период: последние {LOOKBACK_HOURS}ч. Инциденты: {sample_ids}.\n"
                        "Требуется: групповой анализ кампании атак (источники, паттерны), "
                        "усиление фильтров, отчёт с мерами."
                    ),
                    json.dumps({
                        "source": "security_responder",
                        "consolidated": True,
                        # [v150.28] Security-кэш
                        "incident_hash": new_hash,
                        "incident_ids": sorted(new_ids),
                        "incident_count": len(incidents),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }),
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
    try:
        incidents = fetch_new_incidents()
    except Exception as e:
        log_alert(f"[{datetime.now(timezone.utc).isoformat()}] DB CONNECT ERROR: {e}")
        print(f"⚠️ DB temporarily unavailable, skip cycle: {e}")
        return 0
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

    # Консолидация: одна сводная задача на запуск (200+ инцидентов/день = спам задач недопустим)
    types_summary = {}
    for incident in fresh:
        types_summary[incident["anomaly_type"]] = types_summary.get(incident["anomaly_type"], 0) + 1
    top_types = "; ".join(f"{t} x{n}" for t, n in sorted(types_summary.items(), key=lambda x: -x[1]))
    sample_ids = ", ".join("#" + i["id"] for i in fresh[:5])

    result = create_response_task_consolidated(fresh, top_types)
    if result == "cached":
        # [v150.28] Security-кэш: множество инцидентов не изменилось — фиксируем без новой задачи
        for incident in fresh:
            state["processed"].append(incident["id"])
        save_state(state)
        print(f"🛡️ Без изменений ({len(fresh)} инцидентов) — задача не создана (кэш)")
        return 0
    if result == "updated_open":
        # [v150.32] Обновили существующую активную сводную задачу без нового алерта.
        for incident in fresh:
            state["processed"].append(incident["id"])
        save_state(state)
        print(f"🛡️ Обновлена текущая сводная задача ({len(fresh)} инцидентов), новая не создавалась")
        return 0
    if result == "skipped":
        # [v150.16] рейт-лимит: инциденты фиксируем в state, чтобы не гонять
        # одну и ту же партию каждый запуск до истечения часа
        for incident in fresh:
            state["processed"].append(incident["id"])
        save_state(state)
        print("⏱️ Рейт-лимит: сводная задача за последний час уже была — инциденты зафиксированы без задачи")
        return 0
    if result:
        for incident in fresh:
            state["processed"].append(incident["id"])
        log_alert(
            f"[{datetime.now(timezone.utc).isoformat()}] Консолидировано {len(fresh)} инцидентов "
            f"({top_types}) — сводная задача создана"
        )
        _notify_ntfy(
            f"🛡️ ATRA Security: {len(fresh)} инцидентов ({top_types}). "
            f"Создана сводная задача на разбор."
        )
        notify_telegram(
            f"🛡️ ATRA Security: {len(fresh)} инцидентов ({top_types}) — сводная задача создана."
        )
        save_state(state)
        print(f"🛡️ Сводная задача создана ({len(fresh)} инцидентов)")
    else:
        # не помечаем processed — повторится при следующем запуске
        print("⚠️ Не удалось создать сводную задачу — повторится при следующем запуске")
    return 0


if __name__ == "__main__":
    sys.exit(main())
