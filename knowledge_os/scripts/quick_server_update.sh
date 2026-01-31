#!/bin/bash

# Быстрое обновление сервера с исправлениями DCA
# Применяет все исправления расчета средней цены и TP уровней

echo "🚀 Начало обновления сервера с исправлениями DCA"
echo "=================================================="

# Создаем резервную копию
BACKUP_DIR="server_backup_$(date +%Y%m%d_%H%M%S)"
echo "📦 Создание резервной копии в $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"

# Копируем ключевые файлы
cp signal_live.py "$BACKUP_DIR/"
cp telegram_handlers.py "$BACKUP_DIR/"
cp telegram_utils.py "$BACKUP_DIR/"
cp main.py "$BACKUP_DIR/"

echo "✅ Резервная копия создана"

# Проверяем статус сервера
echo "🔍 Проверка статуса сервера"
if pgrep -f "python.*main.py" > /dev/null; then
    echo "✅ Сервер запущен"
    SERVER_RUNNING=true
else
    echo "⚠️ Сервер не запущен"
    SERVER_RUNNING=false
fi

# Останавливаем сервер если запущен
if [ "$SERVER_RUNNING" = true ]; then
    echo "🛑 Остановка сервера"
    pkill -f "python.*main.py"
    sleep 2
fi

# Применяем исправления к signal_live.py
echo "🔧 Применение исправлений к signal_live.py"

# Исправление 1: Убираем комиссию из средней цены
sed -i 's/# Учитываем комиссию при расчете средней цены/# Расчет средней цены БЕЗ комиссии (комиссия учитывается только в TP)/' signal_live.py
sed -i 's/commission_rate = 0.001  # 0.1% комиссия/# Комиссия учитывается только для новой позиции, не для всех/' signal_live.py
sed -i 's/new_position_cost = new_qty \* price/total_cost = sum(q * p for q, p in zip(qtys, entry_prices)) + new_qty * price/' signal_live.py
sed -i 's/new_position_commission = new_position_cost \* commission_rate/avg_price_new = total_cost \/ total_qty/' signal_live.py
sed -i 's/total_cost_with_commission = sum(q \* p for q, p in zip(qtys, entry_prices)) + new_position_cost + new_position_commission/# Убрано/' signal_live.py
sed -i 's/avg_price_new = total_cost_with_commission \/ total_qty/# Убрано/' signal_live.py

# Исправление 2: Уменьшаем комиссию в TP
sed -i 's/fee_round_frac = 0.001  # 0.1% общая комиссия (уменьшено)/fee_round_frac = 0.0005  # 0.05% общая комиссия (еще уменьшено)/' signal_live.py

echo "✅ signal_live.py обновлен"

# Применяем исправления к telegram_utils.py
echo "🔧 Применение исправлений к telegram_utils.py"

# Исправление: Правильный расчет средней цены
sed -i 's/return 0, 0/return 0, 0, 0/' telegram_utils.py

echo "✅ telegram_utils.py обновлен"

# Запускаем сервер
echo "🚀 Запуск сервера"
nohup python3 main.py > server.log 2>&1 &

# Ждем запуска
sleep 3

# Проверяем статус
if pgrep -f "python.*main.py" > /dev/null; then
    echo "✅ Сервер успешно запущен"
    echo "📊 Логи сервера: tail -f server.log"
else
    echo "❌ Ошибка запуска сервера"
    echo "📊 Проверьте логи: cat server.log"
fi

echo ""
echo "🎉 Обновление сервера завершено!"
echo "📦 Резервная копия: $BACKUP_DIR"
echo "📊 Статус сервера: $(pgrep -f 'python.*main.py' > /dev/null && echo 'Запущен' || echo 'Не запущен')"
