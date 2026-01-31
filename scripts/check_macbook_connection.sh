#!/bin/bash
# Проверка подключения к MacBook и поиск базы данных

set -e

echo "🔍 Поиск MacBook и проверка подключения..."
echo ""

# Возможные IP адреса MacBook
MACBOOK_IPS=(
    "192.168.1.43"  # Mac Studio (из документации)
    "192.168.1.100"
    "192.168.1.101"
    "192.168.0.43"
    "localhost"
)

# Проверяем каждый IP
for ip in "${MACBOOK_IPS[@]}"; do
    echo "🔍 Проверка $ip..."
    
    # Ping
    if ping -c 1 -W 1 "$ip" > /dev/null 2>&1; then
        echo "  ✅ Ping OK"
        
        # Проверяем PostgreSQL
        if psql -h "$ip" -U admin -d knowledge_os -c "SELECT 1;" > /dev/null 2>&1; then
            echo "  ✅ PostgreSQL доступен!"
            COUNT=$(psql -h "$ip" -U admin -d knowledge_os -t -c "SELECT COUNT(*) FROM knowledge_nodes;" 2>/dev/null | tr -d ' ')
            echo "  📊 Узлов знаний: $COUNT"
            echo ""
            echo "✅ MacBook найден: $ip"
            echo "   Узлов знаний: $COUNT"
            exit 0
        else
            echo "  ⚠️  PostgreSQL недоступен"
        fi
    else
        echo "  ❌ Недоступен"
    fi
done

echo ""
echo "❌ MacBook не найден или PostgreSQL недоступен"
echo ""
echo "Проверьте:"
echo "  1. MacBook включен и в той же сети"
echo "  2. PostgreSQL запущен на MacBook"
echo "  3. Порт 5432 открыт"
echo "  4. Пароль: secret, пользователь: admin"
