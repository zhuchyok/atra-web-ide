# 🔄 СИСТЕМА СИНХРОНИЗАЦИИ ДАННЫХ КОМАНДЫ

**Дата:** 2025-12-14  
**Статус:** ✅ **РЕАЛИЗОВАНО**

---

## 🎯 ОПИСАНИЕ

Централизованная система синхронизации данных команды через Git для обеспечения единой базы знаний, обучения, правил и управления во всех проектах.

---

## 📋 ЧТО СИНХРОНИЗИРУЕТСЯ

### **1. Базы знаний сотрудников**

- `scripts/*_knowledge.md` - все базы знаний экспертов
- Содержит: экспертизу, изученные материалы, накопленные знания, лучшие практики

### **2. Программы обучения**

- `scripts/learning_programs/*_program.md` - программы обучения для каждого эксперта
- Содержит: планы обучения, этапы, метрики прогресса

### **3. Правила проекта**

- `.cursorrules` - правила для Cursor IDE
- Содержит: формат работы команды, автоматическую переформулировку промптов

### **4. Управление командой**

- `observability/team_member_manager.py` - управление сотрудниками
- `observability/expert_selector.py` - выбор экспертов для задач
- `observability/knowledge_base.py` - общая база знаний
- `observability/retrospective.py` - ретроспективы
- `observability/continuous_learning.py` - система непрерывного обучения
- `observability/best_practices_searcher.py` - поиск лучших практик

---

## 🚀 БЫСТРЫЙ СТАРТ

### **Вариант 1: Git Submodule (рекомендуется)**

#### **Шаг 1: Создание центрального репозитория**

```bash
# Создайте отдельный репозиторий для данных команды
git init team-data
cd team-data
git remote add origin https://github.com/your-org/team-data.git
```

#### **Шаг 2: Добавление submodule в проекты**

```bash
# В каждом проекте добавьте submodule
cd /path/to/project
git submodule add https://github.com/your-org/team-data.git .team_data
```

#### **Шаг 3: Синхронизация**

```bash
# Синхронизация данных
python scripts/sync_team_data.py sync

# Или отдельно
python scripts/sync_team_data.py push  # Отправить изменения
python scripts/sync_team_data.py pull  # Получить изменения
```

---

### **Вариант 2: Отдельный репозиторий**

#### **Шаг 1: Настройка переменных окружения**

```bash
# Установите URL репозитория данных команды
export TEAM_DATA_REPO="https://github.com/your-org/team-data.git"
export TEAM_DATA_DIR=".team_data"
```

#### **Шаг 2: Первая синхронизация**

```bash
# Инициализация и первая синхронизация
python scripts/sync_team_data.py sync
```

---

## 📖 ИСПОЛЬЗОВАНИЕ

### **Команды синхронизации**

```bash
# Статус синхронизации
python scripts/sync_team_data.py status

# Синхронизация в обе стороны (локально)
python scripts/sync_team_data.py sync

# Отправка изменений в центральный репозиторий
python scripts/sync_team_data.py push

# Загрузка изменений из центрального репозитория
python scripts/sync_team_data.py pull
```

### **С параметрами**

```bash
# Указать удаленный репозиторий
python scripts/sync_team_data.py push --remote https://github.com/your-org/team-data.git

# Указать локальную директорию
python scripts/sync_team_data.py sync --local-dir .team_data
```

---

## 🔧 НАСТРОЙКА

### **Переменные окружения**

```bash
# URL удаленного репозитория
export TEAM_DATA_REPO="https://github.com/your-org/team-data.git"

# Локальная директория для данных
export TEAM_DATA_DIR=".team_data"
```

### **Конфигурация в коде**

Отредактируйте `scripts/sync_team_data.py`:

```python
SYNC_CONFIG = {
    "remote_repo": "https://github.com/your-org/team-data.git",
    "local_dir": ".team_data",
    # ...
}
```

---

## 📁 СТРУКТУРА ДАННЫХ

```
.team_data/
├── .git/                    # Git репозиторий
├── team_data_index.json     # Индекс файлов
├── scripts/
│   ├── viktoriya_knowledge.md
│   ├── dmitriy_knowledge.md
│   └── ...
├── scripts/
│   └── learning_programs/
│       ├── viktoriya_program.md
│       ├── dmitriy_program.md
│       └── ...
├── .cursorrules
└── observability/
    ├── team_member_manager.py
    ├── expert_selector.py
    └── ...
```

---

## 🔄 РАБОЧИЙ ПРОЦЕСС

### **Ежедневная работа**

