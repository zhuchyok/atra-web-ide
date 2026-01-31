Развертывание
=============

Руководство по развертыванию торгового бота ATRA в продакшене.

Требования к серверу
-------------------

### Минимальные требования

* **CPU:** 2 ядра
* **RAM:** 4 GB
* **Диск:** 20 GB SSD
* **ОС:** Ubuntu 20.04+ / CentOS 8+ / Debian 11+

### Рекомендуемые требования

* **CPU:** 4+ ядер
* **RAM:** 8+ GB
* **Диск:** 50+ GB SSD
* **ОС:** Ubuntu 22.04 LTS

### Сетевые требования

* Стабильное интернет-соединение
* Доступ к API бирж (Binance, CoinGecko)
* Доступ к Telegram API

Установка на сервере
--------------------

### 1. Подготовка системы

.. code-block:: bash

   # Обновление системы
   sudo apt update && sudo apt upgrade -y
   
   # Установка Python 3.9+
   sudo apt install python3.9 python3.9-pip python3.9-venv -y
   
   # Установка Git
   sudo apt install git -y

### 2. Создание пользователя

.. code-block:: bash

   # Создание пользователя для бота
   sudo useradd -m -s /bin/bash atra
   sudo usermod -aG sudo atra
   
   # Переключение на пользователя
   sudo su - atra

### 3. Клонирование репозитория

.. code-block:: bash

   # Клонирование проекта
   git clone https://github.com/your-repo/atra.git
   cd atra
   
   # Создание виртуального окружения
   python3.9 -m venv venv
   source venv/bin/activate
   
   # Установка зависимостей
   pip install -r requirements.txt

### 4. Настройка конфигурации

.. code-block:: bash

   # Создание файла конфигурации
   cp .env.example .env
   nano .env
   
   # Настройка переменных окружения
   export TELEGRAM_BOT_TOKEN="your_bot_token"
   export DATABASE_URL="sqlite:///atra.db"
   export LOG_LEVEL="INFO"

Docker развертывание
--------------------

### 1. Создание Dockerfile

