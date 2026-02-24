# 🐳 РУКОВОДСТВО ПО УСТАНОВКЕ DOCKER

## 📋 Текущий статус

✅ **ATRA работает без Docker** - система запущена и функционирует нормально!  
⚠️ **Docker не установлен** - требуется установка для полного стека сервисов

---

## 🚀 УСТАНОВКА DOCKER ДЛЯ MACOS

### **Способ 1: Через Homebrew (рекомендуется)**

```bash
# Установка Docker Desktop
brew install --cask docker

# После установки запустите Docker Desktop из Applications
# Или через командную строку:
open -a Docker
```

### **Способ 2: Скачать с официального сайта**

1. Перейдите на https://www.docker.com/products/docker-desktop/
2. Скачайте Docker Desktop for Mac
3. Установите .dmg файл
4. Запустите Docker Desktop

### **Способ 3: Через MacPorts**

```bash
# Если используете MacPorts
sudo port install docker
```

---

## ✅ ПРОВЕРКА УСТАНОВКИ

После установки проверьте:

```bash
# Проверка Docker
docker --version

# Проверка Docker Compose
docker-compose --version

# Проверка запуска
docker run hello-world
```

**Ожидаемый результат:**

```
Docker version 24.0.0, build 1234567
Docker Compose version v2.20.0
Hello from Docker!
```

---

## 🚀 ЗАПУСК ATRA С DOCKER

После установки Docker:

### **1. Полный стек сервисов:**

```bash
# Запуск всех сервисов (Redis, Elasticsearch, Kibana, Grafana)
docker-compose up -d

# Проверка статуса
docker-compose ps

# Просмотр логов
docker-compose logs -f atra-bot
```

### **2. Доступ к сервисам:**

- **Web Dashboard**: http://localhost:5000
- **REST API**: http://localhost:8080
- **Grafana**: http://localhost:3000 (admin/atra2025)
- **Kibana**: http://localhost:5601

### **3. Остановка:**

```bash
# Остановка всех сервисов
docker-compose down

# Остановка с удалением данных
docker-compose down -v
```

---

## 🔧 УСТРАНЕНИЕ ПРОБЛЕМ

### **Проблема: Docker не запускается**

```bash
# Перезапуск Docker
sudo systemctl restart docker  # Linux
# или
open -a Docker  # macOS
```

### **Проблема: Недостаточно памяти**

```bash
# Увеличьте память в Docker Desktop Settings
# Memory: минимум 4GB, рекомендуется 8GB
```

### **Проблема: Порты заняты**

```bash
# Проверьте занятые порты
lsof -i :5000
lsof -i :8080
lsof -i :3000
lsof -i :5601

# Остановите конфликтующие сервисы
```

---

## 📊 СРАВНЕНИЕ РЕЖИМОВ

| Функция              | Без Docker    | С Docker    |
| -------------------- | ------------- | ----------- |
| **Основная система** | ✅ Работает   | ✅ Работает |
| **База данных**      | ✅ SQLite     | ✅ SQLite   |
| **Логирование**      | ✅ Файлы      | ✅ ELK стек |
| **Мониторинг**       | ✅ Базовый    | ✅ Grafana  |
| **Кэширование**      | ❌ Нет        | ✅ Redis    |
| **Масштабируемость** | ⚠️ Ограничена | ✅ Полная   |

---

## 🎯 РЕКОМЕНДАЦИИ

### **Для разработки:**

- Используйте **без Docker** - быстрее и проще
- Запуск: `./start_atra.sh`

### **Для продакшена:**

- Используйте **с Docker** - полный стек сервисов
- Запуск: `docker-compose up -d`

### **Для тестирования:**

- Сначала **без Docker** для проверки основной функциональности
- Затем **с Docker** для полного тестирования

---

## 🚀 ТЕКУЩИЙ СТАТУС

**✅ ATRA РАБОТАЕТ БЕЗ DOCKER!**

Система полностью функциональна:

- ✅ Торговый бот запущен
- ✅ База данных работает (18 таблиц)
- ✅ API подключения работают
- ✅ Health check проходит успешно

**Docker нужен только для:**

- ELK логирования (Kibana)
- Мониторинга (Grafana)
- Кэширования (Redis)
- Полного enterprise-стека

---

**Заключение**: ATRA готов к использованию прямо сейчас! Docker можно установить позже для расширенного функционала. 🎉
