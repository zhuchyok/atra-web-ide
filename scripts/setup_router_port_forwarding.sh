#!/bin/bash
# Автоматическая настройка проброса порта через UPnP для Headscale

set -e

PORT=8080
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "192.168.1.43")

echo "=============================================="
echo "🔧 АВТОМАТИЧЕСКАЯ НАСТРОЙКА ПРОБРОСА ПОРТА"
echo "=============================================="
echo ""
echo "📋 Параметры:"
echo "   Порт: $PORT"
echo "   Локальный IP: $LOCAL_IP"
echo ""

# Проверка наличия UPnP инструментов
if command -v upnpc >/dev/null 2>&1; then
    echo "✅ Найден upnpc"
    USE_UPNPC=true
elif python3 -c "import miniupnpc" 2>/dev/null; then
    echo "✅ Найден Python miniupnpc"
    USE_PYTHON_UPNPC=true
else
    echo "⚠️  UPnP инструменты не найдены"
    echo "📥 Установка miniupnpc..."
    if command -v brew >/dev/null 2>&1; then
        brew install miniupnpc
        USE_UPNPC=true
    else
        echo "❌ Homebrew не найден. Установите: brew install miniupnpc"
        exit 1
    fi
fi

echo ""
echo "🔍 Поиск UPnP роутера в сети..."

if [ "$USE_UPNPC" = true ]; then
    EXTERNAL_IP=$(upnpc -s 2>/dev/null | grep "ExternalIPAddress" | awk '{print $3}' || echo "")
    
    if [ -z "$EXTERNAL_IP" ]; then
        echo "❌ Не удалось найти UPnP роутер"
        echo ""
        echo "💡 Возможные причины:"
        echo "   1. Роутер не поддерживает UPnP"
        echo "   2. UPnP отключен в настройках роутера"
        echo "   3. Роутер не в той же сети"
        echo ""
        echo "📝 Альтернатива: Настройте проброс порта вручную в роутере"
        echo "   1. Откройте веб-интерфейс роутера (обычно 192.168.1.1)"
        echo "   2. Найдите раздел 'Port Forwarding' или 'Виртуальные серверы'"
        echo "   3. Добавьте правило:"
        echo "      - Внешний порт: $PORT"
        echo "      - Внутренний IP: $LOCAL_IP"
        echo "      - Внутренний порт: $PORT"
        echo "      - Протокол: TCP"
        exit 1
    fi
    
    echo "✅ Роутер найден! Внешний IP: $EXTERNAL_IP"
    echo ""
    echo "🔧 Настройка проброса порта..."
    
    # Удаляем старое правило (если есть)
    upnpc -d $PORT TCP 2>/dev/null || true
    sleep 1
    
    # Добавляем новое правило
    if upnpc -a $LOCAL_IP $PORT $PORT TCP 2>/dev/null; then
        echo "✅ Проброс порта настроен успешно!"
        echo ""
        echo "📊 Информация:"
        echo "   Внешний IP: $EXTERNAL_IP"
        echo "   Порт: $PORT"
        echo "   Внутренний IP: $LOCAL_IP"
        echo ""
        echo "🌐 Теперь можно подключаться из интернета:"
        echo "   tailscale up --login-server=http://$EXTERNAL_IP:$PORT"
        echo ""
        echo "⚠️  ВАЖНО: Проброс порта через UPnP может сброситься при перезагрузке роутера"
        echo "   Рекомендуется настроить проброс порта вручную в настройках роутера"
    else
        echo "❌ Не удалось настроить проброс порта"
        echo ""
        echo "💡 Попробуйте настроить вручную в веб-интерфейсе роутера"
    fi

elif [ "$USE_PYTHON_UPNPC" = true ]; then
    echo "📡 Использование Python miniupnpc..."
    
    python3 << PYTHON_EOF
import miniupnpc
import sys

try:
    u = miniupnpc.UPnPC()
    u.discoverdelay = 200
    devices = u.discover()
    
    if devices == 0:
        print("❌ UPnP устройства не найдены")
        sys.exit(1)
    
    u.selectigd()
    external_ip = u.externalipaddress()
    
    print(f"✅ Роутер найден! Внешний IP: {external_ip}")
    
    # Удаляем старое правило
    try:
        u.deleteportmapping($PORT, 'TCP')
    except:
        pass
    
    # Добавляем новое правило
    result = u.addportmapping($PORT, 'TCP', '$LOCAL_IP', $PORT, 'Headscale', '')
    
    if result:
        print("✅ Проброс порта настроен успешно!")
        print(f"")
        print(f"📊 Информация:")
        print(f"   Внешний IP: {external_ip}")
        print(f"   Порт: $PORT")
        print(f"   Внутренний IP: $LOCAL_IP")
        print(f"")
        print(f"🌐 Теперь можно подключаться из интернета:")
        print(f"   tailscale up --login-server=http://{external_ip}:$PORT")
    else:
        print("❌ Не удалось настроить проброс порта")
        sys.exit(1)
        
except Exception as e:
    print(f"❌ Ошибка: {e}")
    sys.exit(1)
PYTHON_EOF

else
    echo "❌ UPnP инструменты не установлены"
    exit 1
fi

echo ""
echo "=============================================="
echo "✅ НАСТРОЙКА ЗАВЕРШЕНА"
echo "=============================================="
