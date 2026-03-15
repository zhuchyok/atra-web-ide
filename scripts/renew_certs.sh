#!/bin/bash
# [SINGULARITY 21.24] Автоматическое обновление корпоративных mTLS сертификатов
# Запускается cron'ом за 30 дней до истечения.
# Лог: /var/log/atra-certs-renew.log

set -euo pipefail

CERTS_DIR="$(cd "$(dirname "$0")/../certs" && pwd)"
LOG_FILE="/tmp/atra-certs-renew.log"
DAYS_VALID=365
DAYS_WARN=30  # предупреждать и обновлять за 30 дней до истечения

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

check_cert_expiry() {
    local cert="$1"
    local days_left
    days_left=$(( ( $(date -j -f "%b %e %H:%M:%S %Y %Z" \
        "$(openssl x509 -noout -enddate -in "$cert" | cut -d= -f2)" +%s 2>/dev/null \
        || openssl x509 -noout -enddate -in "$cert" | cut -d= -f2 | xargs -I{} date -d "{}" +%s 2>/dev/null) \
        - $(date +%s) ) / 86400 ))
    echo "$days_left"
}

renew_cert() {
    local name="$1"
    local cnf="$2"
    log "🔄 Обновляю сертификат: $name"
    openssl genrsa -out "$CERTS_DIR/$name.key" 2048
    openssl req -new -key "$CERTS_DIR/$name.key" -out "$CERTS_DIR/$name.csr" -config "$cnf"
    openssl x509 -req -in "$CERTS_DIR/$name.csr" \
        -CA "$CERTS_DIR/ca.crt" -CAkey "$CERTS_DIR/ca.key" \
        -CAcreateserial -out "$CERTS_DIR/$name.crt" \
        -days "$DAYS_VALID" -sha256 -extfile "$cnf" -extensions v3_req
    openssl verify -CAfile "$CERTS_DIR/ca.crt" "$CERTS_DIR/$name.crt"
    log "✅ $name.crt обновлён (срок: $DAYS_VALID дней)"
}

log "=== Проверка сертификатов Singularity 21.24 ==="

RENEWED=0

for name in mac-studio vds; do
    cert="$CERTS_DIR/$name.crt"
    cnf="$CERTS_DIR/$name.cnf"

    if [ ! -f "$cert" ]; then
        log "⚠️  $cert не найден, пропускаю"
        continue
    fi

    days_left=$(check_cert_expiry "$cert")
    log "📋 $name.crt: осталось $days_left дней"

    if [ "$days_left" -le "$DAYS_WARN" ]; then
        log "⏰ Срок истекает через $days_left дней — обновляю"
        renew_cert "$name" "$cnf"
        RENEWED=$((RENEWED + 1))
    fi
done

if [ "$RENEWED" -gt 0 ]; then
    log "🔁 Обновлено $RENEWED сертификатов — перезапускаю Gateway"
    cd "$(dirname "$0")/.."
    docker-compose restart gateway 2>&1 | tee -a "$LOG_FILE"
    log "✅ Gateway перезапущен с новыми сертификатами"
else
    log "✅ Все сертификаты актуальны, ничего не обновлялось"
fi

log "=== Готово ==="
