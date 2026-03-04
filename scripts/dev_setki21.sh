#!/usr/bin/env bash
# Запуск локального просмотра сайта Сетки 21 из корня atra-web-ide.
# Открой в браузере: http://localhost:3001

SETKI21_ROOT="${SETKI21_ROOT:-$(cd "$(dirname "$0")/.." && pwd)/../dev/setki-21}"
if [ ! -d "$SETKI21_ROOT" ]; then
  echo "Ошибка: проект setki-21 не найден: $SETKI21_ROOT"
  echo "Задай путь: SETKI21_ROOT=/path/to/setki-21 ./scripts/dev_setki21.sh"
  exit 1
fi
cd "$SETKI21_ROOT"
export NUXT_PUBLIC_API_URL="${NUXT_PUBLIC_API_URL:-https://www.setki21.ru}"
ulimit -n 65536 2>/dev/null || true
echo "Сетки 21: $SETKI21_ROOT"
echo "API: $NUXT_PUBLIC_API_URL"
echo "Открой: http://localhost:3001"
exec npm run dev
