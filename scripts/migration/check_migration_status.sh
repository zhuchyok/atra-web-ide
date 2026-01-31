#!/bin/bash
# Проверка статуса миграции и следующих шагов
M="${HOME}/migration"
S1="${M}/server1"
S2="${M}/server2"

echo "=============================================="
echo "СТАТУС МИГРАЦИИ КОРПОРАЦИИ"
echo "=============================================="
echo ""

if [ ! -d "$M" ]; then
  echo "Каталог ~/migration не найден. Запустите миграцию."
  exit 1
fi

echo "Каталог: $M"
echo ""

echo "Server 1:"
for f in knowledge_os.sql atra.sql redis.rdb s1_logic.tar.gz; do
  [ -f "$S1/$f" ] && echo "  OK $f ($(du -h "$S1/$f" | cut -f1))" || echo "  — $f"
done

echo ""
echo "Server 2:"
for f in knowledge_os.sql s2_brain.tar.gz; do
  [ -f "$S2/$f" ] && echo "  OK $f ($(du -h "$S2/$f" | cut -f1))" || echo "  — $f"
done

echo ""
if pgrep -f "corporation_full_migration" >/dev/null 2>&1; then
  echo "Миграция в процессе. Лог: tail -f ~/migration/migration.log"
elif pgrep -f "fetch_s2_only" >/dev/null 2>&1; then
  echo "Загрузка S2 в процессе. Лог: tail -f ~/migration/fetch_s2.log"
else
  echo "Миграция не запущена."
  [ ! -f "$S2/knowledge_os.sql" ] && [ ! -f "$S2/s2_brain.tar.gz" ] && echo "  S2 пуст? Повторите: python3 scripts/migration/fetch_s2_only.py"
fi

echo ""
echo "Агенты (Victoria/Veronica):"
echo "  Проверка: bash scripts/migration/verify_agents.sh"
echo "  Запуск (после Docker): bash scripts/migration/up_agents_after_docker.sh"
echo ""
echo "Восстановление / стек:"
if ( perl -e 'alarm 6; exec @ARGV' - docker info >/dev/null 2>&1 ) 2>/dev/null; then
  PG=$(perl -e 'alarm 5; exec @ARGV' - docker ps --format '{{.Names}}' 2>/dev/null | grep -E "knowledge|postgres" | head -1)
  if [ -n "$PG" ]; then
    echo "  Docker OK, контейнер: $PG"
    [ -f "$S2/knowledge_os.sql" ] || [ -f "$S1/knowledge_os.sql" ] && echo "  БД: python3 scripts/migration/restore_only.py"
  else
    echo "  Запустите стек: bash scripts/migration/up_agents_after_docker.sh"
  fi
else
  echo "  Docker не запущен или не отвечает. Запустите Docker Desktop, затем: bash scripts/migration/up_agents_after_docker.sh"
fi

echo ""
echo "=============================================="
