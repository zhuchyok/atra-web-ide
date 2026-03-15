#!/bin/bash
# Скрипт проверки SSL-сертификатов для всех доменов Setki21

set -e

DOMAINS=(
    "www.setki21.ru"
    "setki21.ru"
    "сеткимоскитки.рф"
    "xn--e1agaahbbnszfhh.xn--p1ai"
    "www.xn--e1agaahbbnszfhh.xn--p1ai"
    "setkimoskitki.ru"
    "www.setkimoskitki.ru"
)

echo "=========================================="
echo "Проверка SSL-сертификатов Setki21"
echo "=========================================="
echo ""

check_ssl() {
    local domain=$1
    echo "Проверка: $domain"

    # Проверка HTTPS
    if curl -sI --max-time 5 "https://$domain/" > /dev/null 2>&1; then
        # Получаем информацию о сертификате
        cert_info=$(echo | openssl s_client -servername "$domain" -connect "$domain:443" 2>/dev/null | openssl x509 -noout -dates 2>/dev/null)

        if [ -n "$cert_info" ]; then
            expiry=$(echo "$cert_info" | grep "notAfter" | cut -d= -f2)
            echo "  ✅ HTTPS работает"
            echo "  📅 Сертификат истекает: $expiry"
        else
            echo "  ⚠️  HTTPS подключается, но не удалось получить информацию о сертификате"
        fi
    else
        echo "  ❌ HTTPS не работает (timeout или ошибка SSL)"

        # Проверяем HTTP
        if curl -sI --max-time 5 "http://$domain/" > /dev/null 2>&1; then
            echo "  ℹ️  HTTP работает (требуется настройка SSL в NPM)"
        else
            echo "  ❌ HTTP тоже не работает (проверить DNS и NPM)"
        fi
    fi

    # Проверка DNS
    echo -n "  🌐 DNS: "
    dns_result=$(dig +short "$domain" A | head -1)
    if [ -n "$dns_result" ]; then
        echo "$dns_result"
        if [ "$dns_result" != "45.10.43.248" ]; then
            echo "  ⚠️  Внимание: DNS указывает не на наш VDS!"
        fi
    else
        echo "не резолвится"
    fi

    echo ""
}

for domain in "${DOMAINS[@]}"; do
    check_ssl "$domain"
done

echo "=========================================="
echo "Проверка завершена"
echo "=========================================="
echo ""
echo "Легенда:"
echo "  ✅ - Всё работает"
echo "  ⚠️  - Требует внимания"
echo "  ❌ - Не работает"
echo "  ℹ️  - Информация"
echo ""
echo "Если домен показывает '❌ HTTPS не работает', но 'ℹ️ HTTP работает':"
echo "  → Открыть http://45.10.43.248:81 и настроить SSL вручную"
echo "  → Или см. docs/runbooks/SETKI21_SSL_MANUAL_FIX.md"
echo ""
echo "Для автоматической настройки SSL при активации новых доменов:"
echo "  → Деплой исправленного кода: docs/SETKI21_AUTO_SSL_FIX.md"
