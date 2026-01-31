# РУКОВОДСТВО ПО ДЕПЛОЮ БОТА ATRA

**Дата:** 2025-12-01  
**Команда:** Сергей (DevOps), Татьяна (Technical Writer)

## ПРЕДВАРИТЕЛЬНЫЕ ТРЕБОВАНИЯ

### На сервере должны быть установлены:
- Python 3.8+
- pip
- git
- systemd (для управления сервисами)

### Необходимые данные доступа:
- SSH доступ к серверу (root@185.177.216.15)
- Пароль SSH
- Telegram токены (DEV и PROD)

---

## ЭТАП 1: ПОДГОТОВКА СЕРВЕРА

### 1.1 Подключение к серверу
```bash
ssh root@185.177.216.15
# Пароль: u44Ww9NmtQj,XG
```

### 1.2 Проверка места на диске
```bash
df -h
# Должно быть минимум 2GB свободного места
```

### 1.3 Очистка диска (если необходимо)
```bash
cd /root/atra
python scripts/aggressive_cleanup.sh
```

---

## ЭТАП 2: ОБНОВЛЕНИЕ КОДА

### 2.1 Обновление из Git
```bash
cd /root/atra
git pull origin main
```

### 2.2 Проверка изменений
```bash
git status
git log --oneline -5
```

---

## ЭТАП 3: ВОССТАНОВЛЕНИЕ БАЗЫ ДАННЫХ

### 3.1 Запуск скрипта восстановления
```bash
cd /root/atra
python scripts/restore_db_on_server.py
```

### 3.2 Проверка целостности БД
```bash
python -c "
import sqlite3
conn = sqlite3.connect('trading.db')
cursor = conn.cursor()
cursor.execute('PRAGMA integrity_check')
result = cursor.fetchone()
print('БД целостна:', result[0] == 'ok')
conn.close()
"
```

---

## ЭТАП 4: УСТАНОВКА ЗАВИСИМОСТЕЙ

### 4.1 Установка Python зависимостей
```bash
cd /root/atra
pip install -r requirements.txt
```

### 4.2 Установка зависимостей для ML
```bash
pip install numpy lightgbm scikit-learn
```

### 4.3 Проверка установки
```bash
python -c "import numpy, lightgbm, sklearn; print('Все зависимости установлены')"
```

---

## ЭТАП 5: ОБУЧЕНИЕ ML МОДЕЛЕЙ

### 5.1 Проверка данных для обучения
```bash
ls -lh ai_learning_data/trading_patterns.json
# Должен быть файл размером ~12MB
```

### 5.2 Запуск обучения
```bash
cd /root/atra
python scripts/retrain_lightgbm.py
```

### 5.3 Проверка результатов
```bash
ls -lh ai_learning_data/lightgbm_models/
# Должны быть файлы:
# - classifier.txt
# - regressor.txt
# - metadata.json
```

---

## ЭТАП 6: ПРОВЕРКА КОНФИГУРАЦИИ

### 6.1 Проверка API ключей
```bash
cd /root/atra
python -c "
from config import TOKEN, TELEGRAM_TOKEN, TELEGRAM_TOKEN_DEV
print('Telegram токены:', 'OK' if TELEGRAM_TOKEN and TELEGRAM_TOKEN_DEV else 'MISSING')
"
```

### 6.2 Проверка фильтров
```bash
python -c "
from config import USE_NEWS_FILTER, USE_WHALE_FILTER
print('News Filter:', 'ENABLED' if USE_NEWS_FILTER else 'DISABLED')
print('Whale Filter:', 'ENABLED' if USE_WHALE_FILTER else 'DISABLED')
"
```

---

## ЭТАП 7: ЗАПУСК БОТА

### 7.1 Остановка старого процесса (если запущен)
```bash
systemctl stop atra-bot
# или
pkill -f signal_live.py
```

