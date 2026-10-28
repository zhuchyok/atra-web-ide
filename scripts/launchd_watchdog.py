"""Watchdog за launchd-джобами ATRA — проверяет, что автоматика жива.

Каждый час (launchd com.atra.watchdog-jobs): для каждой критичной джобы смотрит
launchctl list (последний exit code) и freshness её лога/артефакта. Если джоба
не загружена или падала — создаёт задачу на разбор и шлёт Telegram один раз
за инцидент (state-файл).

Запуск: python3 scripts/launchd_watchdog.py
"""
import json
import os
import shutil  # [v150.27] disk_usage для диск-канарейки
import subprocess
import sys
import time
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
        state = json.loads(STATE_PATH.read_text())
        if "alerted" not in state:
            state["alerted"] = {}
        if "brain_canary_last_ts" not in state:
            state["brain_canary_last_ts"] = 0
        # Миграция: исторические "сырые" ключи -> нормализованные ключи дедупа.
        normalized = {}
        for raw_key, ts in state.get("alerted", {}).items():
            normalized[problem_key(raw_key)] = ts
        state["alerted"] = normalized
        return state
    return {"alerted": {}, "brain_canary_last_ts": 0}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=1))

def problem_key(problem: str) -> str:
    """Нормализуем ключ инцидента для дедупа алертов/задач.

    Иначе [DISK] с плавающими числами (%/GiB) создаёт новый "уникальный" алерт
    каждый запуск и раздувает очередь.
    """
    if problem.startswith("[DISK] свободно <"):
        return "[DISK] свободно <threshold%"
    if problem.startswith("[CANARY] "):
        # Ключ до двоеточия: стабильный идентификатор проверяемого канареечного узла.
        return problem.split(":", 1)[0]
    if problem.startswith("[CURSOR-DB] "):
        return "[CURSOR-DB] threshold"
    if problem.startswith("[CURSOR-GROWTH] "):
        return "[CURSOR-GROWTH] threshold"
    if problem.startswith("[DISK-GROWTH] "):
        return "[DISK-GROWTH] threshold"
    return problem




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
    try:
        import psycopg2
    except Exception as e:
        print(f"DB driver unavailable (psycopg2): {e}")
        return False

    dsn = os.environ.get("ATRA_DB_DSN", "postgresql://admin:secret@127.0.0.1:6432/knowledge_os")  # pragma: allowlist secret
    conn = None
    for attempt in range(1, 4):
        try:
            conn = psycopg2.connect(dsn)
            break
        except Exception as e:
            if attempt == 3:
                print(f"DB connect error: {e}")
                return False
            time.sleep(attempt)

    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            # Не плодим дублей: если уже есть открытая watchdog-задача, не создаём новую.
            cur.execute(
                """
                SELECT id FROM tasks
                WHERE status IN ('pending', 'in_progress')
                  AND metadata->>'source' = 'launchd_watchdog'
                ORDER BY created_at DESC
                LIMIT 1
                """
            )
            existing = cur.fetchone()
            if existing:
                print(f"Watchdog task already open: {existing[0]}")
                return True

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


def _db_connect():
    """Shared DB connect helper with short retries for launchd context."""
    try:
        import psycopg2
    except Exception:
        return None
    dsn = os.environ.get("ATRA_DB_DSN", "postgresql://admin:secret@127.0.0.1:6432/knowledge_os")  # pragma: allowlist secret
    for attempt in range(1, 4):
        try:
            return psycopg2.connect(dsn)
        except Exception:
            if attempt == 3:
                return None
            time.sleep(attempt)
    return None


