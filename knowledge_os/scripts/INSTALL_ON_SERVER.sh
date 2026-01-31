#!/bin/bash
# Скрипт установки ATRA на сервере

set -e

echo "🚀 УСТАНОВКА ATRA НА СЕРВЕРЕ"
echo "=============================="

# Проверяем, что мы root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Запустите скрипт от имени root: sudo $0"
    exit 1
fi

# Создаем директорию
echo "📁 Создаем директорию /root/atra..."
mkdir -p /root/atra

# Копируем файлы
echo "📋 Копируем файлы..."
cp -r . /root/atra/
cd /root/atra

# Устанавливаем права
echo "🔐 Устанавливаем права доступа..."
chown -R root:root /root/atra
chmod +x /root/atra/main.py
chmod +x /root/atra/server_compatibility_check.py

# Проверяем Python
echo "🐍 Проверяем Python..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не найден. Установите Python 3.8+"
    exit 1
fi

# Проверяем зависимости
echo "📦 Проверяем зависимости..."
python3 -c "
import sys
required_deps = ['pandas', 'numpy', 'requests', 'aiohttp', 'telegram', 'ccxt', 'yfinance']
missing = []
for dep in required_deps:
    try:
        __import__(dep)
    except ImportError:
        missing.append(dep)

if missing:
    print(f'❌ Отсутствуют зависимости: {missing}')
    print('Установите их: pip3 install ' + ' '.join(missing))
    sys.exit(1)
else:
    print('✅ Все зависимости установлены')
"

# Проверяем talib
echo "🔧 Проверяем talib..."
python3 -c "
try:
    from talib_wrapper import get_talib
    talib = get_talib()
    if talib:
        print('✅ talib работает')
    else:
        print('❌ talib недоступен')
        exit(1)
except Exception as e:
    print(f'❌ Ошибка talib: {e}')
    exit(1)
"

# Устанавливаем systemd service
echo "⚙️ Устанавливаем systemd service..."
cp atra.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable atra

# Создаем скрипт перезапуска
echo "🔄 Создаем скрипт перезапуска..."
cat > /usr/local/bin/restart_atra << 'EOF'
#!/bin/bash
echo "🔄 Перезапуск ATRA..."
systemctl stop atra
sleep 2
systemctl start atra
systemctl status atra
EOF
chmod +x /usr/local/bin/restart_atra

# Создаем скрипт проверки статуса
echo "📊 Создаем скрипт проверки статуса..."
cat > /usr/local/bin/status_atra << 'EOF'
#!/bin/bash
echo "📊 Статус ATRA:"
systemctl status atra --no-pager
echo ""
echo "📈 Процессы:"
ps aux | grep "python3 main.py" | grep -v grep
echo ""
echo "📝 Последние логи:"
journalctl -u atra --no-pager -n 20
EOF
chmod +x /usr/local/bin/status_atra

echo ""
echo "✅ УСТАНОВКА ЗАВЕРШЕНА!"
echo "======================"
echo ""
echo "📝 Команды для управления:"
echo "  Запуск:     systemctl start atra"
echo "  Остановка:  systemctl stop atra"
echo "  Перезапуск: restart_atra"
echo "  Статус:     status_atra"
echo "  Логи:       journalctl -u atra -f"
echo ""
echo "🚀 Запускаем ATRA..."
systemctl start atra
sleep 3
systemctl status atra --no-pager

echo ""
echo "🎉 ATRA успешно установлен и запущен на сервере!"