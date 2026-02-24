# 🚀 Быстрый старт: Универсальные правила для Cursor

## 📋 Что это?

Это руководство поможет настроить агентов Cursor для работы с **любым проектом**, а не только с ATRA.

## ⚡ Быстрая настройка (3 шага)

### Шаг 1: Сохраните универсальные правила

```bash
# Создайте директорию для правил
mkdir -p ~/.cursor

# Скопируйте универсальные правила
cp docs/examples/universal-cursor-rules.md ~/.cursor/universal-rules.md
```

### Шаг 2: Создайте .cursorrules для нового проекта

**Вариант A: Используйте скрипт (рекомендуется)**

```bash
# Из директории проекта
./scripts/create-cursor-rules.sh "My Project" .

# Или укажите путь явно
./scripts/create-cursor-rules.sh "My Project" /path/to/project
```

**Вариант B: Создайте вручную**

```bash
# Создайте .cursorrules в корне проекта
touch .cursorrules
```

Затем скопируйте содержимое из `docs/examples/universal-cursor-rules.md` и добавьте специфичные для проекта правила.

### Шаг 3: Отредактируйте .cursorrules

Откройте `.cursorrules` и добавьте:

1. **Описание проекта**
2. **Структуру проекта**
3. **Используемые технологии**
4. **Специфичные правила** (если есть)

## 📖 Примеры

### Пример для Python проекта

```markdown
---
description: "Python web application"
alwaysApply: true
---

# ПРАВИЛА ПРОЕКТА: My Python App

## 🌍 УНИВЕРСАЛЬНЫЕ ПРАВИЛА

[Включите универсальные правила]

## 🐍 PYTHON СПЕЦИФИЧНЫЕ ПРАВИЛА

### Code Style:

- PEP 8
- Black formatting
- Type hints обязательны

### Testing:

- pytest
- Покрытие > 80%
```

### Пример для TypeScript проекта

```markdown
---
description: "React TypeScript app"
alwaysApply: true
---

# ПРАВИЛА ПРОЕКТА: My React App

## 🌍 УНИВЕРСАЛЬНЫЕ ПРАВИЛА

[Включите универсальные правила]

## ⚛️ REACT СПЕЦИФИЧНЫЕ ПРАВИЛА

### Code Style:

- TypeScript strict mode
- ESLint + Prettier
- Functional components

### Testing:

- Jest + React Testing Library
- Покрытие > 80%
```

## 🎯 Как это работает?

1. **Универсальные правила** содержат:
   - Команду из 13 экспертов
   - Правила формулировки промптов
   - Общие принципы разработки
   - Stateless архитектура
   - Retry логика
   - И другие универсальные практики

2. **Специфичные правила** в `.cursorrules` содержат:
   - Описание проекта
   - Архитектуру
   - Технологии
   - Специфичные для проекта правила

3. **Cursor применяет правила** автоматически при работе с проектом

## ✅ Чек-лист

- [ ] Универсальные правила сохранены в `~/.cursor/universal-rules.md`
- [ ] Создан `.cursorrules` в новом проекте
- [ ] Добавлены универсальные правила (или ссылка на них)
- [ ] Добавлены специфичные для проекта правила
- [ ] Проверена работа агента с новыми правилами

## 📚 Дополнительная информация

- **Полное руководство:** `docs/CURSOR_UNIVERSAL_RULES_GUIDE.md`
- **Пример универсальных правил:** `docs/examples/universal-cursor-rules.md`
- **Скрипт создания правил:** `scripts/create-cursor-rules.sh`

## 🔗 Полезные ссылки

- [Документация Cursor](https://docs.cursor.com)
- [Фоновые агенты Cursor](https://docs.cursor.com/ru/background-agent)

---

**Вопросы?** Обратитесь к команде экспертов или создайте issue в репозитории.
