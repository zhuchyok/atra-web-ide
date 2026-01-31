#!/bin/bash
# Скрипт настройки автоматических бэкапов
# Singularity 7.5: Observability and Autonomous Operations

set -e

BACKUP_DIR="${BACKUP_DIR:-./backups}"
DB_URL="${DATABASE_URL:-postgresql://zhuchyok@localhost:5432/knowledge_os}"

echo "🔧 Настройка автоматических бэкапов..."

# Создаем директорию для бэкапов
mkdir -p "$BACKUP_DIR"
echo "✅ Директория бэкапов создана: $BACKUP_DIR"

# Проверяем наличие pg_dump
if ! command -v pg_dump &> /dev/null; then
    echo "⚠️ pg_dump не найден. Установите PostgreSQL client tools."
    echo "   Ubuntu/Debian: sudo apt-get install postgresql-client"
    echo "   macOS: brew install postgresql"
    exit 1
fi

echo "✅ pg_dump найден"

# Создаем тестовый бэкап для проверки
echo "🧪 Создание тестового бэкапа..."
python3 -c "
import asyncio
import os
from knowledge_os.app.auto_backup_manager import get_auto_backup_manager

async def test_backup():
    manager = get_auto_backup_manager(
        db_url=os.getenv('DATABASE_URL', '$DB_URL'),
        backup_dir='$BACKUP_DIR'
    )
    result = await manager.create_backup('test', force=True)
    if result:
        print(f'✅ Тестовый бэкап создан: {result}')
    else:
        print('❌ Ошибка создания тестового бэкапа')

asyncio.run(test_backup())
"

if [ $? -eq 0 ]; then
    echo "✅ Автоматические бэкапы настроены успешно!"
    echo ""
    echo "📋 Следующие шаги:"
    echo "   1. Бэкапы будут создаваться автоматически каждые 6 часов"
    echo "   2. Хранится до 30 последних бэкапов"
    echo "   3. Старые бэкапы автоматически удаляются"
    echo ""
    echo "💡 Для ручного создания бэкапа:"
    echo "   python3 -c \"import asyncio; from knowledge_os.app.auto_backup_manager import get_auto_backup_manager; asyncio.run(get_auto_backup_manager().create_backup('manual', force=True))\""
else
    echo "❌ Ошибка настройки автоматических бэкапов"
    exit 1
fi
