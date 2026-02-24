#!/bin/bash

# Скрипт для создания .cursorrules в новом проекте
# Использование: ./create-cursor-rules.sh <project-name> <project-path>

set -e

PROJECT_NAME="${1:-$(basename "$(pwd)")}"
PROJECT_PATH="${2:-$(pwd)}"
UNIVERSAL_RULES_PATH="$HOME/.cursor/universal-rules.md"

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Создание .cursorrules для проекта: $PROJECT_NAME${NC}"
echo -e "${YELLOW}Путь: $PROJECT_PATH${NC}"

# Проверяем, существует ли директория проекта
if [ ! -d "$PROJECT_PATH" ]; then
    echo -e "${RED}❌ Ошибка: Директория $PROJECT_PATH не существует${NC}"
    exit 1
fi

# Проверяем, существует ли уже .cursorrules
if [ -f "$PROJECT_PATH/.cursorrules" ]; then
    echo -e "${YELLOW}⚠️  Файл .cursorrules уже существует${NC}"
    read -p "Перезаписать? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Отменено${NC}"
        exit 0
    fi
fi

# Определяем тип проекта
detect_project_type() {
    if [ -f "$PROJECT_PATH/package.json" ]; then
        echo "javascript/typescript"
    elif [ -f "$PROJECT_PATH/requirements.txt" ] || [ -f "$PROJECT_PATH/pyproject.toml" ]; then
        echo "python"
    elif [ -f "$PROJECT_PATH/Cargo.toml" ]; then
        echo "rust"
    elif [ -f "$PROJECT_PATH/go.mod" ]; then
        echo "go"
    elif [ -f "$PROJECT_PATH/pom.xml" ] || [ -f "$PROJECT_PATH/build.gradle" ]; then
        echo "java"
    else
        echo "generic"
    fi
}

PROJECT_TYPE=$(detect_project_type)
echo -e "${GREEN}📦 Определен тип проекта: $PROJECT_TYPE${NC}"

# Создаем .cursorrules
cat > "$PROJECT_PATH/.cursorrules" << EOF
---
description: "Rules for $PROJECT_NAME project"
alwaysApply: true
---

# ПРАВИЛА ПРОЕКТА: $PROJECT_NAME

## 🌍 УНИВЕРСАЛЬНЫЕ ПРАВИЛА

> **Примечание:** Универсальные правила команды экспертов применяются автоматически.
> См. \`~/.cursor/universal-rules.md\` для деталей.

### Команда экспертов
При работе над проектом **ВСЕГДА** используй формат "команды из 13 экспертов":
- Виктор (Team Lead) - координация и архитектура
- Игорь (Backend Developer) - написание кода и тесты
- Анна (QA Engineer) - тестирование (покрытие > 80%)
- И другие эксперты (см. универсальные правила)

### Правильная формулировка промптов
❌ НЕПРАВИЛЬНО: "Что ты думаешь об этом?"
✅ ПРАВИЛЬНО: "Какие эксперты из команды должны обсудить [тема]? Что бы сказали [Эксперт1], [Эксперт2] и [Эксперт3]?"

---

## 🎯 СПЕЦИФИЧНЫЕ ДЛЯ ПРОЕКТА ПРАВИЛА

### Тип проекта: $PROJECT_TYPE

EOF

# Добавляем специфичные правила в зависимости от типа проекта
case $PROJECT_TYPE in
    "python")
        cat >> "$PROJECT_PATH/.cursorrules" << 'PYTHON_EOF'

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

### Python Structure:
```
src/          # Исходный код
tests/        # Тесты
docs/         # Документация
scripts/      # Вспомогательные скрипты
```

PYTHON_EOF
        ;;
    "javascript/typescript")
        cat >> "$PROJECT_PATH/.cursorrules" << 'JS_EOF'

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

### Dependencies:
- Использовать package.json
- Зафиксировать версии (package-lock.json или yarn.lock)
- Регулярно обновлять зависимости

JS_EOF
        ;;
    "rust")
        cat >> "$PROJECT_PATH/.cursorrules" << 'RUST_EOF'

### Rust Code Style:
- Следовать rustfmt
- Использовать clippy для проверки
- Обрабатывать все ошибки явно
- Использовать Result для обработки ошибок

### Rust Testing:
- Unit тесты в модулях
- Integration тесты в tests/
- Покрытие тестами > 80%
- Использовать #[cfg(test)] для тестовых модулей

RUST_EOF
        ;;
    "go")
        cat >> "$PROJECT_PATH/.cursorrules" << 'GO_EOF'

### Go Code Style:
- Следовать gofmt
- Использовать golint и go vet
- Именование: экспортируемые функции с заглавной буквы
- Обрабатывать все ошибки явно

### Go Testing:
- go test для тестов
- Покрытие тестами > 80%
- Использовать table-driven tests
- Тестировать все публичные функции

GO_EOF
        ;;
    *)
        cat >> "$PROJECT_PATH/.cursorrules" << 'GENERIC_EOF'

### Общие правила:
- Следовать стандартам кодирования для языка проекта
- Покрытие тестами > 80%
- Документировать публичные API
- Использовать линтеры и форматтеры

GENERIC_EOF
        ;;
esac

# Добавляем общие правила
cat >> "$PROJECT_PATH/.cursorrules" << 'EOF'

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

**Создано:** $(date +"%Y-%m-%d")
**Версия правил:** 1.0
EOF

echo -e "${GREEN}✅ Файл .cursorrules создан успешно!${NC}"
echo -e "${YELLOW}📝 Не забудьте отредактировать файл и заполнить специфичные для проекта правила${NC}"
echo -e "${GREEN}📄 Путь: $PROJECT_PATH/.cursorrules${NC}"

# Предлагаем открыть файл в редакторе
if command -v code &> /dev/null; then
    read -p "Открыть файл в VS Code? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        code "$PROJECT_PATH/.cursorrules"
    fi
fi
