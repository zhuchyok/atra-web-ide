#!/bin/bash
# Продолжение миграции, если она была прервана
# Запускать на MacBook: bash scripts/continue_migration.sh

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MAC_STUDIO_IP="192.168.1.64"
MAC_STUDIO_USER="bikos"
MAC_STUDIO_PATH="~/Documents/atra-web-ide"

echo "=============================================="
echo "🔄 ПРОДОЛЖЕНИЕ МИГРАЦИИ"
echo "=============================================="
echo ""

# Поиск последнего бэкапа
BACKUP_DIR=$(find /tmp -name "atra-docker-migration-*" -type d -maxdepth 1 2>/dev/null | sort -r | head -1)

if [ -z "$BACKUP_DIR" ] || [ ! -d "$BACKUP_DIR" ]; then
    echo "❌ Бэкап не найден в /tmp/"
    echo "   Запустите полную миграцию:"
    echo "   bash scripts/full_migration_macbook_to_macstudio.sh"
    exit 1
fi

echo "📁 Найден бэкап: $BACKUP_DIR"
SIZE=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)
echo "   Размер: $SIZE"
echo ""

# Проверка, скопирован ли уже на Mac Studio
echo "🔍 Проверка на Mac Studio..."
REMOTE_BACKUP=$(ssh ${MAC_STUDIO_USER}@${MAC_STUDIO_IP} "ls -td ${MAC_STUDIO_PATH}/backups/migration/atra-docker-migration-* 2>/dev/null | head -1" 2>/dev/null || echo "")

if [ -n "$REMOTE_BACKUP" ]; then
    echo "   ✅ Бэкап уже скопирован на Mac Studio: $REMOTE_BACKUP"
    echo ""
    echo "✅ МИГРАЦИЯ ЗАВЕРШЕНА!"
    echo ""
    echo "📋 СЛЕДУЮЩИЙ ШАГ: На Mac Studio выполните:"
    echo "   cd ~/Documents/atra-web-ide"
    echo "   bash scripts/import_docker_from_macbook.sh"
    exit 0
fi

echo "   ⚠️  Бэкап еще не скопирован на Mac Studio"
echo ""
read -p "Скопировать бэкап на Mac Studio? (y/n): " confirm
if [ "$confirm" != "y" ]; then
    echo "Отменено"
    exit 0
fi

# Копирование на Mac Studio
echo ""
echo "📤 Копирование на Mac Studio..."
echo "   Это может занять некоторое время..."
ssh ${MAC_STUDIO_USER}@${MAC_STUDIO_IP} "mkdir -p ${MAC_STUDIO_PATH}/backups/migration" 2>/dev/null || true

scp -r "$BACKUP_DIR" ${MAC_STUDIO_USER}@${MAC_STUDIO_IP}:${MAC_STUDIO_PATH}/backups/migration/ 2>&1 | while read line; do
    echo "   $line"
done

if [ $? -eq 0 ]; then
    echo "   ✅ Файлы скопированы"
    echo ""
    echo "=============================================="
    echo "✅ ЭКСПОРТ И КОПИРОВАНИЕ ЗАВЕРШЕНЫ"
    echo "=============================================="
    echo ""
    echo "📋 СЛЕДУЮЩИЙ ШАГ: На Mac Studio выполните:"
    echo "   cd ~/Documents/atra-web-ide"
    echo "   bash scripts/import_docker_from_macbook.sh"
    echo ""
    echo "   ИЛИ (автоматически):"
    echo "   bash scripts/start_all_on_mac_studio.sh"
    echo ""
else
    echo "   ❌ Ошибка копирования"
    echo "   💡 Попробуйте вручную:"
    echo "      scp -r $BACKUP_DIR ${MAC_STUDIO_USER}@${MAC_STUDIO_IP}:${MAC_STUDIO_PATH}/backups/migration/"
    exit 1
fi
