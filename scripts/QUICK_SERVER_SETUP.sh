#!/usr/bin/env bash
set -euo pipefail

# Быстрая настройка сервера Mac Studio
# Выполняет все необходимые проверки и настройки

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "🚀 Быстрая настройка сервера Mac Studio"
echo "========================================"
echo ""

# 1. Проверка Docker
echo "[1/4] Проверка Docker..."
if ! docker info >/dev/null 2>&1; then
  echo "❌ Docker daemon не запущен. Запустите Docker Desktop."
  exit 1
fi
echo "✅ Docker работает"
echo ""

# 2. Проверка сервисов
echo "[2/4] Проверка сервисов..."
if [[ -f "scripts/check_all_services_enhanced.sh" ]]; then
  bash scripts/check_all_services_enhanced.sh
else
  echo "⚠️  Скрипт проверки не найден, используем базовую проверку"
  docker-compose ps
fi
echo ""

# 3. Настройка алертов
echo "[3/4] Настройка алертов..."
if [[ -f "scripts/setup_alerts.sh" ]]; then
  bash scripts/setup_alerts.sh
else
  echo "⚠️  Скрипт настройки алертов не найден"
fi
echo ""

# 4. Проверка бэкапов
echo "[4/4] Проверка системы бэкапов..."
if [[ -f "scripts/check_backups_health.sh" ]]; then
  bash scripts/check_backups_health.sh || echo "⚠️  Есть проблемы с бэкапами"
else
  echo "⚠️  Скрипт проверки бэкапов не найден"
fi
echo ""

echo "========================================"
echo "✅ Настройка завершена!"
echo ""
echo "📋 Следующие шаги:"
echo "   1. Проверьте статус: bash scripts/check_all_services_enhanced.sh"
echo "   2. Просмотрите алерты: tail -f ~/Library/Logs/atra/alerts.log"
echo "   3. Миграция данных (когда будете готовы): python3 scripts/migration/migrate_to_mac_studio.py"
echo ""
