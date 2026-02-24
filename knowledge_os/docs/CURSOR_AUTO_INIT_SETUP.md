# 🚀 Автоматическая инициализация Cursor правил

## 📋 Описание

Эта система автоматически создает `.cursorrules` для новых проектов, применяя универсальные правила команды экспертов.

## ⚡ Быстрая настройка

### Шаг 1: Установите универсальные правила

```bash
# Создайте директорию
mkdir -p ~/.cursor

# Скопируйте универсальные правила
cp docs/examples/universal-cursor-rules.md ~/.cursor/universal-rules.md
```

### Шаг 2: Настройте автоматическую инициализацию

```bash
# Запустите скрипт настройки
./scripts/setup-cursor-auto-init.sh

# Перезагрузите shell
source ~/.zshrc  # или ~/.bashrc
```

### Шаг 3: Проверьте работу

```bash
# Создайте тестовый проект
mkdir -p /tmp/test-project
cd /tmp/test-project

# Автоматически создастся .cursorrules
ls -la .cursorrules
```

## 🔧 Варианты использования

### Вариант 1: Автоматическая инициализация (рекомендуется)

После настройки скрипт автоматически создаст `.cursorrules` при:

- Открытии нового проекта в Cursor
- Открытии существующего проекта без `.cursorrules`
- Открытии проекта с `.cursorrules`, но без универсальных правил
- Смене директории (для zsh)
- Открытии нового терминала (для bash)

### Вариант 2: Ручной запуск

```bash
# Для текущей директории
./scripts/init-cursor-rules.sh

# Для конкретного проекта
./scripts/init-cursor-rules.sh /path/to/project
```

### Вариант 3: Массовая инициализация существующих проектов

```bash
# Инициализировать все проекты в домашней директории
./scripts/init-cursor-rules-all.sh ~

# Инициализировать проекты в конкретной директории
./scripts/init-cursor-rules-all.sh ~/projects

# Инициализировать проекты в текущей директории
./scripts/init-cursor-rules-all.sh .
```

### Вариант 4: Git hook (автоматически при клонировании)

Git hook уже настроен в `.git/hooks/post-checkout` и будет автоматически создавать `.cursorrules` при клонировании репозитория.

## 📁 Структура файлов

```
~/.cursor/
├── universal-rules.md          # Универсальные правила (глобально)
└── templates/
    └── project-template-rules.md # Шаблон для новых проектов

scripts/
├── init-cursor-rules.sh        # Скрипт инициализации
└── setup-cursor-auto-init.sh  # Скрипт настройки автоинициализации
```

## 🎯 Как это работает

1. **Универсальные правила** хранятся в `~/.cursor/universal-rules.md`
   - Команда из 13 экспертов
   - Правила формулировки промптов
   - Общие принципы разработки

2. **Автоматическая инициализация** создает `.cursorrules` в новом проекте:
   - Определяет тип проекта (Python, TypeScript, Rust, Go и т.д.)
   - Добавляет специфичные правила для типа проекта
   - Включает ссылку на универсальные правила

3. **Cursor применяет правила** автоматически при работе с проектом

## 🔍 Проверка работы

### Проверка универсальных правил

```bash
# Проверьте наличие файла
ls -la ~/.cursor/universal-rules.md

# Просмотрите содержимое
head -20 ~/.cursor/universal-rules.md
```

### Проверка автоматической инициализации

```bash
# Создайте тестовый проект
mkdir -p /tmp/test-cursor-project
cd /tmp/test-cursor-project

# Запустите инициализацию
./scripts/init-cursor-rules.sh

# Проверьте созданный файл
cat .cursorrules
```

### Проверка Git hook

```bash
# Клонируйте репозиторий
git clone <your-repo> /tmp/test-clone
cd /tmp/test-clone

# Проверьте наличие .cursorrules
ls -la .cursorrules
```

## 🛠️ Устранение неполадок

### Проблема: Универсальные правила не найдены

```bash
# Решение: Скопируйте вручную
cp docs/examples/universal-cursor-rules.md ~/.cursor/universal-rules.md
```

### Проблема: Автоматическая инициализация не работает

```bash
# Решение 1: Проверьте настройки shell
grep "init_cursor_rules_auto" ~/.zshrc  # или ~/.bashrc

# Решение 2: Перезагрузите shell
source ~/.zshrc  # или ~/.bashrc

# Решение 3: Запустите вручную
./scripts/init-cursor-rules.sh
```

### Проблема: Git hook не работает

```bash
# Решение: Убедитесь, что hook исполняемый
chmod +x .git/hooks/post-checkout
```

## 📚 Дополнительная информация

- **Полное руководство:** `docs/CURSOR_UNIVERSAL_RULES_GUIDE.md`
- **Быстрый старт:** `docs/CURSOR_RULES_QUICK_START.md`
- **Пример правил:** `docs/examples/universal-cursor-rules.md`

## 🔄 Обновление правил

### Обновление универсальных правил

```bash
# Обновите файл
cp docs/examples/universal-cursor-rules.md ~/.cursor/universal-rules.md

# Все новые проекты будут использовать обновленные правила
```

### Обновление правил в существующем проекте

```bash
# Запустите инициализацию заново
./scripts/init-cursor-rules.sh

# Или отредактируйте вручную
code .cursorrules
```

## ✅ Чек-лист настройки

- [ ] Универсальные правила сохранены в `~/.cursor/universal-rules.md`
- [ ] Запущен скрипт настройки `setup-cursor-auto-init.sh`
- [ ] Shell перезагружен (`source ~/.zshrc` или `source ~/.bashrc`)
- [ ] Проверена работа на тестовом проекте
- [ ] Git hook настроен (если используется)

---

**Готово!** Теперь при открытии нового проекта в Cursor автоматически создастся `.cursorrules` с универсальными правилами команды экспертов.
