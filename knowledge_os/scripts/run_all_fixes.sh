#!/bin/bash
# Автоматический скрипт для исправления всех позиций
# Запускать на боевом сервере

set -e

echo "🚀 НАЧАЛО ИСПРАВЛЕНИЯ ПОЗИЦИЙ"
echo "================================"
echo ""

# Переходим в директорию проекта
cd "$(dirname "$0")/.." || exit 1

echo "📋 ШАГ 1: Синхронизация позиций с биржи"
echo "----------------------------------------"
python3 scripts/sync_positions_with_exchange.py
echo ""

echo "📋 ШАГ 2: Экстренное исправление PUMPUSDT"
echo "----------------------------------------"
python3 scripts/emergency_fix_pumpusdt.py
echo ""

echo "📋 ШАГ 3: Общее исправление всех позиций"
echo "----------------------------------------"
python3 scripts/fix_open_positions_tp_sl.py
echo ""

echo "✅ ВСЕ ИСПРАВЛЕНИЯ ЗАВЕРШЕНЫ"
echo "================================"
echo ""
echo "📊 Проверьте результаты:"
echo "   - Позиции на бирже должны иметь TP1/TP2/SL"
echo "   - Логи в order_audit_log"
echo "   - Позиции в active_positions"
