#!/bin/bash
# Скрипт для деплоя компенсации проскальзывания на сервер

echo "🔄 Обновление кода на сервере..."
cd /root/atra
git pull

echo "✅ Проверка синтаксиса..."
python3 -m py_compile src/execution/slippage_manager.py src/execution/order_manager.py signal_live.py

echo "✅ Проверка импортов..."
python3 -c "from src.execution.slippage_manager import get_slippage_manager; sm = get_slippage_manager(); print('✅ SlippageManager работает')"

echo "🔄 Перезапуск сервиса..."
systemctl restart signal_live

echo "⏳ Ожидание запуска (5 сек)..."
sleep 5

echo "📊 Статус сервиса:"
systemctl status signal_live --no-pager | head -15

echo "📋 Последние логи (фильтр по slippage):"
journalctl -u signal_live -n 50 --no-pager | grep -i -E "(slippage|SLIPPAGE|SlippageManager|✅|❌)" | tail -10

echo ""
echo "✅ Деплой завершен!"

