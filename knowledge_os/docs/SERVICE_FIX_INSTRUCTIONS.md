# Исправление проблемы с systemd сервисом

## 🎯 Проблема

Сервис `myproject.service` не найден и был убит с `SIGKILL` из-за таймаута:

```
Loaded: not-found (Reason: Unit myproject.service not found.)
Active: failed (Result: timeout)
Main PID: 1755 (code=killed, signal=KILL)
```

## 🚀 Быстрое решение

### 1. Запустите скрипт установки на сервере:

```bash
# Перейдите в директорию проекта
cd /root/atra

# Запустите скрипт установки
sudo ./install_service.sh
```

### 2. Если скрипт не работает, выполните вручную:

```bash
# 1. Скопируйте сервис в systemd
sudo cp myproject.service /etc/systemd/system/

# 2. Перезагрузите systemd
sudo systemctl daemon-reload

# 3. Включите сервис
sudo systemctl enable myproject.service

# 4. Запустите сервис
sudo systemctl start myproject.service

# 5. Проверьте статус
sudo systemctl status myproject.service
```

## 🔍 Диагностика проблем

### Проверьте статус сервиса:

```bash
sudo systemctl status myproject.service
```

**Ожидаемый результат:**

```
● myproject.service - Trading bot ATRA
   Active: active (running)
   Main PID: 1234 (python)
```

### Проверьте логи:

```bash
journalctl -u myproject.service -f
```

**Ищите ошибки:**

- `❌ Ошибка импорта модулей`
- `❌ Ошибка токена бота`
- `❌ Ошибка базы данных`
- `❌ Ошибка виртуального окружения`

### Проверьте конфигурацию:

```bash
# Проверьте файл сервиса
cat /etc/systemd/system/myproject.service

# Проверьте пути
ls -la /root/atra/main.py
ls -la /root/atra/.venv/bin/python
```

## 🛠️ Частые проблемы и решения

### 1. Сервис не запускается

**Проблема:** `systemctl status myproject.service` показывает `inactive`

**Решение:**

```bash
# Проверьте логи
journalctl -u myproject.service -n 20

# Перезапустите сервис
sudo systemctl restart myproject.service
```

### 2. Ошибка виртуального окружения

**Проблема:** `❌ Ошибка виртуального окружения`

**Решение:**

```bash
# Создайте виртуальное окружение
cd /root/atra
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Ошибка токена бота

**Проблема:** `❌ Ошибка токена бота`

**Решение:**

```bash
# Проверьте .env файл
cat .env

# Обновите токен если нужно
nano .env
```

### 4. Ошибка прав доступа

**Проблема:** `❌ Permission denied`

**Решение:**

```bash
# Установите правильные права
sudo chown -R root:root /root/atra
sudo chmod +x /root/atra/main.py
sudo chmod +x /root/atra/.venv/bin/python
```

## 📊 Проверка работы

### 1. Проверьте, что сервис активен:

```bash
sudo systemctl is-active myproject.service
```

**Ожидаемый результат:** `active`

### 2. Проверьте логи:

```bash
journalctl -u myproject.service -f
```

**Ищите сообщения:**

- `✅ Бот запущен`
- `✅ Обработчики зарегистрированы`
- `✅ Команды зарегистрированы`

### 3. Проверьте Telegram бота:

Отправьте команду `/start` боту в Telegram.

**Ожидаемый результат:**

- Бот должен ответить приветственным сообщением
- Должны появиться кнопки меню

## 🚨 Критические ошибки

### Если сервис все еще не работает:

1. **Проверьте файл сервиса:**

   ```bash
   cat /etc/systemd/system/myproject.service
   ```

2. **Проверьте пути:**

   ```bash
   ls -la /root/atra/main.py
   ls -la /root/atra/.venv/bin/python
   ```

3. **Проверьте логи:**

   ```bash
   journalctl -u myproject.service -n 50
   ```

4. **Пересоздайте сервис:**
   ```bash
   sudo systemctl stop myproject.service
   sudo systemctl disable myproject.service
   sudo rm /etc/systemd/system/myproject.service
   sudo systemctl daemon-reload
   sudo ./install_service.sh
   ```

## 📋 Чек-лист для сервера

- [ ] Сервис скопирован в `/etc/systemd/system/`
- [ ] systemd перезагружен (`systemctl daemon-reload`)
- [ ] Сервис включен (`systemctl enable myproject.service`)
- [ ] Сервис запущен (`systemctl start myproject.service`)
- [ ] Сервис активен (`systemctl is-active myproject.service`)
- [ ] Нет ошибок в логах (`journalctl -u myproject.service`)
- [ ] Виртуальное окружение работает
- [ ] Токен бота валиден
- [ ] Бот отвечает на команды

## 📅 Дата создания

6 октября 2025

## ✅ Статус

- ✅ systemd сервис создан
- ✅ Скрипт установки создан
- ✅ Инструкции созданы
- ⏳ Требуется установка на сервере
