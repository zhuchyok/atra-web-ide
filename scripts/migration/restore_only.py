#!/usr/bin/env python3
"""
Только восстановление: импорт БД и распаковка архива.
Запускать, когда данные уже в ~/migration (например, после --fetch-only или ручного scp).
"""

import os
import subprocess
import shutil
from pathlib import Path

HOME = Path.home()
MIGRATION = HOME / "migration"
M1, M2 = MIGRATION / "server1", MIGRATION / "server2"
REPO = HOME / "Documents" / "dev" / "atra"
for d in [HOME / "atra", HOME / "Documents" / "GITHUB" / "atra" / "atra"]:
    if d.exists() and ((d / "docker-compose.yml").exists() or (d / "knowledge_os" / "docker-compose.yml").exists()):
        REPO = d
        break


def run(cmd, check=True, capture=True, timeout=300):
    try:
        r = subprocess.run(cmd, shell=True, check=check, capture_output=capture, text=True, timeout=timeout)
        return ((r.stdout or "") + (r.stderr or "")) if capture else ""
    except subprocess.TimeoutExpired:
        return ""


def main():
    print("=" * 60)
    print("ВОССТАНОВЛЕНИЕ (restore only)")
    print("=" * 60)
    if not MIGRATION.exists():
        print("Каталог ~/migration не найден. Сначала выполните миграцию.")
        return

    db_dump = None
    for p in [M2 / "knowledge_os_dump.sql", M2 / "knowledge_os.sql", M1 / "knowledge_os.sql", M1 / "atra.sql"]:
        if p.exists() and p.stat().st_size > 0:
            db_dump = p
            break

    if db_dump:
        print(f"\n[1/2] Импорт БД из {db_dump.name}...")
        skip_docker = os.environ.get("RESTORE_SKIP_DOCKER", "").lower() in ("1", "true", "yes")
        if skip_docker:
            print("  RESTORE_SKIP_DOCKER=1: пропуск автоматического импорта.")
            print(f"  Вручную: docker exec -i knowledge_os_db psql -U admin -d knowledge_os < {db_dump}")
        else:
            pg = None
            try:
                r = subprocess.run(
                    "docker info >/dev/null 2>&1 && docker ps --format '{{.Names}}' 2>/dev/null",
                    shell=True, capture_output=True, text=True, timeout=8
                )
                out = (r.stdout or "") + (r.stderr or "")
                candidates = [x.strip() for x in out.splitlines() if x.strip()]
                pg = next((c for c in candidates if "_db" in c or "postgres" in c.lower()), None)
                if not pg:
                    pg = next((c for c in candidates if "knowledge" in c.lower()), None)
            except (subprocess.TimeoutExpired, Exception):
                pass
            if pg:
                try:
                    run(f"docker exec -i {pg} psql -U admin -d knowledge_os < {db_dump}", timeout=600, check=False)
                    print(f"  Импорт в {pg}")
                except Exception as e:
                    print(f"  Ошибка: {e}")
            else:
                print("  Docker не запущен или контейнер не найден. Вручную:")
                print(f"    docker exec -i knowledge_os_db psql -U admin -d knowledge_os < {db_dump}")
    else:
        print("\n[1/2] Дамп БД не найден, пропуск.")

    brain = M2 / "s2_brain.tar.gz"
    print("\n[2/2] Распаковка s2_brain...")
    if brain.exists() and brain.stat().st_size > 0:
        run(f"tar -xzvf {brain} -C {REPO} 2>/dev/null || true", check=False, timeout=120)
        print("  OK")
    else:
        print("  s2_brain.tar.gz не найден.")

    print("\n" + "=" * 60)
    print("ГОТОВО")
    print("=" * 60)


if __name__ == "__main__":
    main()
