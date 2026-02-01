#!/usr/bin/env bash
# Поиск узлов знаний на MacBook (запускать НА MacBook, где делали миграцию)
# Использование: bash scripts/search_knowledge_on_macbook.sh

set -e
echo "🔍 Поиск узлов знаний на этой машине ($(hostname))"
echo ""

# 1. Проверка ~/migration
echo "📁 ~/migration:"
if [ -d ~/migration ]; then
  find ~/migration -type f \( -name "*.sql" -o -name "*.dump" -o -name "*.json" \) -exec ls -la {} \;
  for f in ~/migration/server2/knowledge_os_dump.sql ~/migration/server2/knowledge_os_dump.dump; do
    if [ -f "$f" ]; then
      echo "   $(ls -lh "$f" | awk '{print $5, $9}')"
    fi
  done
else
  echo "   Папка не найдена"
fi
echo ""

# 2. Проверка Docker volumes
echo "🐳 Docker volumes (postgres, knowledge):"
docker volume ls 2>/dev/null | grep -iE "postgres|knowledge" || echo "   Docker недоступен"
echo ""

# 3. Подсчёт узлов в knowledge_postgres (если запущен)
echo "📊 Узлов в knowledge_postgres:"
if docker ps --format "{{.Names}}" | grep -q knowledge_postgres 2>/dev/null; then
  docker exec knowledge_postgres psql -U admin -d knowledge_os -t -c "SELECT COUNT(*) FROM knowledge_nodes;" 2>/dev/null || echo "   Ошибка запроса"
else
  echo "   Контейнер не запущен"
fi
echo ""

# 4. Поиск больших SQL-файлов
echo "📄 SQL-файлы >1MB в домашней директории:"
find ~ -maxdepth 5 -name "*.sql" -size +1M 2>/dev/null | head -10 || echo "   Не найдено"
echo ""

# 5. Проверка бэкапов проекта
echo "📦 backups/migration:"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT" 2>/dev/null || cd ~/Documents/atra-web-ide 2>/dev/null || true
if [ -d backups/migration ]; then
  find backups/migration -name "*.tar.gz" -exec ls -lh {} \;
  # Ищем volume-архивы (postgres data)
  for d in backups/migration/*/; do
    if [ -f "${d}atra_knowledge_postgres_data.tar.gz" ] || [ -f "${d}knowledge_os_postgres_data.tar.gz" ]; then
      echo "   ✅ Найден volume postgres!"
      ls -lh "${d}"*postgres*.tar.gz 2>/dev/null
    fi
  done
else
  echo "   Папка не найдена"
fi
echo ""

echo "✅ Поиск завершён. Скопируйте вывод и отправьте на Mac Studio."
