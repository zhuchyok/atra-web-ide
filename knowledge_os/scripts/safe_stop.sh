#!/bin/bash
# safe_stop.sh - Безопасная остановка бота с сохранением БД

echo "🛑 Останавливаем бота безопасно..."

# Получаем PID процесса main.py
PID=$(ps aux | grep 'python3 main.py' | grep -v grep | awk '{print $2}')

if [ -z "$PID" ]; then
    echo "✅ Бот не запущен"
    exit 0
fi

echo "📍 Найден процесс: PID=$PID"

# Отправляем SIGTERM для graceful shutdown
echo "📤 Отправляем SIGTERM (graceful shutdown)..."
kill -15 $PID

# Ждем до 15 секунд, пока процесс завершится
echo "⏳ Ждем завершения (максимум 15 секунд)..."
for i in {1..15}; do
    if ! ps -p $PID > /dev/null 2>&1; then
        echo "✅ Процесс завершился корректно за ${i} секунд"
        break
    fi
    sleep 1
    echo -n "."
done
echo ""

# Проверяем, завершился ли процесс
if ps -p $PID > /dev/null 2>&1; then
    echo "⚠️ Процесс не завершился за 15 секунд, используем SIGKILL..."
    kill -9 $PID
    sleep 1

    if ps -p $PID > /dev/null 2>&1; then
        echo "❌ Не удалось остановить процесс!"
        exit 1
    else
        echo "✅ Процесс принудительно остановлен"
    fi
fi

# Делаем WAL checkpoint для синхронизации БД
echo "🔄 Синхронизация WAL с БД..."
cd /root/atra
python3 << 'PYEOF'
try:
    from db_health_monitor import checkpoint_wal
    if checkpoint_wal():
        print("✅ WAL checkpoint успешно выполнен")
    else:
        print("⚠️ WAL checkpoint не удался")
except Exception as e:
    print(f"⚠️ Ошибка WAL checkpoint: {e}")
PYEOF

# Проверяем целостность БД
echo "🔍 Проверка целостности БД..."
python3 << 'PYEOF'
try:
    from db_health_monitor import check_db_integrity
    is_ok, msg = check_db_integrity()
    print(msg)
    if not is_ok:
        print("⚠️ БД повреждена! Запустите 'python3 -c \"from db_health_monitor import auto_fix_database; auto_fix_database()\"'")
except Exception as e:
    print(f"⚠️ Ошибка проверки БД: {e}")
PYEOF

# Удаляем lock файлы
echo "🗑️ Удаляем lock файлы..."
rm -f /root/atra/atra.lock
rm -f /tmp/atra_tg_poll_*.lock

echo "✅ Бот безопасно остановлен!"
echo ""
echo "📊 Для запуска используйте: nohup python3 main.py > main.log 2>&1 &"
