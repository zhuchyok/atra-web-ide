# 🚀 Развертывание ATRA на сервере

## ✅ Совместимость

ATRA протестирован и готов к работе на:
- **Linux** (Ubuntu, CentOS, Debian)
- **macOS** (локальная разработка)
- **Python 3.8+**
- **systemd** (Linux серверы)

## 📋 Требования к серверу

### Минимальные требования:
- **CPU**: 2 ядра
- **RAM**: 4 GB
- **Диск**: 20 GB свободного места
- **Python**: 3.8 или выше
- **ОС**: Linux с systemd

### Рекомендуемые требования:
- **CPU**: 4+ ядер
- **RAM**: 8+ GB
- **Диск**: 50+ GB SSD
- **Сеть**: стабильное интернет-соединение

## 🔧 Установка на сервере

### 1. Автоматическая установка (рекомендуется)

```bash
# Загрузите проект на сервер
git clone <your-repo-url> /root/atra
cd /root/atra

# Запустите автоматическую установку
sudo ./install_on_server.sh
```

### 2. Ручная установка

```bash
# 1. Установите зависимости
sudo apt update
sudo apt install python3 python3-pip python3-venv

# 2. Установите Python пакеты
pip3 install pandas numpy requests aiohttp python-telegram-bot ccxt yfinance

# 3. Установите talib (для Linux)
sudo apt install build-essential
pip3 install TA-Lib

# 4. Скопируйте файлы
sudo cp -r . /root/atra/
sudo chown -R root:root /root/atra

# 5. Установите systemd service
sudo cp atra.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable atra
```

## 🚀 Запуск и управление

### Основные команды:

```bash
# Запуск
sudo systemctl start atra

# Остановка
sudo systemctl stop atra

# Перезапуск
sudo systemctl restart atra

# Статус
sudo systemctl status atra

# Автозапуск при загрузке
sudo systemctl enable atra
```

### Полезные команды:

```bash
# Быстрый перезапуск
restart_atra

# Проверка статуса
status_atra

# Просмотр логов в реальном времени
journalctl -u atra -f

# Просмотр последних логов
journalctl -u atra --no-pager -n 50
```

## 📊 Мониторинг

### Проверка работы:

```bash
# Процессы
ps aux | grep "python3 main.py"

# Порт 8080 (REST API)
netstat -tlnp | grep 8080

# Порт 5002 (Web Dashboard)
netstat -tlnp | grep 5002

# Логи системы
journalctl -u atra --since "1 hour ago"
```

### Веб-интерфейсы:

- **REST API**: http://your-server:8080
- **Web Dashboard**: http://your-server:5002

## 🔧 Конфигурация

### Основные настройки в `config.py`:

```python
# Токен Telegram бота
TOKEN = "your-bot-token"

# Окружение (prod/dev)
ATRA_ENV = "prod"

# Настройки базы данных
DATABASE_URL = "sqlite:///atra.db"
```

### Переменные окружения:

```bash
# В /etc/systemd/system/atra.service
Environment=ATRA_ENV=prod
Environment=PYTHONPATH=/root/atra
Environment=PYTHONUNBUFFERED=1
```

## 🛠️ Устранение неполадок

### Проблемы с talib:

```bash
# Проверка talib
python3 -c "from talib_wrapper import get_talib; print('talib:', get_talib() is not None)"

# Переустановка talib
pip3 uninstall TA-Lib
pip3 install TA-Lib
```

### Проблемы с зависимостями:

```bash
# Проверка зависимостей
python3 server_compatibility_check.py

# Установка недостающих пакетов
pip3 install pandas numpy requests aiohttp python-telegram-bot ccxt yfinance
```

### Проблемы с правами доступа:

```bash
# Исправление прав
sudo chown -R root:root /root/atra
sudo chmod +x /root/atra/main.py
```

## 📈 Производительность

### Оптимизация для сервера:

1. **Увеличьте лимиты в systemd**:
```ini
# В atra.service
MemoryLimit=8G
CPUQuota=800%
```

2. **Настройте логирование**:
```bash
# Ротация логов
sudo logrotate -f /etc/logrotate.d/atra
```

3. **Мониторинг ресурсов**:
```bash
# Использование памяти
free -h

# Использование CPU
top -p $(pgrep -f "python3 main.py")

# Использование диска
df -h
```

## 🔒 Безопасность

### Рекомендации:

1. **Firewall**:
```bash
# Откройте только необходимые порты
sudo ufw allow 22    # SSH
sudo ufw allow 8080 # REST API
sudo ufw allow 5002  # Web Dashboard
```

2. **SSL/TLS** (опционально):
```bash
# Используйте nginx как reverse proxy
sudo apt install nginx
# Настройте SSL сертификаты
```

3. **Резервное копирование**:
```bash
# Автоматическое резервное копирование
crontab -e
# Добавьте: 0 2 * * * tar -czf /backup/atra-$(date +\%Y\%m\%d).tar.gz /root/atra
```

## 📞 Поддержка

При возникновении проблем:

1. Проверьте логи: `journalctl -u atra -f`
2. Запустите проверку совместимости: `python3 server_compatibility_check.py`
3. Проверьте статус: `status_atra`

---

**🎉 ATRA готов к работе на сервере!**
