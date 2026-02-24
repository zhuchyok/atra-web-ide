# 🔍 ДИАГНОСТИКА: Почему нет сигналов в PROD боте (@PiuX_Trade_bot)

## 📊 ТЕКУЩАЯ СИТУАЦИЯ

- **PROD бот**: @PiuX_Trade_bot (токен `8156844481`)
- **DEV бот**: @piu_piu_dev_bot (токен `8141444679`)
- **Проблема**: Сигналы не приходят в PROD бот

## 🔍 ЛОГИКА ОПРЕДЕЛЕНИЯ ТОКЕНА

В `config.py` (строки 166-173):

```python
ATRA_ENV = os.getenv("ATRA_ENV", "dev").lower().strip()
TOKEN = (
    TELEGRAM_TOKEN if ATRA_ENV == "prod" else (
        TELEGRAM_TOKEN_DEV or TELEGRAM_TOKEN
    )
)
```

**Критично**: Если `ATRA_ENV != "prod"`, используется DEV токен!

## ⚠️ ВОЗМОЖНЫЕ ПРИЧИНЫ

### 1. Неправильный ATRA_ENV на сервере для PROD бота

**Проблема**: Если на сервере для PROD бота установлен `ATRA_ENV=dev`, то:

- Будет использоваться DEV токен (`8141444679`)
- Сигналы пойдут в DEV бот (@piu_piu_dev_bot)
- PROD бот не получит сигналы

**Проверка на сервере**:

```bash
cd /root/atra
echo "=== ПРОВЕРКА PROD БОТА ==="
echo ""
echo "1. Проверяем ATRA_ENV:"
grep "^ATRA_ENV" env
echo ""
echo "2. Проверяем токен PROD:"
grep "^TELEGRAM_TOKEN=" env | head -1
echo ""
echo "3. Проверяем процессы:"
ps aux | grep "python.*main" | grep -v grep
```

**Исправление**:

```bash
cd /root/atra
# Создаем резервную копию
cp env env.backup

# Устанавливаем ATRA_ENV=prod для PROD бота
sed -i 's/^ATRA_ENV=.*/ATRA_ENV=prod/' env

# Проверяем
grep "^ATRA_ENV" env
```

### 2. PROD бот не запущен на сервере

**Проверка**:

```bash
# Проверяем процессы
ps aux | grep "python.*main" | grep -v grep

# Проверяем логи
tail -50 logs/*.log | grep -i "telegram\|bot\|start"
```

**Запуск PROD бота**:

```bash
cd /root/atra
# Убедитесь, что ATRA_ENV=prod в env файле
nohup python3 main.py > logs/prod_bot.log 2>&1 &
```

### 3. Сигналы генерируются, но отправляются в DEV бот

**Проверка логов**:

```bash
# Проверяем, какие сигналы генерируются
tail -100 logs/*.log | grep -E "сигнал|SIGNAL|notify_user" | tail -20

# Проверяем, какой токен используется
grep -E "TOKEN|ATRA_ENV" logs/*.log | tail -10
```

**Диагностика**:

```bash
cd /root/atra
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv('env')

print('=== ДИАГНОСТИКА ===')
print(f'ATRA_ENV: {os.getenv(\"ATRA_ENV\")}')
print(f'TELEGRAM_TOKEN (первые 20 символов): {os.getenv(\"TELEGRAM_TOKEN\", \"не установлен\")[:20]}...')
print(f'TELEGRAM_TOKEN_DEV (первые 20 символов): {os.getenv(\"TELEGRAM_TOKEN_DEV\", \"не установлен\")[:20]}...')

# Проверяем, какой токен будет использован
from config import TOKEN, ATRA_ENV
print(f'')
print(f'Используемый TOKEN (первые 20 символов): {TOKEN[:20] if TOKEN else \"не установлен\"}...')
print(f'ATRA_ENV из config: {ATRA_ENV}')
"
```