1. **Начало работы:**

   ```bash
   python scripts/sync_team_data.py pull
   ```

2. **Работа над проектом:**
   - Обновление баз знаний
   - Обучение сотрудников
   - Изменение правил

3. **Перед завершением:**
   ```bash
   python scripts/sync_team_data.py push
   ```

### **Автоматическая синхронизация**

Добавьте в cron или GitHub Actions:

```bash
# Каждый час
0 * * * * cd /path/to/project && python scripts/sync_team_data.py sync
```

---

## 🎯 ПРЕИМУЩЕСТВА

1. **Единая база знаний** - все проекты используют одни и те же данные
2. **Автоматическая синхронизация** - изменения распространяются автоматически
3. **Версионирование** - все изменения отслеживаются через Git
4. **Изоляция проектов** - каждый проект может иметь свои специфичные данные
5. **Масштабируемость** - легко добавлять новые проекты

---

## 🔐 БЕЗОПАСНОСТЬ

### **Рекомендации:**

1. **Приватный репозиторий** - используйте приватный репозиторий для данных команды
2. **Access tokens** - используйте токены доступа вместо паролей
3. **Шифрование** - для чувствительных данных используйте шифрование
4. **Backup** - регулярно создавайте резервные копии

---

## 🚨 УСТРАНЕНИЕ ПРОБЛЕМ

### **Проблема: Конфликты при синхронизации**

```bash
# Решение: Разрешить конфликты вручную
cd .team_data
git status
# Разрешите конфликты
git add .
git commit -m "Resolve conflicts"
```

### **Проблема: Репозиторий не найден**

```bash
# Решение: Инициализировать заново
rm -rf .team_data
python scripts/sync_team_data.py sync
```

### **Проблема: Файлы не синхронизируются**

```bash
# Решение: Проверить статус
python scripts/sync_team_data.py status
# Проверить права доступа
ls -la scripts/*_knowledge.md
```

---

## 📊 МОНИТОРИНГ

### **Проверка статуса**

```bash
python scripts/sync_team_data.py status
```

**Вывод:**

```
📊 Статус синхронизации:
  Локальный репозиторий: ✅
  Git инициализирован: ✅
  Файлов: 45
  Последняя синхронизация: 2025-12-14T10:30:00+00:00
```

---

## 🔗 ИНТЕГРАЦИЯ С CURSOR

### **Автоматическая активация**

После синхронизации команда автоматически активируется в Cursor:

1. Скопируйте `.cursorrules` из `.team_data` в корень проекта
2. Откройте новый чат в Cursor
3. Виктория автоматически активирует команду из 22 экспертов

---

## ✅ ЧЕКЛИСТ НАСТРОЙКИ

- [ ] Создан центральный репозиторий для данных команды
- [ ] Настроены переменные окружения (TEAM_DATA_REPO, TEAM_DATA_DIR)
- [ ] Выполнена первая синхронизация (`sync`)
- [ ] Настроена автоматическая синхронизация (cron/GitHub Actions)
- [ ] Проверен статус синхронизации (`status`)
- [ ] Протестирована синхронизация в обоих направлениях

---

## 📝 ПРИМЕРЫ

### **Пример 1: Первая настройка**

```bash
# 1. Установить переменные окружения
export TEAM_DATA_REPO="https://github.com/your-org/team-data.git"
export TEAM_DATA_DIR=".team_data"

# 2. Первая синхронизация
python scripts/sync_team_data.py sync

# 3. Проверить статус
python scripts/sync_team_data.py status
```

### **Пример 2: Обновление данных**

```bash
# 1. Получить последние изменения
python scripts/sync_team_data.py pull

# 2. Работа над проектом...

# 3. Отправить изменения
python scripts/sync_team_data.py push
```

### **Пример 3: Использование в новом проекте**

```bash
# 1. Клонировать проект
git clone https://github.com/your-org/new-project.git
cd new-project

# 2. Добавить submodule (если используется)
git submodule add https://github.com/your-org/team-data.git .team_data

# 3. Синхронизировать данные
python scripts/sync_team_data.py pull

# 4. Скопировать .cursorrules
cp .team_data/.cursorrules .cursorrules
```

---

## 🎓 ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ

- **Документация Git Submodules:** https://git-scm.com/book/en/v2/Git-Tools-Submodules
- **Документация Cursor Rules:** `docs/HOW_TO_USE_EXPERTS_IN_NEW_PROJECT.md`

---

**Автор:** Виктория (Team Lead)  
**Дата:** 2025-12-14  
**Статус:** ✅ **ГОТОВО К ИСПОЛЬЗОВАНИЮ**