### 7.2 Запуск через systemd
```bash
systemctl start atra-bot
systemctl status atra-bot
```

### 7.3 Или запуск вручную (для тестирования)
```bash
cd /root/atra
python signal_live.py
```

---

## ЭТАП 8: ПРОВЕРКА РАБОТЫ

### 8.1 Проверка логов
```bash
tail -f logs/atra.log
# или
journalctl -u atra-bot -f
```

### 8.2 Проверка генерации сигналов
```bash
# Проверить последние сигналы в БД
python -c "
import sqlite3
conn = sqlite3.connect('trading.db')
cursor = conn.cursor()
cursor.execute('SELECT * FROM accepted_signals ORDER BY created_at DESC LIMIT 5')
signals = cursor.fetchall()
print('Последние сигналы:', len(signals))
conn.close()
"
```

### 8.3 Проверка отправки в Telegram
- Проверить получение тестового сигнала в Telegram
- Проверить форматирование сообщения
- Проверить работу кнопок (Accept, Reject)

---

## ЭТАП 9: МОНИТОРИНГ

### 9.1 Проверка процессов
```bash
ps aux | grep signal_live.py
```

### 9.2 Проверка использования ресурсов
```bash
top -p $(pgrep -f signal_live.py)
```

### 9.3 Проверка дискового пространства
```bash
df -h
du -sh /root/atra/logs/
du -sh /root/atra/backups/
```

---

## УСТРАНЕНИЕ ПРОБЛЕМ

### Проблема: БД повреждена
```bash
python scripts/restore_db_on_server.py
```

### Проблема: Недостаточно места на диске
```bash
python scripts/aggressive_cleanup.sh
```

### Проблема: Ошибки импорта
```bash
pip install -r requirements.txt --upgrade
```

### Проблема: Бот не запускается
```bash
# Проверить логи
tail -100 logs/atra.log

# Проверить конфигурацию
python -c "from config import *; print('Config OK')"
```

### Проблема: ML модели не загружаются
```bash
# Переобучить модели
python scripts/retrain_lightgbm.py
```

---

## АВТОМАТИЗАЦИЯ ДЕПЛОЯ

### Скрипт полного деплоя
```bash
#!/bin/bash
# deploy_full.sh

cd /root/atra

# 1. Обновление кода
git pull origin main

# 2. Восстановление БД
python scripts/restore_db_on_server.py

# 3. Установка зависимостей
pip install -r requirements.txt
pip install numpy lightgbm scikit-learn

# 4. Обучение ML моделей
python scripts/retrain_lightgbm.py

# 5. Перезапуск бота
systemctl restart atra-bot

# 6. Проверка статуса
systemctl status atra-bot
```

---

## ПРОВЕРКА УСПЕШНОСТИ ДЕПЛОЯ

### Критерии успешного деплоя:
1. ✅ БД восстановлена и работает
2. ✅ ML модели обучены и загружаются
3. ✅ Бот запущен и работает
4. ✅ Сигналы генерируются
5. ✅ Сигналы отправляются в Telegram
6. ✅ Нет ошибок в логах

### Команда для проверки всех критериев:
```bash
python -c "
import sqlite3
import os

# Проверка БД
conn = sqlite3.connect('trading.db')
cursor = conn.cursor()
cursor.execute('PRAGMA integrity_check')
db_ok = cursor.fetchone()[0] == 'ok'
conn.close()

# Проверка ML моделей
ml_ok = os.path.exists('ai_learning_data/lightgbm_models/classifier.txt')

# Проверка процесса
import subprocess
process_ok = subprocess.run(['pgrep', '-f', 'signal_live.py'], capture_output=True).returncode == 0

print('БД:', 'OK' if db_ok else 'FAIL')
print('ML модели:', 'OK' if ml_ok else 'FAIL')
print('Процесс:', 'OK' if process_ok else 'FAIL')
"
```

---

**Статус:** Готово к деплою
