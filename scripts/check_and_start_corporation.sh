#!/bin/bash
# Умный скрипт: проверяет Docker и запускает корпорацию если нужно
# Можно запускать каждый раз - безопасно (идемпотентно)

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=============================================="
echo "🔍 Проверка и запуск корпорации ATRA"
echo "=============================================="
echo ""

# 1. Проверка Docker
if ! docker info >/dev/null 2>&1; then
    echo "⚠️ Docker не запущен"
    echo ""
    echo "Запускаю Docker Desktop..."
    open -a Docker

    echo "⏳ Ожидание запуска Docker (до 60 секунд)..."
    MAX_WAIT=60
    WAITED=0
    while ! docker info >/dev/null 2>&1; do
        if [ $WAITED -ge $MAX_WAIT ]; then
            echo "❌ Docker не запустился за $MAX_WAIT секунд"
            echo "   Запустите Docker Desktop вручную и повторите"
            exit 1
        fi
        sleep 2
        WAITED=$((WAITED + 2))
        echo -n "."
    done
    echo ""
    echo "✅ Docker запущен"
    sleep 3
else
    echo "✅ Docker уже запущен"
fi

# 2. Проверка контейнеров
echo ""
echo "Проверка контейнеров..."

DB_RUNNING=$(docker ps --format "{{.Names}}" | grep -E "(knowledge.*db|atra.*db)" | head -1 || echo "")
VIC_RUNNING=$(docker ps --format "{{.Names}}" | grep -E "victoria" | head -1 || echo "")
VER_RUNNING=$(docker ps --format "{{.Names}}" | grep -E "veronica" | head -1 || echo "")

if [ -z "$DB_RUNNING" ] || [ -z "$VIC_RUNNING" ] || [ -z "$VER_RUNNING" ]; then
    echo "⚠️ Некоторые контейнеры не запущены"
    echo "   Запускаю корпорацию..."
    echo ""
    bash scripts/start_full_corporation.sh
else
    echo "✅ Все контейнеры запущены:"
    echo "   - $DB_RUNNING"
    echo "   - $VIC_RUNNING"
    echo "   - $VER_RUNNING"
fi

# 3. Проверка автономных систем
echo ""
echo "Проверка автономных систем..."

if ! pgrep -f "start_orchestrator.sh" > /dev/null; then
    echo "⚠️ Orchestrator не запущен"
    echo "   Запускаю..."
    bash scripts/start_autonomous_systems.sh
else
    echo "✅ Orchestrator запущен"
fi

if ! pgrep -f "start_nightly_learner.sh" > /dev/null; then
    echo "⚠️ Nightly Learner не запущен"
    echo "   Запускаю..."
    bash scripts/start_autonomous_systems.sh
else
    echo "✅ Nightly Learner запущен"
fi

# 4. Финальная проверка
echo ""
echo "=============================================="
echo "📊 ФИНАЛЬНЫЙ СТАТУС"
echo "=============================================="

# Проверка агентов
if curl -sf http://localhost:8010/health >/dev/null 2>&1; then
    echo "✅ Victoria Agent: работает"
else
    echo "❌ Victoria Agent: не работает"
fi

if curl -sf http://localhost:8011/health >/dev/null 2>&1; then
    echo "✅ Veronica Agent: работает"
else
    echo "❌ Veronica Agent: не работает"
fi

# Проверка БД
if docker ps | grep -qE "(knowledge.*db|atra.*db)"; then
    echo "✅ Knowledge OS DB: работает"
else
    echo "❌ Knowledge OS DB: не работает"
fi

echo ""
echo "✅ Готово! Корпорация работает."
echo ""
