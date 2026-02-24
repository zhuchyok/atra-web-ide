# 🔧 Исправление: Почему сигналы не идут в PROD

## ❌ Проблема

Сигналы идут в **DEV**, но не идут в **PROD**.

## 🔍 Причина

На сервере (prod) не установлена переменная окружения `ATRA_ENV=prod`, поэтому система использует DEV токен вместо PROD токена.

## ✅ Решение

### 1. Проверка текущего окружения на сервере

Подключитесь к серверу и проверьте:

```bash
ssh root@185.177.216.15
cd /path/to/atra
cat env | grep ATRA_ENV
```

### 2. Установка PROD окружения

**Вариант 1: В файле env (рекомендуется)**

```bash
# На сервере
cd /path/to/atra
nano env
# Измените строку:
ATRA_ENV=prod
# Сохраните (Ctrl+O, Enter, Ctrl+X)
```

**Вариант 2: Через export**

```bash
# На сервере
export ATRA_ENV=prod
# Добавьте в ~/.bashrc для постоянства:
echo 'export ATRA_ENV=prod' >> ~/.bashrc
```

### 3. Проверка токенов

Убедитесь, что в файле `env` на сервере установлены:

```bash
# PROD токен (основной)
TELEGRAM_TOKEN=PROD_TOKEN_REDACTED

# DEV токен (для разработки)
TELEGRAM_TOKEN_DEV=DEV_TOKEN_REDACTED

# Chat IDs (ваши ID)
TELEGRAM_CHAT_IDS=556251171,958930260
```

### 4. Проверка конфигурации

Запустите скрипт проверки на сервере:

```bash
cd /path/to/atra
python3 scripts/check_environment.py
```

Должно показать:

```
📊 Окружение: PROD
   ✅ PROD режим - используется TELEGRAM_TOKEN
🎯 Активный токен: TELEGRAM_TOKEN (PROD)
```

### 5. Перезапуск системы

После изменения `ATRA_ENV` перезапустите систему:

```bash
# Остановите текущий процесс
systemctl stop atra  # или ваш способ остановки

# Запустите заново
systemctl start atra  # или ваш способ запуска

# Проверьте статус
systemctl status atra
```

## 📊 Логика выбора токена

В `config.py`:

```python
ATRA_ENV = os.getenv("ATRA_ENV", "dev").lower().strip()

# prod -> TELEGRAM_TOKEN, иначе -> TELEGRAM_TOKEN_DEV
TOKEN = (
    TELEGRAM_TOKEN if ATRA_ENV == "prod" else (
        TELEGRAM_TOKEN_DEV or TELEGRAM_TOKEN
    )
)
```

**Логика:**

- Если `ATRA_ENV=prod` → используется `TELEGRAM_TOKEN` (PROD токен)
- Если `ATRA_ENV=dev` или не установлен → используется `TELEGRAM_TOKEN_DEV` (DEV токен)

## 🔍 Диагностика

### Проверка на сервере:

1. **Проверьте переменную окружения:**

   ```bash
   echo $ATRA_ENV
   # Должно быть: prod
   ```

2. **Проверьте файл env:**

   ```bash
   grep ATRA_ENV env
   # Должно быть: ATRA_ENV=prod
   ```

3. **Проверьте токены:**

   ```bash
   grep TELEGRAM_TOKEN env
   # Должны быть оба токена
   ```

4. **Проверьте логи:**

   ```bash
   tail -f logs/system.log | grep -i "telegram\|signal\|token"
   ```

5. **Запустите скрипт проверки:**
   ```bash
   python3 scripts/check_environment.py
   ```

## ✅ Быстрое исправление

**На сервере выполните:**

```bash
# 1. Перейдите в директорию проекта
cd /path/to/atra

# 2. Установите PROD окружение в env файле
sed -i 's/ATRA_ENV=dev/ATRA_ENV=prod/' env

# 3. Проверьте изменение
grep ATRA_ENV env

# 4. Перезапустите систему
systemctl restart atra  # или ваш способ перезапуска

# 5. Проверьте логи
tail -f logs/system.log
```

## 🎯 Итог

**Проблема:** На сервере `ATRA_ENV=dev` вместо `ATRA_ENV=prod`

**Решение:** Установите `ATRA_ENV=prod` в файле `env` на сервере и перезапустите систему.

**Проверка:** Запустите `python3 scripts/check_environment.py` - должно показать `Окружение: PROD`

---

**Версия:** 1.0  
**Дата:** 2025-11-13  
**Автор:** ATRA Team
