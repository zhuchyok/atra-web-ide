# 🚀 ФИНАЛЬНАЯ ИНСТРУКЦИЯ: ОБНОВЛЕНИЕ И ПЕРЕЗАПУСК НА PROD

**Дата:** 18 ноября 2025  
**Цель:** Обновить код на сервере, остановить старые процессы, запустить новый процесс

---

## ✅ **ЧТО УЖЕ СДЕЛАНО:**

1. ✅ Добавлено сохранение сигналов в БД при отправке (`signal_live.py`)
2. ✅ Созданы скрипты диагностики
3. ✅ Созданы инструкции по развертыванию

---

## 📋 **КОМАНДЫ ДЛЯ ВЫПОЛНЕНИЯ:**

### **ШАГ 1: Локально - Commit и Push**

```bash
cd /Users/zhuchyok/Documents/GITHUB/atra/atra

# Остановка локальных процессов (если запущены)
pkill -f "python.*signal_live" 2>/dev/null || true
pkill -f "python.*main.py" 2>/dev/null || true

# Добавление изменений
git add signal_live.py docs/ check_*.py find_*.py deploy_*.sh SERVER_COMMANDS.sh QUICK_DEPLOY_COMMANDS.txt

# Commit
git commit -m "Добавлено сохранение сигналов в БД при отправке + диагностика"

# Push
git push origin insight
```

### **ШАГ 2: На сервере - Обновление и перезапуск**

```bash
# Подключение к серверу
ssh root@185.177.216.15
# Пароль: u44Ww9NmtQj,XG

# Переход в директорию
cd /root/atra

# Обновление кода
git fetch origin
git checkout insight
git pull origin insight

# Остановка ВСЕХ старых процессов (signal_live, main.py, DEV процессы)
pkill -f "python.*signal_live" || true
pkill -f "python.*main.py" || true
sleep 2

# Принудительная остановка оставшихся процессов
ps aux | grep -E "(python.*signal_live|python.*main\.py)" | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null || true

# Проверка, что все остановлено
ps aux | grep -E "(python.*signal_live|python.*main\.py)" | grep -v grep
# Должно быть пусто

# Проверка окружения
python3 -c "from config import ATRA_ENV; print(f'ATRA_ENV: {ATRA_ENV}')"
# Должно быть: prod

# Запуск процесса в PROD режиме
nohup python3 main.py > main.log 2>&1 &
sleep 3

# Проверка, что процесс запустился
ps aux | grep "python.*main.py" | grep -v grep
# Должен показать процесс с PID

# Проверка логов
tail -30 main.log
```

---

## 🔍 **ПРОВЕРКА УСПЕШНОСТИ:**

### **1. Процесс запущен:**

```bash
ps aux | grep "python.*main.py" | grep -v grep
```

### **2. Логи без критических ошибок:**

```bash
tail -50 main.log | grep -i "error\|exception" | tail -5
```

### **3. Сигналы начинают генерироваться:**

```bash
# Подождите 5-10 минут, затем проверьте:
python3 -c "
import sqlite3
from datetime import datetime
conn = sqlite3.connect('trading.db')
cursor = conn.cursor()
cursor.execute('SELECT symbol, created_at FROM signals_log ORDER BY created_at DESC LIMIT 5')
signals = cursor.fetchall()
if signals:
    print('✅ Последние сигналы:')
    for s in signals:
        print(f'  {s[0]} - {s[1]}')
else:
    print('⏳ Сигналов пока нет (подождите 5-10 минут)')
conn.close()
"
```

---

## ⚠️ **ВАЖНО:**

1. **Остановите ВСЕ процессы** перед запуском нового
2. **Проверьте ATRA_ENV** - должно быть `prod`
3. **Проверьте логи** после запуска
4. **Подождите 5-10 минут** перед проверкой сигналов

---

## 📝 **АЛЬТЕРНАТИВА: Использование скрипта**

Если файл `SERVER_COMMANDS.sh` загружен на сервер:

```bash
cd /root/atra
chmod +x SERVER_COMMANDS.sh
./SERVER_COMMANDS.sh
```

---

**Готово! После выполнения этих команд процесс должен работать на сервере в PROD режиме.**
