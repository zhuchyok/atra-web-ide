#!/bin/bash

# Скрипт автоматической инициализации .cursorrules для нового проекта
# Использование: ./init-cursor-rules.sh [project-path]
# Или добавьте в .bashrc/.zshrc для автоматического запуска

set -e

PROJECT_PATH="${1:-$(pwd)}"
UNIVERSAL_RULES_PATH="$HOME/.cursor/universal-rules.md"
TEMPLATE_PATH="$HOME/.cursor/templates/project-template-rules.md"
CURSOR_RULES_FILE="$PROJECT_PATH/.cursorrules"

# Цвета
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}🔍 Проверка инициализации Cursor правил...${NC}"

# Проверяем, существует ли уже .cursorrules
if [ -f "$CURSOR_RULES_FILE" ]; then
    echo -e "${YELLOW}ℹ️  Файл .cursorrules уже существует${NC}"
    echo -e "${YELLOW}   Путь: $CURSOR_RULES_FILE${NC}"

    # Проверяем, содержит ли файл универсальные правила
    if grep -q "КОМАНДА ЭКСПЕРТОВ\|Команда экспертов\|команда экспертов" "$CURSOR_RULES_FILE" 2>/dev/null; then
        echo -e "${GREEN}✅ Универсальные правила уже применены${NC}"

        # Если запущен в автоматическом режиме (неинтерактивно), просто выходим
        if [ -t 0 ] && [ -t 1 ]; then
            # Интерактивный режим - спрашиваем
            read -p "Обновить правила? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                exit 0
            fi
        else
            # Неинтерактивный режим - не обновляем существующий файл
            exit 0
        fi
    else
        echo -e "${YELLOW}⚠️  Файл существует, но не содержит универсальных правил${NC}"

        # В автоматическом режиме добавляем правила без вопроса
        if [ ! -t 0 ] || [ ! -t 1 ]; then
            echo -e "${BLUE}📝 Автоматически добавляем универсальные правила...${NC}"
        else
            read -p "Добавить универсальные правила? (Y/n): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Nn]$ ]]; then
                exit 0
            fi
        fi

        # Создаем резервную копию существующего файла
        BACKUP_FILE="${CURSOR_RULES_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
        cp "$CURSOR_RULES_FILE" "$BACKUP_FILE"
        echo -e "${BLUE}💾 Создана резервная копия: $BACKUP_FILE${NC}"
    fi
fi

# Создаем директории если не существуют
mkdir -p "$HOME/.cursor/templates"

# Проверяем наличие универсальных правил
if [ ! -f "$UNIVERSAL_RULES_PATH" ]; then
    echo -e "${YELLOW}⚠️  Универсальные правила не найдены в $UNIVERSAL_RULES_PATH${NC}"
    echo -e "${BLUE}📥 Копирование универсальных правил...${NC}"

    # Ищем в проекте ATRA
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    ATRA_EXAMPLES="$SCRIPT_DIR/../docs/examples/universal-cursor-rules.md"

    if [ -f "$ATRA_EXAMPLES" ]; then
        cp "$ATRA_EXAMPLES" "$UNIVERSAL_RULES_PATH"
        echo -e "${GREEN}✅ Универсальные правила скопированы${NC}"
    else
        echo -e "${RED}❌ Не найдены универсальные правила${NC}"
        echo -e "${YELLOW}   Создайте файл: $UNIVERSAL_RULES_PATH${NC}"
        exit 1
    fi
fi

# Определяем тип проекта
detect_project_type() {
    local path="$1"
    if [ -f "$path/package.json" ]; then
        echo "javascript/typescript"
    elif [ -f "$path/requirements.txt" ] || [ -f "$path/pyproject.toml" ]; then
        echo "python"
    elif [ -f "$path/Cargo.toml" ]; then
        echo "rust"
    elif [ -f "$path/go.mod" ]; then
        echo "go"
    elif [ -f "$path/pom.xml" ] || [ -f "$path/build.gradle" ]; then
        echo "java"
    else
        echo "generic"
    fi
}

PROJECT_NAME=$(basename "$PROJECT_PATH")
PROJECT_TYPE=$(detect_project_type "$PROJECT_PATH")

echo -e "${GREEN}📦 Проект: $PROJECT_NAME${NC}"
echo -e "${GREEN}📦 Тип: $PROJECT_TYPE${NC}"

# Создаем .cursorrules
echo -e "${BLUE}📝 Создание .cursorrules...${NC}"

cat > "$CURSOR_RULES_FILE" << EOF
---
description: "Rules for $PROJECT_NAME project"
alwaysApply: true
---

# ПРАВИЛА ПРОЕКТА: $PROJECT_NAME

## 🌍 УНИВЕРСАЛЬНЫЕ ПРАВИЛА