def _auto_close_stale_internal_tails() -> None:
    """Close stale synthetic/internal tails that no longer progress."""
    max_age_h = int(os.environ.get("WATCHDOG_STALE_INTERNAL_HOURS", "8"))
    sources_env = os.environ.get(
        "WATCHDOG_STALE_INTERNAL_SOURCES",
        "nightly_hypothesis_debate,launchd_watchdog,predictive_monitor",
    )
    sources = [s.strip() for s in sources_env.split(",") if s.strip()]
    if not sources:
        return
    conn = _db_connect()
    if conn is None:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE tasks
                SET status='cancelled',
                    completed_at=NOW(),
                    updated_at=NOW(),
                    result=COALESCE(result,'') ||
                      E'\\n[auto-close] stale internal tail closed by launchd_watchdog',
                    metadata = COALESCE(metadata, '{}'::jsonb) ||
                      jsonb_build_object(
                        'auto_closed_by','launchd_watchdog',
                        'auto_closed_at',NOW()::text,
                        'auto_close_reason','stale_internal_tail'
                      )
                WHERE status IN ('pending','in_progress')
                  AND COALESCE(metadata->>'source','') = ANY(%s)
                  AND updated_at < NOW() - (%s || ' hours')::INTERVAL
                """,
                (sources, str(max_age_h)),
            )
            changed = cur.rowcount
        conn.commit()
        if changed:
            print(f"[TAIL-CLOSE] closed stale internal tasks: {changed}")
    except Exception as e:
        print(f"[TAIL-CLOSE] error: {e}")
    finally:
        conn.close()


def _metadata_hygiene(state: dict) -> None:
    """Monthly cleanup of transient metadata keys on terminal tasks."""
    cadence_days = int(os.environ.get("TASK_METADATA_HYGIENE_EVERY_DAYS", "30"))
    retain_days = int(os.environ.get("TASK_METADATA_HYGIENE_RETAIN_DAYS", "30"))
    now_ts = time.time()
    last_ts = float(state.get("metadata_hygiene_last_ts", 0))
    if now_ts - last_ts < cadence_days * 24 * 3600:
        return

    conn = _db_connect()
    if conn is None:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE tasks
                SET metadata =
                    (COALESCE(metadata, '{}'::jsonb)
                      - 'dispatch_attempts'
                      - 'pending_dispatch_timeout_count'
                      - 'dispatched_to_stream_at'
                      - 'next_retry_after'
                      - 'processing_started_at'
                      - 'stale_requeued_at'
                      - 'llm_stub_retries')
                WHERE status IN ('completed','failed','cancelled')
                  AND updated_at < NOW() - (%s || ' days')::INTERVAL
                  AND metadata IS NOT NULL
                """,
                (str(retain_days),),
            )
            changed = cur.rowcount
        conn.commit()
        state["metadata_hygiene_last_ts"] = now_ts
        print(f"[META-HYGIENE] cleaned terminal metadata rows: {changed}")
    except Exception as e:
        print(f"[META-HYGIENE] error: {e}")
    finally:
        conn.close()


def http_canaries(state: dict) -> list:
    """[v150.3] Генерационные канарейки: сервис «запущен» ≠ «отвечает».

    launchd говорит только «джоба загружена, exit 0» — живость инференса это не
    гарантирует (ollama может отдавать 503 после сегфолта, эмбеддер — висеть).
    Поэтому дергаем реальную генерацию/энкодинг с минимальным num_predict.
    Таймауты большие: холодная загрузка модели в память — легитимна.
    """
    canaries = [
        # (имя, url, payload, таймаут в секундах)
        # [v150.8] руки — на выделенном инстансе 11437; мозг проверяем отдельно
        (
            "hands phi3.5@11437",
            "http://127.0.0.1:11437/api/generate",
            {"model": "phi3.5:3.8b", "prompt": "ok", "stream": False,
             "options": {"num_predict": 1, "num_ctx": 2048}},
            180,
        ),
        # Brain canary can amplify warmup flaps right after watchdog restart.
        # Run it less frequently, and skip while watchdog marks brain as not-ready.
        # [v150.14] MLX-канарейка снят: узел декомиссирован (вне маршрутизации
        # с v150.10, прокси мёртв с 14.10 — возврат: env MLX_API_URL + bootstrap)
        (
            "text-embeddings /encode",
            "http://127.0.0.1:8001/encode",
            {"text": "canary"},
            30,
        ),
    ]
    problems = []
    now_ts = datetime.now().timestamp()
    brain_every_sec = int(os.environ.get("LAUNCHD_WD_BRAIN_CANARY_EVERY_SEC", "300"))
    brain_not_ready_flag = Path("/tmp/atra_runtime_state/brain_11434_not_ready")
    run_brain_canary = (
        not brain_not_ready_flag.exists()
        and (now_ts - float(state.get("brain_canary_last_ts", 0))) >= brain_every_sec
    )
    if run_brain_canary:
        canaries.append(
            (
                "brain victoria-qwen38@11434",
                "http://127.0.0.1:11434/api/generate",
                {"model": "victoria-qwen38:latest", "prompt": "ok", "stream": False,
                 "options": {"num_predict": 1, "num_ctx": 2048}},
                240,
            )
        )

    for name, url, payload, timeout in canaries:
        try:
            req = urllib.request.Request(
                url, data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=timeout)
            if name.startswith("brain victoria-qwen38@11434"):
                state["brain_canary_last_ts"] = now_ts
        except Exception as e:
            problems.append(f"[CANARY] {name}: {url} не отвечает ({e})")

    # [v150.27] диск-канарейка.
    # По умолчанию сигналим при free% < 12 (вместо 15), чтобы убрать ложный
    # шум на рабочем коридоре 12-15% и фокусироваться на реальном риске.
    # При необходимости порог задаётся env: LAUNCHD_WD_DISK_MIN_FREE_PCT.
    try:
        du = shutil.disk_usage("/")
        free_pct = du.free / du.total * 100
        min_free_pct = float(os.environ.get("LAUNCHD_WD_DISK_MIN_FREE_PCT", "12.0"))
        if free_pct < min_free_pct:
            problems.append(
                f"[DISK] свободно <{min_free_pct:.1f}% ({free_pct:.1f}% свободно, "
                f"{du.free / (1 << 30):.1f}GiB из {du.total / (1 << 30):.1f}GiB)"
            )
    except Exception as e:
        problems.append(f"[DISK] проверка не удалась: {e}")
    return problems


