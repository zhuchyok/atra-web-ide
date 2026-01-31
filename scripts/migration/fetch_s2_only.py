#!/usr/bin/env python3
"""
Повторная загрузка только с Server 2 (46.149.66.170).
Использовать, если основной скрипт упал по таймауту на S2.
Тар только knowledge_os (быстрее). Таймаут tar: 30 мин.
"""

import sys
import subprocess
import shutil
from pathlib import Path

S2 = "46.149.66.170"
USER = "root"
P2 = "tT@B43Td21w?NB"
HOME = Path.home()
M2 = HOME / "migration" / "server2"
SSH_OPTS = "-o StrictHostKeyChecking=no -o ServerAliveInterval=15 -o ServerAliveCountMax=6 -o ConnectTimeout=20"
TAR_TIMEOUT = 1800  # 30 min


def run(cmd, check=True, capture=True, timeout=300):
    r = subprocess.run(
        cmd, shell=True, check=check, capture_output=capture, text=True, timeout=timeout
    )
    return ((r.stdout or "") + (r.stderr or "")) if capture else ""


def ssh_run(script, timeout=600):
    pass_esc = P2.replace("'", "'\"'\"'")
    cmd = f"sshpass -p '{pass_esc}' ssh {SSH_OPTS} {USER}@{S2} {script!r}"
    return run(cmd, check=True, timeout=timeout)


def scp_from(remote_path, local_path, timeout=900):
    local_path = Path(local_path)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    pass_esc = P2.replace("'", "'\"'\"'")
    cmd = f"sshpass -p '{pass_esc}' scp {SSH_OPTS} {USER}@{S2}:{remote_path} {local_path!s}"
    return run(cmd, check=True, timeout=timeout)


def log(msg):
    print(msg, flush=True)


def main():
    log("=" * 60)
    log("ЗАГРУЗКА ТОЛЬКО S2 (46.149.66.170)")
    log("=" * 60)
    if shutil.which("sshpass") is None:
        log("Установите sshpass: brew install hudochenkov/sshpass/sshpass")
        sys.exit(1)
    M2.mkdir(parents=True, exist_ok=True)
    log(f"Каталог: {M2}\n")

    try:
        log("[1/4] mkdir на S2...")
        ssh_run("mkdir -p /root/migration_tmp", timeout=30)
        log("[2/4] pg_dump...")
        ssh_run(
            "docker exec knowledge_os_db pg_dump -U admin knowledge_os > /root/migration_tmp/knowledge_os.sql 2>/dev/null || "
            "docker exec knowledge_postgres pg_dump -U admin knowledge_os > /root/migration_tmp/knowledge_os.sql 2>/dev/null || "
            "sudo -u postgres pg_dump -U postgres knowledge_os > /root/migration_tmp/knowledge_os.sql 2>/dev/null || true",
            timeout=600,
        )
        log(f"[3/4] tar knowledge_os (таймаут {TAR_TIMEOUT}s)...")
        ssh_run(
            "cd /root && (tar -czvf /root/migration_tmp/s2_brain.tar.gz knowledge_os 2>/dev/null) || true",
            timeout=TAR_TIMEOUT,
        )
        log("[4/4] scp...")
        for name, remote in [
            ("knowledge_os.sql", "/root/migration_tmp/knowledge_os.sql"),
            ("s2_brain.tar.gz", "/root/migration_tmp/s2_brain.tar.gz"),
        ]:
            try:
                scp_from(remote, M2 / name)
                if (M2 / name).exists() and (M2 / name).stat().st_size > 0:
                    sz = run(f"du -h {M2/name}", capture=True).split()[0]
                    log(f"  OK {name} ({sz})")
            except Exception as e:
                log(f"  skip {name}: {e}")
        ssh_run("rm -rf /root/migration_tmp", timeout=15)
        log("\nГотово. Дальше: python3 scripts/migration/restore_only.py")
    except Exception as e:
        log(f"Ошибка: {e}")
        sys.exit(1)
    log("=" * 60)


if __name__ == "__main__":
    main()
