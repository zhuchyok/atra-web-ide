#!/bin/bash
# Полная миграция всех Docker контейнеров с MacBook на Mac Studio
# Запускать на MacBook: bash scripts/full_migration_macbook_to_macstudio.sh

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MAC_STUDIO_IP="192.168.1.64"
MAC_STUDIO_USER="bikos"
MAC_STUDIO_PATH="~/Documents/atra-web-ide"

echo "=============================================="
echo "🚚 ПОЛНАЯ МИГРАЦИЯ DOCKER: MACBOOK → MAC STUDIO"
echo "=============================================="
echo ""
echo "📋 Этот скрипт перенесет:"
echo "   ✅ Все Docker volumes"
echo "   ✅ Все Docker образы"
echo "   ✅ Всю конфигурацию"
echo "   ✅ Все данные контейнеров"
echo ""
echo "⚠️  ВНИМАНИЕ:"
echo "   - Контейнеры на MacBook будут остановлены"
echo "   - После миграции Docker на MacBook можно выключить"
echo ""

read -p "Продолжить миграцию? (y/n): " confirm
if [ "$confirm" != "y" ]; then
    echo "Отменено"
    exit 0
fi

# Шаг 1: Экспорт
echo ""
echo "=============================================="
echo "ШАГ 1: ЭКСПОРТ С MACBOOK"
echo "=============================================="
bash scripts/migrate_docker_to_mac_studio.sh

if [ $? -ne 0 ]; then
    echo "❌ Ошибка экспорта!"
    exit 1
fi

# Шаг 2: Инструкция для Mac Studio
echo ""
echo "=============================================="
echo "✅ ЭКСПОРТ ЗАВЕРШЕН"
echo "=============================================="
echo ""
echo "📋 СЛЕДУЮЩИЙ ШАГ: На Mac Studio выполните:"
echo ""
echo "   cd ~/Documents/atra-web-ide"
echo "   bash scripts/import_docker_from_macbook.sh"
echo ""
echo "Или запустите полный скрипт:"
echo "   bash scripts/start_all_on_mac_studio.sh"
echo "   (он автоматически импортирует данные, если найдет бэкап)"
echo ""
echo "📁 Данные скопированы на Mac Studio в:"
echo "   ${MAC_STUDIO_PATH}/backups/migration/"
echo ""
