#!/bin/bash

# Скрипт настройки автоматической инициализации Cursor правил
# Этот скрипт настраивает автоматический запуск init-cursor-rules.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INIT_SCRIPT="$SCRIPT_DIR/init-cursor-rules.sh"
SHELL_RC=""

# Определяем shell и путь к .rc файлу
if [ -n "$ZSH_VERSION" ]; then
    SHELL_RC="$HOME/.zshrc"
    SHELL_NAME="zsh"
elif [ -n "$BASH_VERSION" ]; then
    SHELL_RC="$HOME/.bashrc"
    SHELL_NAME="bash"
else
    echo "❌ Неподдерживаемый shell. Используйте bash или zsh."
    exit 1
fi

echo "🔧 Настройка автоматической инициализации Cursor правил для $SHELL_NAME..."

# Проверяем, существует ли уже функция
if grep -q "init-cursor-rules" "$SHELL_RC" 2>/dev/null; then
    echo "⚠️  Функция уже настроена в $SHELL_RC"
    read -p "Перезаписать? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 0
    fi
    # Удаляем старую функцию
    sed -i.bak '/# Cursor rules auto-init/,/^}$/d' "$SHELL_RC"
fi

# Добавляем функцию в .rc файл
cat >> "$SHELL_RC" << EOF

# Cursor rules auto-init
# Автоматическая инициализация .cursorrules при открытии проекта
init_cursor_rules_auto() {
    local project_path="\$(pwd)"
    
    # Проверяем, нужно ли создавать .cursorrules
    if [ ! -f "\$project_path/.cursorrules" ]; then
        # Нет .cursorrules - создаем
        if [ -f "$INIT_SCRIPT" ]; then
            "$INIT_SCRIPT" "\$project_path" 2>/dev/null || true
        fi
    else
        # Есть .cursorrules - проверяем, содержит ли универсальные правила
        if ! grep -q "КОМАНДА ЭКСПЕРТОВ\|Команда экспертов\|команда экспертов" "\$project_path/.cursorrules" 2>/dev/null; then
            # Нет универсальных правил - добавляем (неинтерактивно)
            if [ -f "$INIT_SCRIPT" ]; then
                "$INIT_SCRIPT" "\$project_path" < /dev/null 2>/dev/null || true
            fi
        fi
    fi
}

# Автоматический запуск при смене директории (для zsh)
if [ -n "\$ZSH_VERSION" ]; then
    autoload -U add-zsh-hook
    add-zsh-hook chpwd init_cursor_rules_auto
fi

# Для bash можно использовать PROMPT_COMMAND
if [ -n "\$BASH_VERSION" ]; then
    # Запускаем при открытии нового терминала
    init_cursor_rules_auto
fi
EOF

echo "✅ Автоматическая инициализация настроена!"
echo ""
echo "📋 Что было сделано:"
echo "   - Добавлена функция init_cursor_rules_auto() в $SHELL_RC"
echo "   - Для zsh: автоматический запуск при смене директории"
echo "   - Для bash: запуск при открытии терминала"
echo ""
echo "🔄 Перезагрузите shell или выполните:"
echo "   source $SHELL_RC"
echo ""
echo "💡 Или запускайте вручную:"
echo "   $INIT_SCRIPT"