.. code-block:: dockerfile

   FROM python:3.9-slim
   
   WORKDIR /app
   
   # Установка системных зависимостей
   RUN apt-get update && apt-get install -y \
       gcc \
       g++ \
       && rm -rf /var/lib/apt/lists/*
   
   # Копирование файлов
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   
   COPY . .
   
   # Создание пользователя
   RUN useradd -m -u 1000 atra
   USER atra
   
   # Запуск приложения
   CMD ["python", "main.py"]

### 2. Docker Compose

.. code-block:: yaml

   version: '3.8'
   
   services:
     atra:
       build: .
       container_name: atra-bot
       restart: unless-stopped
       environment:
         - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
         - DATABASE_URL=sqlite:///data/atra.db
         - LOG_LEVEL=INFO
       volumes:
         - ./data:/app/data
         - ./logs:/app/logs
       networks:
         - atra-network
   
     nginx:
       image: nginx:alpine
       container_name: atra-nginx
       restart: unless-stopped
       ports:
         - "80:80"
         - "443:443"
       volumes:
         - ./nginx.conf:/etc/nginx/nginx.conf
       networks:
         - atra-network
   
   networks:
     atra-network:
       driver: bridge

### 3. Запуск с Docker

.. code-block:: bash

   # Сборка и запуск
   docker-compose up -d
   
   # Просмотр логов
   docker-compose logs -f atra
   
   # Остановка
   docker-compose down

Systemd сервис
--------------

### 1. Создание сервиса

Создайте файл `/etc/systemd/system/atra.service`:

.. code-block:: ini

   [Unit]
   Description=ATRA Trading Bot
   After=network.target
   
   [Service]
   Type=simple
   User=atra
   Group=atra
   WorkingDirectory=/home/atra/atra
   Environment=PATH=/home/atra/atra/venv/bin
   ExecStart=/home/atra/atra/venv/bin/python main.py
   Restart=always
   RestartSec=10
   
   [Install]
   WantedBy=multi-user.target

### 2. Управление сервисом

.. code-block:: bash

   # Перезагрузка systemd
   sudo systemctl daemon-reload
   
   # Включение автозапуска
   sudo systemctl enable atra
   
   # Запуск сервиса
   sudo systemctl start atra
   
   # Проверка статуса
   sudo systemctl status atra
   
   # Просмотр логов
   sudo journalctl -u atra -f

Nginx конфигурация
------------------

### 1. Базовая конфигурация

Создайте файл `/etc/nginx/sites-available/atra`:

.. code-block:: nginx

   server {
       listen 80;
       server_name your-domain.com;
       
       location / {
           proxy_pass http://localhost:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
       
       location /static/ {
           alias /home/atra/atra/static/;
       }
   }

### 2. SSL сертификат

.. code-block:: bash

   # Установка Certbot
   sudo apt install certbot python3-certbot-nginx -y
   
   # Получение SSL сертификата
   sudo certbot --nginx -d your-domain.com

Мониторинг
----------

### 1. Логирование

.. code-block:: bash

   # Просмотр логов
   tail -f logs/system.log
   tail -f logs/errors.log
   tail -f logs/trades.log
   
   # Ротация логов
   sudo logrotate -f /etc/logrotate.d/atra

### 2. Метрики

.. code-block:: bash

   # Установка Prometheus
   wget https://github.com/prometheus/prometheus/releases/download/v2.40.0/prometheus-2.40.0.linux-amd64.tar.gz
   tar xzf prometheus-2.40.0.linux-amd64.tar.gz
   cd prometheus-2.40.0.linux-amd64
   ./prometheus --config.file=prometheus.yml

### 3. Алерты

Настройте уведомления в Telegram:

.. code-block:: python

   # config.py
   ALERT_TELEGRAM_CHAT_ID = "your_chat_id"
   ALERT_TELEGRAM_BOT_TOKEN = "your_bot_token"

Резервное копирование
---------------------

### 1. Автоматическое резервное копирование

Создайте скрипт `/home/atra/backup.sh`:

.. code-block:: bash

   #!/bin/bash
   
   BACKUP_DIR="/home/atra/backups"
   DATE=$(date +%Y%m%d_%H%M%S)
   
   # Создание директории для бэкапов
   mkdir -p $BACKUP_DIR
   
   # Бэкап базы данных
   cp atra.db $BACKUP_DIR/atra_$DATE.db
   
   # Бэкап конфигурации
   cp .env $BACKUP_DIR/env_$DATE
   
   # Бэкап логов
   tar -czf $BACKUP_DIR/logs_$DATE.tar.gz logs/
   
   # Удаление старых бэкапов (старше 30 дней)
   find $BACKUP_DIR -name "*.db" -mtime +30 -delete
   find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete

### 2. Cron задача

.. code-block:: bash

   # Добавление в crontab
   crontab -e
   
   # Ежедневный бэкап в 2:00
   0 2 * * * /home/atra/backup.sh

Обновление
----------

### 1. Обновление кода

.. code-block:: bash

   # Остановка сервиса
   sudo systemctl stop atra
   
   # Обновление кода
   git pull origin main
   
   # Обновление зависимостей
   source venv/bin/activate
   pip install -r requirements.txt
   
   # Запуск тестов
   python run_tests.py
   
   # Запуск сервиса
   sudo systemctl start atra

### 2. Откат изменений

.. code-block:: bash

   # Откат к предыдущей версии
   git reset --hard HEAD~1
   
   # Перезапуск сервиса
   sudo systemctl restart atra

Безопасность
------------

### 1. Firewall

.. code-block:: bash

   # Настройка UFW
   sudo ufw enable
   sudo ufw allow ssh
   sudo ufw allow 80
   sudo ufw allow 443
   sudo ufw deny 8000

### 2. SSH безопасность

.. code-block:: bash

   # Отключение root логина
   sudo nano /etc/ssh/sshd_config
   # PermitRootLogin no
   
   # Перезапуск SSH
   sudo systemctl restart ssh

### 3. Обновления безопасности

.. code-block:: bash

   # Автоматические обновления безопасности
   sudo apt install unattended-upgrades -y
   sudo dpkg-reconfigure unattended-upgrades

Проверка развертывания
----------------------

### 1. Проверка сервисов

.. code-block:: bash

   # Статус сервисов
   sudo systemctl status atra
   sudo systemctl status nginx
   
   # Проверка портов
   netstat -tlnp | grep :80
   netstat -tlnp | grep :443

### 2. Проверка логов

.. code-block:: bash

   # Проверка логов приложения
   tail -f logs/system.log
   
   # Проверка логов nginx
   tail -f /var/log/nginx/access.log
   tail -f /var/log/nginx/error.log

### 3. Тестирование функциональности

.. code-block:: bash

   # Запуск тестов
   python run_tests.py
   
   # Проверка API
   curl http://localhost:8000/health
   
   # Проверка Telegram бота
   # Отправьте команду /start боту
