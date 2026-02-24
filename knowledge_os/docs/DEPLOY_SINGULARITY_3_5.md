# 🚀 ДЕПЛОЙ SINGULARITY 3.5 НА СЕРВЕР

**Дата:** 2025-12-14  
**Версия:** Singularity 3.5  
**Статус:** 📋 **ИНСТРУКЦИЯ ПО ДЕПЛОЮ**

---

## 🎯 ЧТО НУЖНО ЗАДЕПЛОИТЬ

### **Новые файлы для деплоя:**

1. **Мониторинг и бэкапы:**
   - `knowledge_os/app/enhanced_monitor.py`
   - `knowledge_os/scripts/setup_automated_backups.sh`
   - `knowledge_os/scripts/setup_monitoring.sh`
   - `knowledge_os/scripts/setup_all_monitoring.sh`
   - `knowledge_os/scripts/restore_from_backup.sh`

2. **Orchestrator:**
   - `knowledge_os/app/enhanced_orchestrator.py`
   - `knowledge_os/db/migrations/add_tasks_table.sql`

3. **Поиск:**
   - `knowledge_os/app/enhanced_search.py`
   - `knowledge_os/app/main_enhanced.py`

4. **Иммунитет:**
   - `knowledge_os/app/enhanced_immunity.py`

5. **Аналитика:**
   - `knowledge_os/dashboard/enhanced_analytics.py`
   - `knowledge_os/dashboard/app_enhanced.py`

---

## 🚀 СПОСОБ 1: АВТОМАТИЧЕСКИЙ ДЕПЛОЙ

### **Использование скрипта:**

```bash
cd /path/to/atra/knowledge_os
bash scripts/deploy_enhancements.sh
```

**Скрипт автоматически:**

- ✅ Проверит подключение к серверу
- ✅ Создаст необходимые директории
- ✅ Загрузит все файлы
- ✅ Установит права доступа
- ✅ Применит миграцию БД (если возможно)

---

## 📋 СПОСОБ 2: РУЧНОЙ ДЕПЛОЙ

### **Шаг 1: Подключение к серверу**

```bash
ssh root@185.177.216.15
# Пароль: u44Ww9NmtQj,XG
```

### **Шаг 2: Создание директорий**

```bash
cd /root/knowledge_os
mkdir -p app scripts dashboard db/migrations
```

### **Шаг 3: Загрузка файлов**

**С локальной машины:**

```bash
# Мониторинг
scp knowledge_os/app/enhanced_monitor.py root@185.177.216.15:/root/knowledge_os/app/
scp knowledge_os/scripts/setup_*.sh root@185.177.216.15:/root/knowledge_os/scripts/
scp knowledge_os/scripts/restore_from_backup.sh root@185.177.216.15:/root/knowledge_os/scripts/

# Orchestrator
scp knowledge_os/app/enhanced_orchestrator.py root@185.177.216.15:/root/knowledge_os/app/
scp knowledge_os/db/migrations/add_tasks_table.sql root@185.177.216.15:/root/knowledge_os/db/migrations/

# Поиск
scp knowledge_os/app/enhanced_search.py root@185.177.216.15:/root/knowledge_os/app/
scp knowledge_os/app/main_enhanced.py root@185.177.216.15:/root/knowledge_os/app/

# Иммунитет
scp knowledge_os/app/enhanced_immunity.py root@185.177.216.15:/root/knowledge_os/app/

# Аналитика
scp knowledge_os/dashboard/enhanced_analytics.py root@185.177.216.15:/root/knowledge_os/dashboard/
scp knowledge_os/dashboard/app_enhanced.py root@185.177.216.15:/root/knowledge_os/dashboard/
```

### **Шаг 4: Установка прав**

```bash
ssh root@185.177.216.15
cd /root/knowledge_os
chmod +x scripts/*.sh
```

---

## 🔧 НАСТРОЙКА НА СЕРВЕРЕ

