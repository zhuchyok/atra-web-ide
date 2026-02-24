# 🚀 БЫСТРЫЙ СТАРТ: СИНХРОНИЗАЦИЯ ДАННЫХ КОМАНДЫ

**Дата:** 2025-12-14  
**Статус:** ✅ **ГОТОВО**

---

## ⚡ 3 ШАГА ДЛЯ НАСТРОЙКИ

### **Шаг 1: Запустить скрипт настройки**

```bash
bash scripts/setup_team_sync.sh
```

Скрипт запросит:

- URL репозитория данных команды (или пропустить)
- Локальную директорию (по умолчанию `.team_data`)
- Создать ли `.env` файл
- Выполнить ли первую синхронизацию

---

### **Шаг 2: Настроить переменные окружения (если нужно)**

```bash
# Если не создали .env файл
export TEAM_DATA_REPO="https://github.com/your-org/team-data.git"
export TEAM_DATA_DIR=".team_data"
```

---

### **Шаг 3: Использовать синхронизацию**

```bash
# Статус
python scripts/sync_team_data.py status

# Синхронизация (в обе стороны)
python scripts/sync_team_data.py sync

# Отправить изменения
python scripts/sync_team_data.py push

# Получить изменения
python scripts/sync_team_data.py pull
```

---

## 📋 ЧТО СИНХРОНИЗИРУЕТСЯ

✅ Базы знаний сотрудников (`scripts/*_knowledge.md`)  
✅ Программы обучения (`scripts/learning_programs/*_program.md`)  
✅ Правила Cursor (`.cursorrules`)  
✅ Управление командой (`observability/*.py`)

---

## 🎯 ДЛЯ НОВОГО ПРОЕКТА

```bash
# 1. Клонировать проект
git clone https://github.com/your-org/new-project.git
cd new-project

# 2. Настроить синхронизацию
bash scripts/setup_team_sync.sh

# 3. Получить данные команды
python scripts/sync_team_data.py pull

# 4. Скопировать правила в проект
cp .team_data/.cursorrules .cursorrules
```

---

## ✅ ГОТОВО!

Теперь все проекты используют единую базу знаний, обучения и правил команды!

**Подробная документация:** `docs/TEAM_DATA_SYNC_SYSTEM.md`

---

**Автор:** Виктория (Team Lead)