> **⚠️ ВАЖНО:** Эти правила синхронизируются из единой базы \`~/.cursor/universal-rules.md\`
> Для обновления во всех проектах запустите: \`./scripts/sync-cursor-rules.sh\`

EOF

# Вставляем полное содержимое универсальных правил
if [ -f "$UNIVERSAL_RULES_PATH" ]; then
    # Пропускаем frontmatter (строки между ---)
    cat "$UNIVERSAL_RULES_PATH" | sed '/^---$/,/^---$/d' >> "$CURSOR_RULES_FILE"
else
    # Если универсальные правила не найдены, добавляем краткую версию
    cat >> "$CURSOR_RULES_FILE" << 'UNIVERSAL_EOF'

### 👥 Команда экспертов
При работе над проектом **ВСЕГДА** используй формат "команды из 13 экспертов":
- **Виктор (Team Lead)** - координация и архитектура
- **Игорь (Backend Developer)** - написание кода и тесты
- **Анна (QA Engineer)** - тестирование (покрытие > 80%)
- **Максим (Data Analyst)** - анализ данных и метрики
- **Елена (Monitor)** - мониторинг и логи
- **Алексей (Security Engineer)** - безопасность
- **Сергей (DevOps)** - деплой и инфраструктура
- И другие эксперты (см. ~/.cursor/universal-rules.md)

### 🎯 Правильная формулировка промптов
❌ **НЕПРАВИЛЬНО:** "Что ты думаешь об этом?"
✅ **ПРАВИЛЬНО:** "Какие эксперты из команды должны обсудить [тема]? Что бы сказали [Эксперт1], [Эксперт2] и [Эксперт3]?"

### 📋 Общие принципы
- Code Quality: type hints, документация, покрытие тестами > 80%
- Security: не коммитить секреты, использовать env variables
- Performance: оптимизация latency, async/await для I/O
- Stateless: передавать состояние через параметры
- UTC: всегда использовать UTC для временных меток
- Retry: централизованная retry логика с exponential backoff

> 💡 **Для полных универсальных правил см.:** \`~/.cursor/universal-rules.md\`

UNIVERSAL_EOF
fi

cat >> "$CURSOR_RULES_FILE" << 'EOF'

---

## 🎯 СПЕЦИФИЧНЫЕ ДЛЯ ПРОЕКТА ПРАВИЛА

### Тип проекта: $PROJECT_TYPE

EOF

# Добавляем специфичные правила в зависимости от типа проекта
case $PROJECT_TYPE in
    "python")
        cat >> "$CURSOR_RULES_FILE" << 'PYTHON_EOF'

### Python Code Style:
- PEP 8 compliance
- Black formatting (если настроен)
- Type hints обязательны для всех функций
- Docstrings для всех публичных функций и классов

### Python Testing:
- pytest для тестов
- Покрытие тестами > 80%
- Использовать fixtures для тестовых данных
- Mock внешние зависимости

### Python Dependencies:
- Использовать requirements.txt или pyproject.toml
- Зафиксировать версии зависимостей
- Регулярно обновлять и проверять уязвимости

PYTHON_EOF
        ;;
    "javascript/typescript")
        cat >> "$CURSOR_RULES_FILE" << 'JS_EOF'

### TypeScript/JavaScript Code Style:
- TypeScript strict mode (если используется TS)
- ESLint + Prettier
- Использовать современный синтаксис (ES6+)
- Избегать any типов

### Testing:
- Jest или Vitest для тестов
- React Testing Library (если React проект)
- Покрытие тестами > 80%
- Тестировать поведение, не реализацию

JS_EOF
        ;;
    "rust")
        cat >> "$CURSOR_RULES_FILE" << 'RUST_EOF'

### Rust Code Style:
- Следовать rustfmt
- Использовать clippy для проверки
- Обрабатывать все ошибки явно
- Использовать Result для обработки ошибок

### Rust Testing:
- Unit тесты в модулях
- Integration тесты в tests/
- Покрытие тестами > 80%

RUST_EOF
        ;;
    "go")
        cat >> "$CURSOR_RULES_FILE" << 'GO_EOF'

### Go Code Style:
- Следовать gofmt
- Использовать golint и go vet
- Именование: экспортируемые функции с заглавной буквы
- Обрабатывать все ошибки явно

### Go Testing:
- go test для тестов
- Покрытие тестами > 80%
- Использовать table-driven tests

GO_EOF
        ;;
    *)
        cat >> "$CURSOR_RULES_FILE" << 'GENERIC_EOF'

### Общие правила:
- Следовать стандартам кодирования для языка проекта
- Покрытие тестами > 80%
- Документировать публичные API
- Использовать линтеры и форматтеры

GENERIC_EOF
        ;;
esac

# Добавляем секцию для заполнения
cat >> "$CURSOR_RULES_FILE" << 'EOF'

---

## 📁 СТРУКТУРА ПРОЕКТА

[Опишите структуру вашего проекта здесь]

## 🔧 ТЕХНОЛОГИИ

[Перечисли используемые технологии и инструменты]

## 🧪 ТЕСТИРОВАНИЕ

- Фреймворк: [укажите фреймворк для тестов]
- Покрытие: > 80%
- Команда запуска: [make test / npm test / pytest / etc]

## 🚀 ДЕПЛОЙ

[Опишите процесс деплоя проекта]

---

**Создано автоматически:** $(date +"%Y-%m-%d %H:%M:%S")
**Версия правил:** 1.0
**Универсальные правила:** ~/.cursor/universal-rules.md
EOF

echo -e "${GREEN}✅ Файл .cursorrules создан успешно!${NC}"
echo -e "${GREEN}📄 Путь: $CURSOR_RULES_FILE${NC}"
echo -e "${YELLOW}📝 Не забудьте отредактировать файл и заполнить специфичные для проекта правила${NC}"

# Предлагаем открыть файл
if command -v code &> /dev/null; then
    echo -e "${BLUE}💡 Откройте файл в редакторе: code $CURSOR_RULES_FILE${NC}"
fi
