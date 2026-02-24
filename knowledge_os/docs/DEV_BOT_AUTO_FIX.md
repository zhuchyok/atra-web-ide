# 🛡️ ИСПРАВЛЕНИЕ: DEV бот открывает позиции автоматически

## 🔴 ПРОБЛЕМА

Сигналы приходят в DEV бот (@piu_piu_dev_bot, токен `8141444679`), но позиции открываются автоматически на бирже. DEV бот должен работать **только в manual режиме**.

## ✅ ЧТО СДЕЛАНО

### 1. Добавлена двойная защита:

**`signal_live.py` (строка 4220):**

```python
if ATRA_ENV != "prod":
    logger.info("⏭️ [AUTO] %s: окружение=%s, авто-исполнение отключено", symbol, ATRA_ENV)
    return
```

**`auto_execution.py` (строка 52):**

```python
if ATRA_ENV != "prod":
    logger.error("🚫 [AUTO BLOCKED] %s: АВТО-ИСПОЛНЕНИЕ ЗАБЛОКИРОВАНО! Окружение=%s", symbol, ATRA_ENV)
    return False
```

### 2. Логирование окружения

Теперь в логах видно, какое окружение используется при попытке авто-исполнения.

## 📋 ИНСТРУКЦИИ ДЛЯ СЕРВЕРА

### Шаг 1: Проверить конфигурацию DEV бота

```bash
cd /root/atra
echo "=== ПРОВЕРКА DEV БОТА ==="
echo ""
echo "1. Проверяем ATRA_ENV:"
grep "^ATRA_ENV" env
echo ""
echo "2. Проверяем токен:"
grep "^TELEGRAM_TOKEN_DEV" env
echo ""
echo "3. Проверяем процессы:"
ps aux | grep "python.*main" | grep -v grep
```

### Шаг 2: Исправить ATRA_ENV для DEV бота

**Если `ATRA_ENV=prod` для DEV бота, нужно изменить:**

```bash
cd /root/atra
# Создаем резервную копию
cp env env.backup

# Меняем ATRA_ENV на dev
sed -i 's/^ATRA_ENV=.*/ATRA_ENV=dev/' env

# Проверяем
grep "^ATRA_ENV" env
```

### Шаг 3: Обновить код на сервере

```bash
cd /root/atra
git pull origin main  # или master, в зависимости от ветки
```

### Шаг 4: Перезапустить DEV бот

```bash
# Остановить DEV бот
pkill -f "python.*main"  # или systemctl stop atra-dev (если есть сервис)

# Подождать 5 секунд
sleep 5

# Запустить DEV бот
cd /root/atra
nohup python3 main.py > logs/dev_bot.log 2>&1 &
```

### Шаг 5: Проверить работу

```bash
# Проверить логи
tail -f logs/dev_bot.log | grep -E "AUTO|ATRA_ENV|BLOCKED"

# Проверить процессы
ps aux | grep "python.*main" | grep -v grep
```

## 🧪 ТЕСТИРОВАНИЕ

После перезапуска:

1. **Отправить тестовый сигнал** в DEV бот
2. **Проверить логи** - должно быть:
   ```
   🚫 [AUTO BLOCKED] SYMBOL: АВТО-ИСПОЛНЕНИЕ ЗАБЛОКИРОВАНО! Окружение=dev
   ```
3. **Проверить биржу** - позиция НЕ должна открыться автоматически
4. **Проверить manual режим** - команда `/accept` должна работать

## ⚠️ ВАЖНО

- **DEV бот** должен иметь `ATRA_ENV=dev` в файле `env`
- **PROD бот** должен иметь `ATRA_ENV=prod` в файле `env`
- Если на сервере запущены оба бота, у каждого должен быть свой `env` файл или своя директория

## 📊 ПРОВЕРКА УСПЕШНОСТИ

После исправления:

✅ Сигналы приходят в DEV бот  
✅ Позиции НЕ открываются автоматически  
✅ В логах видно `🚫 [AUTO BLOCKED]`  
✅ Manual режим работает (`/accept` открывает позицию)

## 🔍 ДИАГНОСТИКА

Если проблема сохраняется:

1. Проверить, какой `ATRA_ENV` читает бот:

   ```bash
   cd /root/atra
   python3 -c "import os; from dotenv import load_dotenv; load_dotenv('env'); print('ATRA_ENV:', os.getenv('ATRA_ENV'))"
   ```

2. Проверить логи при генерации сигнала:

   ```bash
   tail -100 logs/dev_bot.log | grep -E "AUTO CHECK|ATRA_ENV|BLOCKED"
   ```

3. Проверить, что код обновлен:
   ```bash
   cd /root/atra
   git log --oneline -5
   grep -A 5 "КРИТИЧЕСКАЯ ПРОВЕРКА" auto_execution.py
   ```
