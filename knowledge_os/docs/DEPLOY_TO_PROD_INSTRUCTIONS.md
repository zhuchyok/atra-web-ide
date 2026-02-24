# 🚀 ИНСТРУКЦИЯ: ОБНОВЛЕНИЕ И ПЕРЕЗАПУСК НА PROD СЕРВЕРЕ

**Дата:** 18 ноября 2025  
**Задача:** Обновить код, остановить старые процессы, запустить новый процесс в PROD режиме

---

## 📋 **ПОШАГОВАЯ ИНСТРУКЦИЯ**

### **1. Локально: Commit и Push изменений**

```bash
cd /Users/zhuchyok/Documents/GITHUB/atra/atra

# Проверка статуса
git status

# Добавление изменений
git add signal_live.py docs/SIGNAL_*.md check_*.py find_*.py deploy_*.sh

# Commit
git commit -m "Добавлено сохранение сигналов в БД при отправке + диагностика"

# Push
git push origin insight
```

### **2. Подключение к серверу**

```bash
ssh root@185.177.216.15
# Пароль: u44Ww9NmtQj,XG
```

### **3. На сервере: Обновление кода**

```bash
cd /root/atra

# Обновление с git
git fetch origin
git checkout insight
git pull origin insight

# Проверка изменений
git log --oneline -5
```

### **4. На сервере: Остановка старых процессов**

```bash
# Остановка всех процессов Python связанных с atra
pkill -f "python.*signal_live" || true
pkill -f "python.*main.py" || true

# Ждем 2 секунды
sleep 2

# Проверяем, что процессы остановлены
ps aux | grep -E "(python.*signal_live|python.*main\.py)" | grep -v grep

# Если процессы еще есть, принудительная остановка
ps aux | grep -E "(python.*signal_live|python.*main\.py)" | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null || true

# Финальная проверка
ps aux | grep -E "(python.*signal_live|python.*main\.py)" | grep -v grep
# Должно быть пусто
```

### **5. На сервере: Проверка окружения**

```bash
# Проверка ATRA_ENV
python3 -c "from config import ATRA_ENV; print(f'ATRA_ENV: {ATRA_ENV}')"

# Должно быть: prod
# Если не prod, проверьте файл env:
cat env | grep ATRA_ENV

# Если нужно, установите:
export ATRA_ENV=prod
# Или отредактируйте файл env
```

### **6. На сервере: Запуск процесса**

```bash
# Запуск в фоне с логами
nohup python3 main.py > main.log 2>&1 &

# Ждем 3 секунды
sleep 3

# Проверка, что процесс запустился
ps aux | grep -E "python.*main\.py" | grep -v grep

# Должен показать процесс с PID
```

### **7. На сервере: Проверка логов**

```bash
# Последние строки лога
tail -50 main.log

# Мониторинг в реальном времени
tail -f main.log
```

---

## ✅ **ПРОВЕРКА УСПЕШНОСТИ**

### **1. Процесс запущен:**

```bash
ps aux | grep "python.*main.py" | grep -v grep
# Должен показать процесс
```

### **2. Логи без критических ошибок:**

```bash
tail -100 main.log | grep -i "error\|exception" | tail -10
# Должно быть минимум ошибок
```

### **3. Сигналы генерируются:**

```bash
# Проверка последних сигналов в БД
python3 -c "
import sqlite3
from datetime import datetime
conn = sqlite3.connect('trading.db')
cursor = conn.cursor()
cursor.execute('SELECT symbol, created_at FROM signals_log ORDER BY created_at DESC LIMIT 5')
signals = cursor.fetchall()
if signals:
    print('Последние сигналы:')
    for s in signals:
        print(f'  {s[0]} - {s[1]}')
else:
    print('Сигналов пока нет')
conn.close()
"
```

---

## 🔧 **АЛЬТЕРНАТИВНЫЙ СПОСОБ (через скрипт)**

Если скрипт `deploy_to_server_manual.sh` загружен на сервер:

```bash
cd /root/atra
chmod +x deploy_to_server_manual.sh
./deploy_to_server_manual.sh
```

---

## ⚠️ **ВОЗМОЖНЫЕ ПРОБЛЕМЫ**

### **1. Процесс не запускается:**

```bash
# Проверьте логи
tail -50 main.log

# Проверьте зависимости
python3 -c "import sqlite3, pandas, aiohttp; print('OK')"

# Проверьте права доступа
ls -la main.py
```

### **2. Ошибки при импорте:**

```bash
# Проверьте Python версию
python3 --version

# Проверьте установленные пакеты
pip3 list | grep -E "(pandas|aiohttp|sqlite3)"
```

### **3. Процесс падает сразу после запуска:**

```bash
# Запустите в foreground для просмотра ошибок
python3 main.py
```

---

## 📝 **ПОСЛЕ ЗАПУСКА**

1. ✅ Проверьте, что процесс работает: `ps aux | grep main.py`
2. ✅ Проверьте логи: `tail -f main.log`
3. ✅ Подождите 5-10 минут и проверьте, появились ли сигналы
4. ✅ Проверьте базу данных на наличие новых сигналов

---

**Готово! Процесс должен работать на сервере в PROD режиме.**
