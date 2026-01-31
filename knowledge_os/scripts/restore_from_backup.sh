#!/bin/bash
# Восстановление базы данных из бэкапа

set -e

BACKUP_DIR="/root/knowledge_os/backups"
DB_NAME="knowledge_os"
DB_USER="admin"
DB_PASSWORD="secret"

echo "🔄 Восстановление базы данных из бэкапа..."

# Проверяем наличие директории бэкапов
if [ ! -d "$BACKUP_DIR" ]; then
    echo "❌ Директория бэкапов не найдена: $BACKUP_DIR"
    exit 1
fi

# Показываем доступные бэкапы
echo ""
echo "📦 Доступные бэкапы:"
ls -lh "$BACKUP_DIR"/*.sql.gz 2>/dev/null | tail -10 || echo "  (нет бэкапов)"

# Запрашиваем имя файла бэкапа
echo ""
read -p "Введите имя файла бэкапа (или полный путь): " BACKUP_FILE

# Проверяем, указан ли полный путь
if [ ! -f "$BACKUP_FILE" ]; then
    # Пробуем найти в директории бэкапов
    BACKUP_FILE="$BACKUP_DIR/$BACKUP_FILE"
fi

# Проверяем существование файла
if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ Файл бэкапа не найден: $BACKUP_FILE"
    exit 1
fi

# Подтверждение
echo ""
echo "⚠️  ВНИМАНИЕ: Это действие перезапишет текущую базу данных!"
echo "📦 Файл бэкапа: $BACKUP_FILE"
read -p "Продолжить? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "❌ Восстановление отменено"
    exit 0
fi

# Распаковываем бэкап если нужно
if [[ "$BACKUP_FILE" == *.gz ]]; then
    echo "📦 Распаковка бэкапа..."
    TEMP_FILE="${BACKUP_FILE%.gz}"
    gunzip -c "$BACKUP_FILE" > "$TEMP_FILE"
    BACKUP_FILE="$TEMP_FILE"
    CLEANUP_TEMP=true
else
    CLEANUP_TEMP=false
fi

# Останавливаем подключения к БД (опционально)
echo "🛑 Остановка подключений к БД..."
PGPASSWORD="$DB_PASSWORD" psql -U "$DB_USER" -h localhost -d postgres -c "
    SELECT pg_terminate_backend(pid)
    FROM pg_stat_activity
    WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();
" 2>/dev/null || true

# Восстанавливаем базу данных
echo "🔄 Восстановление базы данных..."
PGPASSWORD="$DB_PASSWORD" psql -U "$DB_USER" -h localhost -d postgres <<EOF
DROP DATABASE IF EXISTS $DB_NAME;
CREATE DATABASE $DB_NAME;
EOF

PGPASSWORD="$DB_PASSWORD" psql -U "$DB_USER" -h localhost -d "$DB_NAME" < "$BACKUP_FILE"

# Очищаем временный файл
if [ "$CLEANUP_TEMP" = true ]; then
    rm -f "$TEMP_FILE"
fi

echo ""
echo "✅ База данных успешно восстановлена из бэкапа!"
echo ""
echo "📝 Проверка:"
PGPASSWORD="$DB_PASSWORD" psql -U "$DB_USER" -h localhost -d "$DB_NAME" -c "
    SELECT 
        (SELECT count(*) FROM knowledge_nodes) as knowledge_nodes,
        (SELECT count(*) FROM experts) as experts,
        (SELECT count(*) FROM domains) as domains;
"

