#!/bin/bash
# Запуск дашборда корпорации ATRA через victoria-agent

set -e

echo "🚀 Запуск дашборда корпорации ATRA..."
echo ""

# Проверяем Docker
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Docker не запущен!"
    exit 1
fi

# Проверяем контейнер
if ! docker ps | grep -q victoria-agent; then
    echo "❌ Контейнер victoria-agent не запущен!"
    echo "   Запустите: docker-compose -f knowledge_os/docker-compose.yml up -d"
    exit 1
fi

# Проверяем порт
if lsof -i :8501 > /dev/null 2>&1; then
    echo "✅ Дашборд уже запущен на порту 8501"
    echo "   Откройте: http://localhost:8501"
    exit 0
fi

# Устанавливаем зависимости
echo "📦 Проверка зависимостей..."
docker exec victoria-agent pip install -q streamlit pandas plotly psycopg2-binary networkx asyncpg 2>&1 | tail -1

# Запускаем дашборд
echo "🌐 Запуск Streamlit дашборда..."
docker exec -d victoria-agent bash -c "cd /app/knowledge_os/dashboard && python3 -m streamlit run app.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true --browser.gatherUsageStats=false > /tmp/dashboard.log 2>&1 &"

sleep 5

# Проверяем
if curl -s http://localhost:8501/_stcore/health > /dev/null 2>&1; then
    echo "✅ Дашборд запущен!"
    echo ""
    echo "🌐 Доступ:"
    echo "   Локально: http://localhost:8501"
    echo "   Удаленно: http://$(hostname -I | awk '{print $1}'):8501"
    echo ""
    echo "📊 Что показывает дашборд:"
    echo "   ✅ Задачи корпорации"
    echo "   ✅ Структура экспертов"
    echo "   ✅ Обучение и аналитика"
    echo "   ✅ И 20+ других разделов"
else
    echo "⚠️ Дашборд запускается, подождите несколько секунд..."
    echo "   Проверьте логи: docker exec victoria-agent tail -f /tmp/dashboard.log"
    echo "   Или откройте: http://localhost:8501"
fi
