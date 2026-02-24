# 🚀 ИНСТРУКЦИЯ: Запуск Mac Studio как сервера

**Дата:** 2025-01-21  
**Проект:** atra-web-ide (всё по Mac Studio)

---

## ⚠️ ВАЖНО: Docker Desktop должен быть запущен!

Если вы видите ошибку "Docker daemon не запущен", выполните:

1. **Запустите Docker Desktop** на Mac Studio
2. **Дождитесь** пока Docker полностью загрузится
3. **Запустите** скрипт снова

---

## 🚀 ЗАПУСК ИНФРАСТРУКТУРЫ

### Вариант 1: Через готовый скрипт

```bash
./scripts/start_mac_studio_full.sh
```

### Вариант 2: Вручную через Docker Compose

```bash
# 1. Создайте директории
mkdir -p logs/mlx logs/knowledge-os logs/agents
mkdir -p backups/knowledge-os data cache

# 2. Запустите все сервисы
docker-compose up -d

# 3. Проверьте статус
docker-compose ps
```

---

## 📋 ЧТО БУДЕТ ЗАПУЩЕНО

1. ✅ **MLX API Server** - все production модели (131GB, 61GB, и т.д.)
2. ✅ **Knowledge OS Database** - PostgreSQL с pgvector
3. ✅ **Knowledge OS API** - REST API для Knowledge OS
4. ✅ **Knowledge OS Worker** - фоновые задачи
5. ✅ **Victoria Agent** - Team Lead агент
6. ✅ **Veronica Agent** - Web Researcher агент
7. ✅ **Nightly Learner** - обучение экспертов
8. ✅ **Prometheus** - мониторинг метрик
9. ✅ **Grafana** - дашборды и визуализация

---

## 🔍 ПРОВЕРКА РАБОТОСПОСОБНОСТИ

После запуска проверьте:

```bash
# Статус всех контейнеров
docker-compose ps

# Проверка MLX API Server
curl http://localhost:11434/

# Проверка Knowledge OS API
curl http://localhost:8000/

# Проверка Prometheus
curl http://localhost:9090/-/healthy

# Проверка Grafana
curl http://localhost:3000/api/health
```

---

## 📊 ДОСТУП К СЕРВИСАМ

- **MLX API Server:** http://localhost:11434
- **Knowledge OS API:** http://localhost:8000
- **Prometheus:** http://localhost:9090
- **Grafana:** http://localhost:3000 (admin/atra2025)

---

## 🔧 УПРАВЛЕНИЕ

### Остановка:

```bash
docker-compose down
```

### Перезапуск:

```bash
docker-compose restart [service_name]
```

### Просмотр логов:

```bash
docker-compose logs -f [service_name]
```

---

## ✅ ПОСЛЕ ЗАПУСКА

1. ✅ Все сервисы работают
2. ✅ Mac Studio - центральный сервер
3. ✅ Все агенты используют локальные модели
4. ✅ Knowledge OS готова к миграции данных
5. ✅ Мониторинг активен

---

_Скопировано из atra в atra-web-ide для работы по Mac Studio — 2025-01_
