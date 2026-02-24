# ✅ АВТОМАТИЧЕСКАЯ СИНХРОНИЗАЦИЯ НАСТРОЕНА

**Дата:** 2025-12-14  
**Статус:** ✅ **ВЫПОЛНЕНО**

---

## 🎯 ЧТО СДЕЛАНО

### **1. Локальный репозиторий инициализирован**

- ✅ Создана директория `.team_data/`
- ✅ Инициализирован Git репозиторий
- ✅ Выполнена первая синхронизация

### **2. Данные синхронизированы**

- ✅ Базы знаний сотрудников
- ✅ Программы обучения
- ✅ Правила Cursor (`.cursorrules`)
- ✅ Управление командой

### **3. Автоматизация настроена**

- ✅ Скрипт автоматической синхронизации (`scripts/auto_sync_team_data.sh`)
- ✅ Готов к добавлению в cron

---

## 🚀 ИСПОЛЬЗОВАНИЕ

### **Ручная синхронизация**

```bash
# Синхронизация в обе стороны
python scripts/sync_team_data.py sync

# Или через скрипт
bash scripts/auto_sync_team_data.sh
```

### **Автоматическая синхронизация (cron)**

Добавьте в crontab:

```bash
# Каждый час
0 * * * * cd /path/to/atra && bash scripts/auto_sync_team_data.sh >> /tmp/team_sync.log 2>&1

# Или каждые 6 часов
0 */6 * * * cd /path/to/atra && bash scripts/auto_sync_team_data.sh >> /tmp/team_sync.log 2>&1
```

---

## 📦 СТРУКТУРА

```
.team_data/
├── .git/                    # Git репозиторий
├── team_data_index.json     # Индекс файлов
├── scripts/
│   ├── *_knowledge.md       # Базы знаний
│   └── learning_programs/
│       └── *_program.md     # Программы обучения
├── .cursorrules            # Правила Cursor
└── observability/
    └── *.py                # Управление командой
```

---

## 🔗 НАСТРОЙКА УДАЛЕННОГО РЕПОЗИТОРИЯ

### **Шаг 1: Создать репозиторий на GitHub/GitLab**

1. Создайте новый репозиторий (например, `team-data`)
2. Скопируйте URL репозитория

### **Шаг 2: Добавить remote**

```bash
cd .team_data
git remote add origin https://github.com/your-org/team-data.git
git branch -M main
git push -u origin main
```

### **Шаг 3: Настроить переменные окружения**

```bash
export TEAM_DATA_REPO="https://github.com/your-org/team-data.git"
export TEAM_DATA_DIR=".team_data"
```

Или создать `.env.team_sync`:

```bash
export TEAM_DATA_REPO="https://github.com/your-org/team-data.git"
export TEAM_DATA_DIR=".team_data"
```

---

## ✅ ПРОВЕРКА

```bash
# Статус синхронизации
python scripts/sync_team_data.py status

# Проверка файлов
ls -la .team_data/
```

---

## 🎯 ДЛЯ НОВЫХ ПРОЕКТОВ

1. **Клонировать проект**
2. **Выполнить синхронизацию:**
   ```bash
   python scripts/sync_team_data.py pull
   ```
3. **Скопировать правила:**
   ```bash
   cp .team_data/.cursorrules .cursorrules
   ```

---

## 📊 ТЕКУЩИЙ СТАТУС

- ✅ Локальный репозиторий: создан
- ✅ Git инициализирован: да
- ✅ Первая синхронизация: выполнена
- ⏳ Удаленный репозиторий: нужно настроить (опционально)

---

**Автор:** Виктория (Team Lead)  
**Дата:** 2025-12-14
