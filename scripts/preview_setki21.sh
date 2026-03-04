#!/usr/bin/env bash
# Локальный просмотр Сетки 21 без dev-сервера (обход spawn EBADF на macOS).
# Собирает статику и поднимает preview-сервер. Открой URL из вывода (обычно http://localhost:3000).

set -e
SETKI21_ROOT="${SETKI21_ROOT:-$(cd "$(dirname "$0")/.." && pwd)/../dev/setki-21}"

if [ ! -d "$SETKI21_ROOT" ]; then
  echo "Ошибка: проект setki-21 не найден: $SETKI21_ROOT"
  exit 1
fi

cd "$SETKI21_ROOT"
export NUXT_PUBLIC_API_URL="${NUXT_PUBLIC_API_URL:-https://www.setki21.ru}"

echo "Сборка (generate)..."
npm run generate

echo ""
echo "Запуск preview-сервера. Открой URL из вывода ниже."
exec npm run preview