### 4. Сигналы не генерируются вообще (фильтры блокируют)

**Проверка генерации сигналов**:

```bash
# Проверяем логи генерации
tail -200 logs/*.log | grep -E "сигнал|SIGNAL|generate|блок|block" | tail -30

# Проверяем активность системы
tail -100 logs/*.log | grep -E "check_and_send|_generate_signal" | tail -20
```

## 🔧 ПОШАГОВОЕ ИСПРАВЛЕНИЕ

### Шаг 1: Проверить конфигурацию на сервере

```bash
cd /root/atra
echo "=== ДИАГНОСТИКА ==="
echo ""
echo "1. ATRA_ENV:"
grep "^ATRA_ENV" env
echo ""
echo "2. Токены:"
grep "^TELEGRAM_TOKEN" env
echo ""
echo "3. Процессы:"
ps aux | grep "python.*main" | grep -v grep
```

### Шаг 2: Исправить ATRA_ENV для PROD бота

```bash
cd /root/atra
# Устанавливаем ATRA_ENV=prod
sed -i 's/^ATRA_ENV=.*/ATRA_ENV=prod/' env

# Проверяем
grep "^ATRA_ENV" env
```

### Шаг 3: Обновить код (если нужно)

```bash
cd /root/atra
git pull origin main  # или master
```

### Шаг 4: Перезапустить PROD бот

```bash
# Остановить старый процесс
pkill -f "python.*main"

# Подождать 5 секунд
sleep 5

# Запустить PROD бот
cd /root/atra
nohup python3 main.py > logs/prod_bot.log 2>&1 &

# Проверить запуск
sleep 3
ps aux | grep "python.*main" | grep -v grep
tail -20 logs/prod_bot.log
```

### Шаг 5: Проверить работу

```bash
# Проверяем логи
tail -f logs/prod_bot.log | grep -E "сигнал|SIGNAL|notify_user|ATRA_ENV"

# Проверяем, что используется правильный токен
grep "TOKEN\|ATRA_ENV" logs/prod_bot.log | head -10
```

## 📋 ЧЕКЛИСТ ПРОВЕРКИ

- [ ] `ATRA_ENV=prod` в файле `env` на сервере
- [ ] `TELEGRAM_TOKEN` установлен (токен PROD бота `8156844481`)
- [ ] PROD бот запущен на сервере
- [ ] В логах видно использование PROD токена
- [ ] Сигналы генерируются (проверить логи)
- [ ] Сигналы отправляются в PROD бот (проверить Telegram)

## 🧪 ТЕСТИРОВАНИЕ

После исправления:

1. **Проверить логи** - должно быть:

   ```
   ATRA_ENV: prod
   Используемый TOKEN: 8156844481...
   ```

2. **Дождаться сигнала** или проверить историю:

   ```bash
   tail -100 logs/prod_bot.log | grep "сигнал\|SIGNAL"
   ```

3. **Проверить Telegram** - сигналы должны приходить в @PiuX_Trade_bot

## ⚠️ ВАЖНО

- **PROD бот** должен иметь `ATRA_ENV=prod` в файле `env`
- **DEV бот** должен иметь `ATRA_ENV=dev` в файле `env`
- Если на сервере запущены оба бота, у каждого должен быть свой `env` файл или своя директория

## 🔍 ДОПОЛНИТЕЛЬНАЯ ДИАГНОСТИКА

Если проблема сохраняется:

1. **Проверить, генерируются ли сигналы**:

   ```bash
   tail -500 logs/*.log | grep -E "check_and_send|_generate_signal" | tail -50
   ```

2. **Проверить фильтры**:

   ```bash
   tail -500 logs/*.log | grep -E "блок|block|фильтр|filter" | tail -50
   ```

3. **Проверить подключение к Telegram API**:
   ```bash
   tail -100 logs/*.log | grep -E "Telegram\|API\|error\|Error" | tail -20
   ```
