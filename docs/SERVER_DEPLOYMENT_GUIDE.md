# 🚀 РУКОВОДСТВО ПО РАЗВЕРТЫВАНИЮ НА СЕРВЕРЕ

## 🔧 **РЕШЕНИЕ ПРОБЛЕМЫ С GIT**

### **1. Исправление незавершенного слияния:**

```bash
# Отменить текущее слияние
git merge --abort

# Или принудительно сбросить изменения
git reset --hard HEAD

# Очистить рабочую директорию
git clean -fd
```

### **2. Обновление кода:**

```bash
# Получить последние изменения
git pull origin worker

# Если есть конфликты, принудительно обновить
git fetch origin
git reset --hard origin/worker
```

## 🚀 **РАЗВЕРТЫВАНИЕ НОВОЙ СИСТЕМЫ УПРАВЛЕНИЯ**

### **1. Проверка файлов:**

```bash
# Убедиться, что новые файлы есть
ls -la server_manager.py
ls -la atra_server.sh
ls -la server_config.json
```

### **2. Настройка прав:**

```bash
# Сделать скрипт исполняемым
chmod +x atra_server.sh

# Проверить Python
python3 --version
```

### **3. Остановка старых процессов:**

```bash
# Остановить все процессы ATRA
pkill -f "main.py"
pkill -f "system_monitor"
pkill -f "monitor_bot"
pkill -f "auto_restart"

# Удалить файлы блокировки
rm -f atra.lock bot_restart_signal.txt
```

### **4. Запуск новой системы:**

```bash
# Запустить через новую систему управления
./atra_server.sh start

# Проверить статус
./atra_server.sh status
```

## ⚙️ **КОНФИГУРАЦИЯ ДЛЯ СЕРВЕРА**

### **Минимальная конфигурация (рекомендуется):**

```bash
# Отключить конфликтующие мониторы
./atra_server.sh disable monitoring
./atra_server.sh disable auto_restart
./atra_server.sh disable rest_api
./atra_server.sh disable web_dashboard

# Запустить только основную систему
./atra_server.sh start
```

### **С автоперезапуском (для нестабильных серверов):**

```bash
# Включить автоперезапуск
./atra_server.sh enable auto_restart
./atra_server.sh start
```

### **Полная конфигурация (для продвинутых пользователей):**

```bash
# Включить все компоненты
./atra_server.sh enable monitoring
./atra_server.sh enable rest_api
./atra_server.sh enable web_dashboard
./atra_server.sh start
```

## 🔄 **АВТОМАТИЧЕСКИЙ ЗАПУСК ПРИ ПЕРЕЗАГРУЗКЕ**

### **1. Создание systemd сервиса:**

```bash
# Создать файл сервиса
sudo nano /etc/systemd/system/atra.service
```

### **2. Содержимое сервиса:**

```ini
[Unit]
Description=ATRA Trading System
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/atra
ExecStart=/root/atra/atra_server.sh start
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### **3. Активация сервиса:**

```bash
# Перезагрузить systemd
sudo systemctl daemon-reload

# Включить автозапуск
sudo systemctl enable atra.service

# Запустить сервис
sudo systemctl start atra.service

# Проверить статус
sudo systemctl status atra.service
```

## 📊 **МОНИТОРИНГ СИСТЕМЫ**

### **Проверка статуса:**

```bash
# Статус системы управления
./atra_server.sh status

# Статус systemd сервиса
sudo systemctl status atra.service

# Логи системы
tail -f logs/system.log.1
```

### **Управление сервисом:**

```bash
# Остановить
sudo systemctl stop atra.service

# Запустить
sudo systemctl start atra.service

# Перезапустить
sudo systemctl restart atra.service
```

## 🚨 **РЕШЕНИЕ ПРОБЛЕМ**

### **Проблема: Git конфликты**

```bash
git merge --abort
git reset --hard HEAD
git pull origin worker
```

### **Проблема: Система не запускается**

```bash
# Проверить зависимости
python3 -c "import asyncio, aiohttp, telegram"

# Проверить права
chmod +x atra_server.sh

# Проверить конфигурацию
cat server_config.json
```

### **Проблема: Постоянные перезапуски**

```bash
# Отключить конфликтующие мониторы
./atra_server.sh disable monitoring
./atra_server.sh disable auto_restart
./atra_server.sh restart
```

## 📋 **ЧЕКЛИСТ РАЗВЕРТЫВАНИЯ**

- [ ] Исправлен Git конфликт
- [ ] Обновлен код с GitHub
- [ ] Остановлены старые процессы
- [ ] Настроены права на файлы
- [ ] Протестирован запуск через новую систему
- [ ] Настроена конфигурация для сервера
- [ ] Создан systemd сервис (опционально)
- [ ] Протестирован автозапуск

## 🎯 **РЕКОМЕНДАЦИИ**

### **Для стабильной работы:**

- Используйте минимальную конфигурацию
- Отключите все мониторы
- Настройте systemd сервис

### **Для мониторинга:**

- Включите только один тип мониторинга
- Не используйте одновременно `monitoring` и `auto_restart`

### **Для разработки:**

- Включите `monitoring` для отслеживания
- Используйте `./atra_server.sh status` для проверки
