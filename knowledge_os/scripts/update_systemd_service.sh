#!/bin/bash

# Скрипт для обновления systemd сервиса на сервере
# Использование: ./update_systemd_service.sh

echo "🚀 Обновление systemd сервиса myproject.service..."

# Проверяем, что скрипт запущен от root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Скрипт должен быть запущен от root"
    exit 1
fi

# Останавливаем сервис
echo "🛑 Останавливаем сервис..."
systemctl stop myproject.service

# Создаем резервную копию текущего сервиса
if [ -f "/etc/systemd/system/myproject.service" ]; then
    echo "📋 Создаем резервную копию..."
    cp /etc/systemd/system/myproject.service /etc/systemd/system/myproject.service.backup.$(date +%Y%m%d_%H%M%S)
fi

# Копируем новый файл сервиса
echo "📝 Копируем новый файл сервиса..."
cp myproject.service /etc/systemd/system/

# Устанавливаем правильные права доступа
chmod 644 /etc/systemd/system/myproject.service

# Перезагружаем конфигурацию systemd
echo "🔄 Перезагружаем конфигурацию systemd..."
systemctl daemon-reload

# Включаем автозапуск сервиса
echo "⚙️ Включаем автозапуск сервиса..."
systemctl enable myproject.service

# Запускаем сервис
echo "▶️ Запускаем сервис..."
systemctl start myproject.service

# Проверяем статус
echo "📊 Проверяем статус сервиса..."
systemctl status myproject.service --no-pager

# Показываем логи
echo "📋 Последние логи сервиса:"
journalctl -u myproject.service --no-pager -n 20

echo "✅ Обновление systemd сервиса завершено!"
echo ""
echo "📋 Полезные команды для мониторинга:"
echo "  systemctl status myproject.service    - статус сервиса"
echo "  journalctl -u myproject.service -f    - следить за логами"
echo "  systemctl restart myproject.service   - перезапустить сервис"
echo "  systemctl stop myproject.service      - остановить сервис"
