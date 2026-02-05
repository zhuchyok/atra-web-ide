#!/usr/bin/env bash
# Запуск Ollama от пользователя bikos (модели в ~/.ollama/ у bikos).
# Сначала останавливаем все процессы Ollama от nik (serve + runner), затем запускаем от текущего.
#
# Важно: если на Mac залогинен пользователь nik — пусть он выйдет из приложения Ollama
# (иконка в меню-баре → Quit), иначе приложение может снова запустить serve.
#
# Использование: в Терминале (чтобы ввести пароль sudo):
#   ./scripts/start_ollama_as_bikos.sh

set -e
echo "Stopping brew ollama service..."
brew services stop ollama 2>/dev/null || true
sleep 1

echo "Stopping all Ollama processes of user nik (нужен пароль sudo)..."
sudo pkill -u nik -f ollama 2>/dev/null && echo "Stopped." || echo "Ни одного процесса nik/ollama не найдено."
echo "Waiting 3s for port 11434 to be released..."
sleep 3

if nc -z 127.0.0.1 11434 2>/dev/null; then
  echo "Ошибка: порт 11434 всё ещё занят."
  echo "Сделай: (1) У пользователя nik в меню-баре выйди из Ollama (Quit); (2) снова запусти этот скрипт."
  exit 1
fi

echo "Starting Ollama as $(whoami)..."
exec ollama serve
