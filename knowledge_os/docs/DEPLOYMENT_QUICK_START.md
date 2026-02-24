# 🚀 БЫСТРЫЙ СТАРТ ДЕПЛОЯ

## ✅ ЧТО УЖЕ ГОТОВО:

1. ✅ **Оптимальный портфель** обновлен в `config.py`:
   - AVAXUSDT, LINKUSDT, SOLUSDT, SUIUSDT, DOGEUSDT
2. ✅ **Динамическое плечо** интегрировано и работает

3. ✅ **Индивидуальные параметры** настроены для всех монет

4. ✅ **Бэктесты подтвердили** отличные результаты:
   - Win Rate: 56.84%
   - Profit Factor: 1.37
   - PnL: +54.69% за 30 дней

---

## 🔧 КОМАНДЫ ДЛЯ РУЧНОГО ДЕПЛОЯ:

### 1. Подключение к серверу:

```bash
ssh root@185.177.216.15
# Пароль: u44Ww9NmtQj,XG
```

### 2. Переход в директорию проекта:

```bash
cd /root/atra  # или ваш путь к проекту
```

### 3. Создание бэкапа:

```bash
cp -r /root/atra /root/atra.backup.$(date +%Y%m%d_%H%M%S)
```

### 4. Остановка текущего процесса:

```bash
# Найти PID
ps aux | grep "python.*main.py" | grep -v grep

# Остановить (замените <PID> на реальный)
kill -SIGTERM <PID>

# Подождать 5 секунд
sleep 5

# Если не остановился, принудительно
kill -9 <PID> 2>/dev/null || true
```

### 5. Обновление файлов (выберите один способ):

#### Способ A: Через git (если используется)

```bash
git pull origin main
```

#### Способ B: Через rsync с локальной машины

```bash
# На ЛОКАЛЬНОЙ машине выполните:
rsync -avz --progress \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.env' \
    ./ root@185.177.216.15:/root/atra/
```

#### Способ C: Вручную скопировать ключевые файлы

```bash
# На сервере обновите:
# - config.py (COINS обновлен)
# - src/core/config.py (SYMBOL_SPECIFIC_CONFIG)
```

### 6. Проверка конфигурации:

```bash
# Проверить env файл
cat env | grep -E "ATRA_ENV|TELEGRAM_TOKEN"

# Убедиться, что ATRA_ENV=prod
# Если нет, обновить:
sed -i 's/^ATRA_ENV=.*/ATRA_ENV=prod/' env

# Проверить список монет
python3 -c "from config import COINS; print('COINS:', COINS)"
```

### 7. Запуск системы:

```bash
# Активировать виртуальное окружение (если используется)
source venv/bin/activate  # если есть venv

# Создать директорию для логов
mkdir -p logs

# Запустить в фоне
nohup python3 main.py > logs/atra.log 2>&1 &

# Проверить, что запустилось
ps aux | grep "python.*main.py" | grep -v grep
```

### 8. Проверка работы:

```bash
# Смотреть логи в реальном времени
tail -f logs/atra.log

# Проверить последние 100 строк
tail -100 logs/atra.log

# Проверить ошибки
tail -200 logs/atra.log | grep -i error

# Проверить успешный запуск
tail -100 logs/atra.log | grep -E "✅|🚀|запущен|started|COINS"
```

---

## 📊 ЧТО ПРОВЕРИТЬ ПОСЛЕ ЗАПУСКА:

### 1. Система запущена:

```bash
ps aux | grep "python.*main.py" | grep -v grep
# Должен быть процесс
```

### 2. Telegram бот работает:

- Отправьте команду `/start` боту
- Проверьте ответ

### 3. Генерация сигналов:

```bash
# Проверить последние сигналы
tail -200 logs/atra.log | grep -E "сигнал|signal|SIGNAL"

# Проверить использование оптимального портфеля
tail -200 logs/atra.log | grep -E "AVAXUSDT|LINKUSDT|SOLUSDT|SUIUSDT|DOGEUSDT"
```

### 4. Динамическое плечо:

```bash
tail -200 logs/atra.log | grep -E "DYNAMIC_LEVERAGE|динамическое плечо|leverage"
```

### 5. База данных:

```bash
# Проверить последние сигналы в БД
sqlite3 trading.db "SELECT symbol, side, created_at FROM signals ORDER BY created_at DESC LIMIT 10;"
```

---

## ⚠️ ВОЗМОЖНЫЕ ПРОБЛЕМЫ:

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

## 📈 МОНИТОРИНГ ПЕРВЫЕ 24 ЧАСА:

1. **Количество сигналов** - должно быть несколько в день
2. **Распределение по монетам** - все 5 монет портфеля
3. **Использование динамического плеча** - 2.0x, 2.5x, 3.0x
4. **Ошибки в логах** - минимизировать

---

## 🎯 ОЖИДАЕМЫЕ РЕЗУЛЬТАТЫ:

На основе бэктестов:

- **Win Rate:** ~57%
- **Profit Factor:** ~1.37
- **Среднее плечо:** ~2.24x
- **Максимальная просадка:** ~4.43%

---

**Готово к запуску!** 🚀
