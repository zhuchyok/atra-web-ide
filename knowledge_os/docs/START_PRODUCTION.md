# 🚀 ЗАПУСК СИСТЕМЫ НА ПРОДАКШН

## 📋 БЫСТРЫЙ ЗАПУСК

### Вариант 1: Автоматический скрипт (рекомендуется)

```bash
# На сервере выполните:
ssh root@185.177.216.15
cd /root/atra
bash scripts/start_production.sh
```

### Вариант 2: Ручной запуск

```bash
# 1. Подключиться к серверу
ssh root@185.177.216.15
# Пароль: u44Ww9NmtQj,XG

# 2. Перейти в директорию проекта
cd /root/atra

# 3. Остановить текущий процесс (если запущен)
ps aux | grep "python.*main.py" | grep -v grep
# Если найден процесс, остановить:
kill -SIGTERM <PID>
sleep 5

# 4. Проверить конфигурацию
cat env | grep ATRA_ENV
# Если не prod, обновить:
sed -i 's/^ATRA_ENV=.*/ATRA_ENV=prod/' env

# 5. Активировать виртуальное окружение (если есть)
source .venv/bin/activate  # или venv/bin/activate

# 6. Создать директорию для логов
mkdir -p logs

# 7. Запустить систему
nohup python3 main.py > logs/atra.log 2>&1 &

# 8. Проверить запуск
ps aux | grep "python.*main.py" | grep -v grep
tail -50 logs/atra.log
```

---

## ✅ ПРОВЕРКА РАБОТЫ

### 1. Проверить, что процесс запущен:

```bash
ps aux | grep "python.*main.py" | grep -v grep
# Должен показать процесс
```

### 2. Проверить логи:

```bash
# Последние 50 строк
tail -50 logs/atra.log

# В реальном времени
tail -f logs/atra.log

# Проверить ошибки
tail -200 logs/atra.log | grep -i error
```

### 3. Проверить Telegram бота:

- Отправьте `/start` боту
- Проверьте ответ

### 4. Проверить генерацию сигналов:

```bash
# Проверить использование оптимального портфеля
tail -200 logs/atra.log | grep -E "AVAXUSDT|LINKUSDT|SOLUSDT|SUIUSDT|DOGEUSDT"

# Проверить динамическое плечо
tail -200 logs/atra.log | grep "DYNAMIC_LEVERAGE"
```

### 5. Проверить базу данных:

```bash
sqlite3 trading.db "SELECT symbol, side, created_at FROM signals ORDER BY created_at DESC LIMIT 10;"
```

---

## ⚠️ ВОЗМОЖНЫЕ ПРОБЛЕМЫ

### Проблема: Процесс не запускается

```bash
# Запустить вручную для диагностики
python3 main.py
# Посмотреть ошибки
```

### Проблема: Нет сигналов

```bash
# Проверить конфигурацию монет
python3 -c "from config import COINS; print(COINS)"

# Проверить фильтры
tail -200 logs/atra.log | grep -E "фильтр|filter|блок|block"
```

### Проблема: Ошибки в Telegram

```bash
# Проверить токен
cat env | grep TELEGRAM_TOKEN

# Проверить логи
tail -100 logs/atra.log | grep -E "Telegram|telegram|error"
```

---

## 📊 МОНИТОРИНГ

### Первые 24 часа проверяйте:

1. Количество сигналов (должно быть несколько в день)
2. Распределение по монетам (все 5 монет портфеля)
3. Использование динамического плеча (2.0x, 2.5x, 3.0x)
4. Ошибки в логах (минимизировать)

---

**Готово к запуску!** 🚀
