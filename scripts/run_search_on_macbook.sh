#!/usr/bin/env bash
# Запуск поиска на MacBook через SSH
# Сначала: ssh-copy-id bikos@192.168.1.38
# Затем: bash scripts/run_search_on_macbook.sh

MACBOOK_IP="${MACBOOK_IP:-192.168.1.38}"
MACBOOK_USER="${MACBOOK_USER:-bikos}"

echo "🔗 Подключение к MacBook ($MACBOOK_USER@$MACBOOK_IP)..."
echo ""

ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no "$MACBOOK_USER@$MACBOOK_IP" 'bash -s' << 'REMOTE'
echo "🔍 Поиск на $(hostname)"
echo ""

echo "📁 ~/migration/server2:"
ls -la ~/migration/server2/ 2>/dev/null || echo "   Не найдено"
for f in ~/migration/server2/knowledge_os_dump.sql ~/migration/server2/knowledge_os_dump.dump; do
  [ -f "$f" ] && echo "   $(ls -lh "$f" | awk "{print \$5, \$9}")"
done
echo ""

echo "🐳 Docker knowledge_postgres:"
docker exec knowledge_postgres psql -U admin -d knowledge_os -t -c "SELECT COUNT(*) FROM knowledge_nodes;" 2>/dev/null || echo "   Контейнер не запущен"
echo ""

echo "📄 SQL >1MB:"
find ~ -maxdepth 5 -name "*.sql" -size +1M 2>/dev/null | head -5 || echo "   Не найдено"
echo ""

echo "📦 backups/migration (volume tar.gz):"
find ~/Documents/atra-web-ide/backups -name "*postgres*.tar.gz" -o -name "*knowledge*data*.tar.gz" 2>/dev/null | xargs ls -lh 2>/dev/null || echo "   Не найдено"
echo ""

echo "✅ Готово"
REMOTE

echo ""
echo "Если нашли дамп — скопируйте на Mac Studio:"
echo "  scp bikos@192.168.1.38:~/migration/server2/knowledge_os_dump.sql ~/migration/server2/"
echo "  bash scripts/migrate_from_dump.sh"