def _cursor_size_watch(state: dict) -> list:
    """Контроль роста Cursor state DB + мягкая non-critical очистка."""
    problems = []
    cursor_root = Path.home() / "Library" / "Application Support" / "Cursor"
    state_db = cursor_root / "User" / "globalStorage" / "state.vscdb"
    snapshots = cursor_root / "snapshots"
    logs_dir = cursor_root / "logs"

    warn_gb = float(os.environ.get("CURSOR_STATE_DB_WARN_GB", "80"))
    growth_warn_gb = float(os.environ.get("CURSOR_STATE_DB_GROWTH_WARN_GB", "5"))
    growth_window_h = int(os.environ.get("CURSOR_STATE_DB_GROWTH_WINDOW_HOURS", "24"))
    logs_keep_days = int(os.environ.get("CURSOR_LOGS_KEEP_DAYS", "14"))
    snapshots_keep_days = int(os.environ.get("CURSOR_SNAPSHOTS_KEEP_DAYS", "7"))

    # 1) Soft cleanup: old logs and old snapshot entries (safe, no runtime data loss).
    freed_bytes = 0
    now_ts = time.time()
    logs_cutoff = now_ts - logs_keep_days * 24 * 3600
    snaps_cutoff = now_ts - snapshots_keep_days * 24 * 3600

    if logs_dir.exists():
        for f in logs_dir.rglob("*"):
            try:
                if f.is_file() and f.stat().st_mtime < logs_cutoff:
                    sz = f.stat().st_size
                    f.unlink()
                    freed_bytes += sz
            except Exception:
                pass

    if snapshots.exists():
        for entry in snapshots.iterdir():
            try:
                if entry.stat().st_mtime >= snaps_cutoff:
                    continue
                if entry.is_dir():
                    sz = sum(p.stat().st_size for p in entry.rglob("*") if p.is_file())
                    shutil.rmtree(entry, ignore_errors=True)
                    freed_bytes += sz
                elif entry.is_file():
                    sz = entry.stat().st_size
                    entry.unlink()
                    freed_bytes += sz
            except Exception:
                pass

    if freed_bytes > 0:
        print(f"[CURSOR-CLEANUP] freed ~{freed_bytes / (1 << 30):.2f} GiB")

    # 2) Size and growth tracking.
    if not state_db.exists():
        return problems

    size_bytes = state_db.stat().st_size
    size_gb = size_bytes / (1 << 30)
    if size_gb >= warn_gb:
        problems.append(f"[CURSOR-DB] state.vscdb {size_gb:.1f}GiB (warn >= {warn_gb:.1f}GiB)")

    samples = state.get("cursor_state_db_samples", [])
    samples.append({"ts": now_ts, "size": size_bytes})
    keep_from = now_ts - (growth_window_h + 2) * 3600
    samples = [s for s in samples if float(s.get("ts", 0)) >= keep_from]
    state["cursor_state_db_samples"] = samples

    baseline = None
    target_from = now_ts - growth_window_h * 3600
    for s in samples:
        if float(s.get("ts", 0)) <= target_from:
            baseline = s
            break
    if baseline is None and samples:
        baseline = samples[0]

    if baseline is not None:
        growth_gb = (size_bytes - int(baseline.get("size", size_bytes))) / (1 << 30)
        if growth_gb >= growth_warn_gb:
            problems.append(
                f"[CURSOR-GROWTH] state.vscdb +{growth_gb:.1f}GiB / {growth_window_h}h "
                f"(warn >= {growth_warn_gb:.1f}GiB)"
            )

    return problems


