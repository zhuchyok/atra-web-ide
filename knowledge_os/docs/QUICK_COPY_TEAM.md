# ⚡ БЫСТРОЕ КОПИРОВАНИЕ КОМАНДЫ В НОВЫЙ ПРОЕКТ

**Дата:** 2025-12-14  
**Статус:** ✅ **ГОТОВО**

---

> **⚠️ ВАЖНО:** `.team_data` — это **ОПЦИОНАЛЬНО**!  
> Для работы команды достаточно только `.cursorrules`.  
> Если видите сообщение про отсутствие `.team_data` — это нормально, команда работает!  
> См. `docs/TEAM_DATA_EXPLANATION.md` для подробностей.

---

## 🚀 ОДНА КОМАНДА - ВСЁ ГОТОВО!

### **Автоматическое копирование:**

```bash
# Из проекта ATRA выполните:
bash scripts/copy_team_to_new_project.sh /path/to/new-project
```

**Пример:**

```bash
bash scripts/copy_team_to_new_project.sh ~/projects/new-website
```

---

## 📋 ЧТО ДЕЛАЕТ СКРИПТ

1. ✅ Копирует `.cursorrules` в новый проект
2. ✅ Создает директорию `scripts/`
3. ✅ Копирует скрипты синхронизации
4. ✅ Копирует данные команды (опционально)
5. ✅ Инициализирует Git репозиторий для данных
6. ✅ Проверяет настройку

---

## ✅ ПОСЛЕ ВЫПОЛНЕНИЯ

1. **Откройте проект в Cursor:**

   ```bash
   cd /path/to/new-project
   cursor .
   ```

2. **Откройте новый чат в Cursor**

3. **Опишите задачу:**

   ```
   Создать новый корпоративный сайт
   ```

4. **Виктория автоматически активирует команду!** 🎉

---

## 🔄 РУЧНОЕ КОПИРОВАНИЕ (если скрипт не работает)

### **Минимальный вариант (только правила) - РЕКОМЕНДУЕТСЯ:**

```bash
# 1. Скопировать .cursorrules
cp /path/to/atra/.cursorrules /path/to/new-project/.cursorrules

# 2. Готово! Откройте Cursor и начните работать
```

> **💡 Этого достаточно!** Команда работает без `.team_data`.  
> Если видите сообщение про `.team_data` — это информационное, не ошибка.

### **Полный вариант (с данными):**

```bash
# 1. Скопировать .cursorrules
cp /path/to/atra/.cursorrules /path/to/new-project/.cursorrules

# 2. Скопировать скрипты
mkdir -p /path/to/new-project/scripts
cp /path/to/atra/scripts/sync_team_data.py /path/to/new-project/scripts/
chmod +x /path/to/new-project/scripts/sync_team_data.py

# 3. Скопировать данные команды
cp -r /path/to/atra/.team_data /path/to/new-project/

# 4. Готово!
```

---

## 📖 ПОДРОБНАЯ ИНСТРУКЦИЯ

См. `docs/STEP_BY_STEP_NEW_PROJECT_SETUP.md` для пошаговой инструкции.

---

**Автор:** Виктория (Team Lead)