### **1. Применение миграции БД**

```bash
cd /root/knowledge_os
psql -U admin -d knowledge_os -f db/migrations/add_tasks_table.sql
```

### **2. Установка зависимостей**

```bash
pip3 install psutil
```

### **3. Настройка мониторинга и бэкапов**

```bash
cd /root/knowledge_os
bash scripts/setup_all_monitoring.sh
```

### **4. Настройка cron задач**

```bash
crontab -e
```

**Добавить:**

```cron
# Мониторинг (каждые 5 минут)
*/5 * * * * cd /root/knowledge_os && python3 app/enhanced_monitor.py >> logs/cron_monitor.log 2>&1

# Orchestrator (каждые 30 минут)
*/30 * * * * cd /root/knowledge_os && python3 app/enhanced_orchestrator.py >> logs/orchestrator.log 2>&1

# Иммунитет (каждые 6 часов)
0 */6 * * * cd /root/knowledge_os && python3 app/enhanced_immunity.py >> logs/immunity.log 2>&1

# Бэкапы (ежедневно в 3:00)
0 3 * * * bash /root/knowledge_os/scripts/backup_db.sh >> /root/knowledge_os/logs/cron_backup.log 2>&1
```

---

## 🧪 ПРОВЕРКА ДЕПЛОЯ

### **1. Проверка файлов:**

```bash
ssh root@185.177.216.15
cd /root/knowledge_os

# Проверка мониторинга
ls -la app/enhanced_monitor.py
ls -la scripts/setup_*.sh

# Проверка Orchestrator
ls -la app/enhanced_orchestrator.py
ls -la db/migrations/add_tasks_table.sql

# Проверка поиска
ls -la app/enhanced_search.py
ls -la app/main_enhanced.py

# Проверка иммунитета
ls -la app/enhanced_immunity.py

# Проверка аналитики
ls -la dashboard/enhanced_analytics.py
ls -la dashboard/app_enhanced.py
```

### **2. Тестовый запуск:**

```bash
# Мониторинг
python3 app/enhanced_monitor.py

# Orchestrator
python3 app/enhanced_orchestrator.py

# Иммунитет
python3 app/enhanced_immunity.py

# Dashboard
cd dashboard
streamlit run app_enhanced.py --server.port 8502
```

### **3. Проверка БД:**

```bash
psql -U admin -d knowledge_os -c "\d tasks"
psql -U admin -d knowledge_os -c "SELECT count(*) FROM tasks;"
```

---

## 📊 ЧЕКЛИСТ ДЕПЛОЯ

- [ ] Файлы загружены на сервер
- [ ] Права доступа установлены
- [ ] Миграция БД применена
- [ ] Зависимости установлены (psutil)
- [ ] Мониторинг настроен (setup_all_monitoring.sh)
- [ ] Cron задачи настроены
- [ ] Тестовый запуск успешен
- [ ] Dashboard доступен

---

## 🚨 РЕШЕНИЕ ПРОБЛЕМ

### **Проблема: SSH подключение не работает**

**Решение:**

```bash
# Использовать пароль при подключении
ssh -o PreferredAuthentications=password root@185.177.216.15

# Или настроить SSH ключ
ssh-copy-id root@185.177.216.15
```

### **Проблема: Миграция БД не применяется**

**Решение:**

```bash
# Применить вручную
psql -U admin -d knowledge_os -f db/migrations/add_tasks_table.sql

# Проверить ошибки
psql -U admin -d knowledge_os -c "\d tasks"
```

### **Проблема: Модули не найдены**

**Решение:**

```bash
# Проверить импорты
python3 -c "from enhanced_search import EnhancedAnalytics"

# Установить зависимости
pip3 install psutil asyncpg httpx redis
```

---

## ✅ ГОТОВО!

После деплоя все улучшения Singularity 3.5 будут работать на сервере!

**Автор:** Виктория (Team Lead)  
**Дата:** 2025-12-14
