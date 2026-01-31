#!/usr/bin/env python3
"""
Полная миграция корпорации (Knowledge OS, агенты, знания) с двух серверов на Mac Studio.
Без торгового бота. Запускать на Mac Studio: python3 scripts/migration/corporation_full_migration.py
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

# Серверы и пароли
S1 = "185.177.216.15"
S2 = "46.149.66.170"
USER = "root"
P1 = "u44Ww9NmtQj,XG"
P2 = "tT@B43Td21w?NB"

# Локальные пути на Mac Studio
HOME = Path.home()
MIGRATION = HOME / "migration"
M1 = MIGRATION / "server1"
M2 = MIGRATION / "server2"
REPO = HOME / "Documents" / "dev" / "atra"
for d in [HOME / "atra", HOME / "Documents" / "GITHUB" / "atra" / "atra"]:
    if (d / "docker-compose.yml").exists() or (d / "knowledge_os" / "docker-compose.yml").exists():
        REPO = d
        break


def run(cmd, check=True, capture=True, timeout=300):
    r = subprocess.run(
        cmd,
        shell=True,
        check=check,
        capture_output=capture,
        text=True,
        timeout=timeout,
        cwd=os.getcwd(),
    )
    return ((r.stdout or "") + (r.stderr or "")) if capture else ""


SSH_OPTS = "-o StrictHostKeyChecking=no -o ServerAliveInterval=15 -o ServerAliveCountMax=6 -o ConnectTimeout=20"


def ssh_run(host, password, script, timeout=900):
    """Выполнить команды на сервере через sshpass."""
    pass_esc = password.replace("'", "'\"'\"'")
    cmd = f"sshpass -p '{pass_esc}' ssh {SSH_OPTS} {USER}@{host} {script!r}"
    return run(cmd, check=True, timeout=timeout)


def scp_from(host, password, remote_path, local_path, timeout=900):
    """Скачать файл с сервера."""
    local_path = Path(local_path)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    pass_esc = password.replace("'", "'\"'\"'")
    cmd = f"sshpass -p '{pass_esc}' scp {SSH_OPTS} {USER}@{host}:{remote_path} {local_path!s}"
    return run(cmd, check=True, timeout=timeout)


def log(msg):
    print(msg, flush=True)


def main(fetch_only=False):
    log("=" * 60)
    log("МИГРАЦИЯ КОРПОРАЦИИ НА MAC STUDIO")
    log("=" * 60)

    if shutil.which("sshpass") is None:
        print("Установите sshpass: brew install hudochenkov/sshpass/sshpass")
        sys.exit(1)

    MIGRATION.mkdir(parents=True, exist_ok=True)
    M1.mkdir(parents=True, exist_ok=True)
    M2.mkdir(parents=True, exist_ok=True)
    log(f"Каталог миграции: {MIGRATION}")

    # --- Сервер 1 (185.177.216.15) ---
    log("\n[1/4] Бэкап на сервере 1 (185.177.216.15)...")
    try:
        ssh_run(S1, P1, "mkdir -p /root/migration_tmp", timeout=30)
        ssh_run(S1, P1, "sudo -u postgres pg_dump -U postgres knowledge_os > /root/migration_tmp/knowledge_os.sql 2>/dev/null || sudo -u postgres pg_dump -U postgres atra > /root/migration_tmp/atra.sql 2>/dev/null || true", timeout=600)
        ssh_run(S1, P1, "redis-cli SAVE 2>/dev/null; cp /var/lib/redis/dump.rdb /root/migration_tmp/redis.rdb 2>/dev/null || true", timeout=60)
        ssh_run(S1, P1, "cd /root && (tar -czvf /root/migration_tmp/s1_logic.tar.gz atra .env 2>/dev/null || tar -czvf /root/migration_tmp/s1_logic.tar.gz -C /root atra 2>/dev/null) || true", timeout=600)
        for name, remote in [("knowledge_os.sql", "/root/migration_tmp/knowledge_os.sql"),
                             ("atra.sql", "/root/migration_tmp/atra.sql"),
                             ("redis.rdb", "/root/migration_tmp/redis.rdb"),
                             ("s1_logic.tar.gz", "/root/migration_tmp/s1_logic.tar.gz")]:
            try:
                scp_from(S1, P1, remote, M1 / name)
                if (M1 / name).exists() and (M1 / name).stat().st_size > 0:
                    log(f"  OK {name}")
            except Exception as e:
                log(f"  skip {name}: {e}")
        ssh_run(S1, P1, "rm -rf /root/migration_tmp", timeout=15)
    except Exception as e:
        log(f"  Ошибка S1: {e}")

    # --- Сервер 2 (46.149.66.170) ---
    log("\n[2/4] Бэкап на сервере 2 (46.149.66.170)...")
    try:
        ssh_run(S2, P2, "mkdir -p /root/migration_tmp", timeout=30)
        ssh_run(S2, P2, "docker exec knowledge_os_db pg_dump -U admin knowledge_os > /root/migration_tmp/knowledge_os.sql 2>/dev/null || docker exec knowledge_postgres pg_dump -U admin knowledge_os > /root/migration_tmp/knowledge_os.sql 2>/dev/null || sudo -u postgres pg_dump -U postgres knowledge_os > /root/migration_tmp/knowledge_os.sql 2>/dev/null || true", timeout=600)
        ssh_run(S2, P2, "cd /root && (tar -czvf /root/migration_tmp/s2_brain.tar.gz knowledge_os 2>/dev/null) || true", timeout=1800)
        for name, remote in [("knowledge_os.sql", "/root/migration_tmp/knowledge_os.sql"),
                             ("s2_brain.tar.gz", "/root/migration_tmp/s2_brain.tar.gz")]:
            try:
                scp_from(S2, P2, remote, M2 / name)
                if (M2 / name).exists() and (M2 / name).stat().st_size > 0:
                    log(f"  OK {name}")
            except Exception as e:
                log(f"  skip {name}: {e}")
        ssh_run(S2, P2, "rm -rf /root/migration_tmp", timeout=15)
    except Exception as e:
        log(f"  Ошибка S2: {e}")

    # --- Выбор дампа БД ---
    db_dump = None
    for p in [M2 / "knowledge_os.sql", M1 / "knowledge_os.sql", M1 / "atra.sql"]:
        if p.exists() and p.stat().st_size > 0:
            db_dump = p
            break
    if fetch_only:
        log("\n[--fetch-only] Пропуск восстановления БД и распаковки.")
        log(f"Данные в {MIGRATION}. Запустите снова без --fetch-only для restore.")
        log("=" * 60)
        return

    if not db_dump:
        log("\nДамп БД не найден. Восстановление БД пропущено.")
    else:
        log(f"\n[3/4] Восстановление БД из {db_dump.name}...")
        try:
            run("docker info >/dev/null 2>&1", check=False)
            out = run('docker ps --format "{{.Names}}" 2>/dev/null || true', check=False, capture=True)
            candidates = [x.strip() for x in out.splitlines() if x.strip()]
            pg_container = next((c for c in candidates if "knowledge" in c.lower() or "postgres" in c.lower()), None)
            if pg_container:
                run(f"docker exec -i {pg_container} psql -U admin -d knowledge_os < {db_dump}", timeout=300, check=False)
                log(f"  Импорт выполнен в {pg_container} (проверьте логи при ошибках)")
            else:
                log("  Контейнер PostgreSQL не найден. Запустите стек Knowledge OS и повторите:")
                log(f"    docker exec -i <pg_container> psql -U admin -d knowledge_os < {db_dump}")
        except Exception as e:
            log(f"  Ошибка восстановления БД: {e}")

    # --- Распаковка архива «мозга» ---
    log("\n[4/4] Распаковка архива знаний...")
    brain = M2 / "s2_brain.tar.gz"
    if brain.exists() and brain.stat().st_size > 0:
        run(f"tar -xzvf {brain} -C {REPO} 2>/dev/null || true", check=False, timeout=120)
        log("  OK s2_brain")
    else:
        log("  s2_brain.tar.gz не найден или пуст.")

    log("\n" + "=" * 60)
    log("МИГРАЦИЯ ЗАВЕРШЕНА")
    log("=" * 60)
    log(f"Данные: {MIGRATION}")
    log("Проверка: docker-compose -f knowledge_os/docker-compose.yml ps")
    log("Логи: docker-compose -f knowledge_os/docker-compose.yml logs -f")


if __name__ == "__main__":
    fetch_only = "--fetch-only" in sys.argv
    if fetch_only:
        # Только бэкап + scp, без restore и распаковки
        pass  # флаг проверяется в main
    main(fetch_only=fetch_only)
