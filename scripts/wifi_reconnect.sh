#!/bin/bash
# Автоматическое переподключение к Wi-Fi на macOS
# Используется системой самовосстановления

set -euo pipefail

LOG_FILE="${HOME}/Library/Logs/atra-wifi-reconnect.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log "=============================================="
log "📡 ПРОВЕРКА И ПЕРЕПОДКЛЮЧЕНИЕ К WI-FI"
log "=============================================="
log ""

# Функция проверки Wi-Fi подключения
check_wifi_connected() {
    # Проверяем, подключен ли Wi-Fi
    if /System/Library/PrivateFrameworks/Apple80211.framework/Resources/airport -I 2>/dev/null | grep -q "SSID:"; then
        SSID=$(/System/Library/PrivateFrameworks/Apple80211.framework/Resources/airport -I 2>/dev/null | grep " SSID:" | awk -F': ' '{print $2}')
        log "✅ Wi-Fi подключен к сети: $SSID"
        return 0
    else
        log "❌ Wi-Fi не подключен"
        return 1
    fi
}

# Функция проверки интернета через Wi-Fi
check_internet_via_wifi() {
    # Проверяем, есть ли интернет через Wi-Fi
    if ping -c 1 -W 3 8.8.8.8 >/dev/null 2>&1 || \
       ping -c 1 -W 3 1.1.1.1 >/dev/null 2>&1; then
        log "✅ Интернет доступен через Wi-Fi"
        return 0
    else
        log "❌ Интернет недоступен через Wi-Fi"
        return 1
    fi
}

# Функция переподключения к Wi-Fi
reconnect_wifi() {
    log "🔄 Попытка переподключения к Wi-Fi..."

    # Получаем список доступных Wi-Fi сетей
    WIFI_INTERFACE=$(networksetup -listallhardwareports | grep -A 1 "Wi-Fi" | grep "Device" | awk '{print $2}')

    if [ -z "$WIFI_INTERFACE" ]; then
        log "❌ Wi-Fi интерфейс не найден"
        return 1
    fi

    log "   Интерфейс Wi-Fi: $WIFI_INTERFACE"

    # Выключаем Wi-Fi
    log "   Выключаю Wi-Fi..."
    networksetup -setairportpower "$WIFI_INTERFACE" off
    sleep 2

    # Включаем Wi-Fi
    log "   Включаю Wi-Fi..."
    networksetup -setairportpower "$WIFI_INTERFACE" on
    sleep 5

    # Пробуем подключиться к последней использованной сети
    log "   Подключаюсь к последней использованной сети..."

    # Ждем подключения (до 30 секунд)
    MAX_WAIT=30
    WAITED=0
    while [ $WAITED -lt $MAX_WAIT ]; do
        if check_wifi_connected; then
            log "✅ Wi-Fi подключен"

            # Проверяем интернет
            sleep 3
            if check_internet_via_wifi; then
                log "✅ Интернет доступен после переподключения"
                return 0
            else
                log "⚠️ Wi-Fi подключен, но интернет недоступен"
                return 1
            fi
        fi
        sleep 2
        WAITED=$((WAITED + 2))
    done

    log "❌ Не удалось подключиться к Wi-Fi за $MAX_WAIT секунд"
    return 1
}

# Основная логика
log "[1/3] Проверка Wi-Fi подключения..."
if check_wifi_connected; then
    log "[2/3] Проверка интернета через Wi-Fi..."
    if check_internet_via_wifi; then
        log "✅ Wi-Fi подключен и интернет доступен"
        exit 0
    else
        log "⚠️ Wi-Fi подключен, но интернет недоступен"
        log "[3/3] Попытка переподключения..."
        if reconnect_wifi; then
            log "✅ Успешно переподключено к Wi-Fi с интернетом"
            exit 0
        else
            log "❌ Не удалось восстановить интернет через Wi-Fi"
            exit 1
        fi
    fi
else
    log "[2/3] Wi-Fi не подключен, пытаюсь подключиться..."
    if reconnect_wifi; then
        log "✅ Успешно подключено к Wi-Fi"
        exit 0
    else
        log "❌ Не удалось подключиться к Wi-Fi"
        exit 1
    fi
fi
