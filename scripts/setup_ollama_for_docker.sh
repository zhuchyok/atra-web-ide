#!/bin/bash
# Скрипт для настройки Ollama для работы из Docker

echo "=== НАСТРОЙКА OLLAMA ДЛЯ РАБОТЫ ИЗ DOCKER ==="
echo ""

# Останавливаем Ollama если запущен
echo "1. Останавливаю Ollama..."
brew services stop ollama 2>/dev/null || killall ollama 2>/dev/null || echo "   Ollama не был запущен"

# Устанавливаем переменную окружения
echo ""
echo "2. Устанавливаю OLLAMA_HOST=0.0.0.0:11434..."
export OLLAMA_HOST=0.0.0.0:11434

# Добавляем в ~/.zshrc или ~/.bash_profile для постоянства
if [ -f ~/.zshrc ]; then
    if ! grep -q "OLLAMA_HOST=0.0.0.0:11434" ~/.zshrc; then
        echo "" >> ~/.zshrc
        echo "# Ollama для работы из Docker" >> ~/.zshrc
        echo "export OLLAMA_HOST=0.0.0.0:11434" >> ~/.zshrc
        echo "   ✅ Добавлено в ~/.zshrc"
    fi
fi

# Запускаем Ollama
echo ""
echo "3. Запускаю Ollama с OLLAMA_HOST=0.0.0.0:11434..."
OLLAMA_HOST=0.0.0.0:11434 brew services start ollama

sleep 3

# Проверяем статус
echo ""
echo "4. Проверяю статус..."
if lsof -i :11434 | grep -q "LISTEN"; then
    echo "   ✅ Ollama запущен и слушает на всех интерфейсах"
    lsof -i :11434 | grep LISTEN | head -2
else
    echo "   ❌ Ollama не запущен или не слушает на всех интерфейсах"
fi

echo ""
echo "✅ Настройка завершена!"
echo ""
echo "Проверка подключения из Docker:"
echo "   docker exec atra-web-ide-backend curl -s http://host.docker.internal:11434/api/tags"