def _du_bytes(path: Path) -> int:
    """Fast size probe via du -sk (works for files and directories)."""
    try:
        r = subprocess.run(
            ["du", "-sk", str(path)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if r.returncode != 0:
            return -1
        kb = int((r.stdout.strip().split() or ["-1"])[0])
        return kb * 1024
    except Exception:
        return -1


def _disk_growth_watch(state: dict) -> list:
    """Top-growers report for key paths over 24h + threshold alert."""
    problems = []
    now_ts = time.time()
    report_every_h = int(os.environ.get("DISK_GROWTH_REPORT_EVERY_HOURS", "24"))
    growth_warn_gb = float(os.environ.get("DISK_GROWTH_WARN_GB_24H", "8"))
    report_path = REPO / "logs" / "disk_growth_report.log"

    watched = {
        "cursor_state_db": Path.home() / "Library" / "Application Support" / "Cursor" / "User" / "globalStorage" / "state.vscdb",
        "cursor_global_storage": Path.home() / "Library" / "Application Support" / "Cursor" / "User" / "globalStorage",
        "docker_raw": Path.home() / "Library" / "Containers" / "com.docker.docker" / "Data" / "vms" / "0" / "data" / "Docker.raw",
        "ollama_models": Path.home() / ".ollama" / "models",
        "ollama_veronica_blobs": Path.home() / ".ollama-veronica" / "blobs",
        "repo_backups": REPO / "backups",
    }

    current = {}
    for key, path in watched.items():
        if not path.exists():
            continue
        size = _du_bytes(path)
        if size >= 0:
            current[key] = {"path": str(path), "size": size, "ts": now_ts}

    if not current:
        return problems

    samples = state.get("disk_growth_samples", {})
    if not isinstance(samples, dict):
        samples = {}
    state["disk_growth_samples"] = samples

    # Keep both latest and baseline sample for each key.
    deltas = []
    baseline_from = now_ts - 24 * 3600
    for key, cur in current.items():
        entry = samples.get(key, {})
        if not isinstance(entry, dict):
            entry = {}
        baseline = entry.get("baseline")
        latest = entry.get("latest")

        if baseline is None:
            baseline = cur
        else:
            # Rotate baseline if too old/missing.
            if float(baseline.get("ts", 0)) < baseline_from:
                baseline = cur

        latest = cur
        samples[key] = {"baseline": baseline, "latest": latest}

        growth_bytes = int(latest["size"]) - int(baseline["size"])
        deltas.append(
            {
                "key": key,
                "path": latest["path"],
                "size_gb": latest["size"] / (1 << 30),
                "growth_gb": growth_bytes / (1 << 30),
                "window_h": (now_ts - float(baseline["ts"])) / 3600.0,
            }
        )

    # Raise if a watched path grows too fast over ~24h.
    for d in deltas:
        if d["window_h"] >= 20 and d["growth_gb"] >= growth_warn_gb:
            problems.append(
                f"[DISK-GROWTH] {d['key']} +{d['growth_gb']:.1f}GiB/{d['window_h']:.0f}h "
                f"(warn >= {growth_warn_gb:.1f}GiB)"
            )

    last_report_ts = float(state.get("disk_growth_last_report_ts", 0))
    if now_ts - last_report_ts >= report_every_h * 3600:
        top = sorted(deltas, key=lambda x: x["growth_gb"], reverse=True)[:6]
        lines = [
            f"[{datetime.now(timezone.utc).isoformat()}] DISK-GROWTH report ({report_every_h}h cadence)",
        ]
        for d in top:
            lines.append(
                f" - {d['key']}: size={d['size_gb']:.1f}GiB "
                f"delta={d['growth_gb']:+.2f}GiB window={d['window_h']:.0f}h"
            )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.open("a", encoding="utf-8").write("\n".join(lines) + "\n")
        print("[DISK-GROWTH] report written")
        state["disk_growth_last_report_ts"] = now_ts

    return problems


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

    # [v150.35] Operational hygiene: close stale synthetic tails + compact metadata.
    _auto_close_stale_internal_tails()
    _metadata_hygiene(state)

    # [v150.3] генерационные канарейки — до агрегации, чтобы попали в алерт/дедуп
    problems.extend(http_canaries(state))
    # [v150.33] Контроль роста Cursor state DB и безопасная soft-cleanup.
    problems.extend(_cursor_size_watch(state))
    # [v150.34] Контроль top-growers на диске и дневной отчёт по приросту.
    problems.extend(_disk_growth_watch(state))

    fresh_problems = []
    for p in problems:
        if problem_key(p) not in state["alerted"]:
            fresh_problems.append(p)
    if not fresh_problems:
        # Persist canary timestamps/state even when there are no new incidents.
        save_state(state)
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
            state["alerted"][problem_key(p)] = datetime.now(timezone.utc).isoformat()
        # держим не более 100 записей
        state["alerted"] = dict(list(state["alerted"].items())[-100:])
        save_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
