# 🚀 Быстрый запуск Victoria Initiative

**Дата:** 2026-01-27

---

## ⚠️ Требуется Docker

**Docker daemon не запущен.** Для запуска Victoria Agent нужно:

### Вариант 1: Docker (рекомендуется)

**Шаг 1:** Запустить Docker Desktop

**Шаг 2:** После запуска Docker выполнить:
```bash
cd /Users/bikos/Documents/atra-web-ide
docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent
```

**Шаг 3:** Проверить логи:
```bash
docker logs -f victoria-agent
```

**Ожидаемые логи:**
```
🚀 Инициализация Victoria Enhanced при старте сервера...
✅ Victoria Enhanced мониторинг запущен при старте сервера
🚀 Event Bus запущен
🚀 File Watcher запущен
🚀 Service Monitor запущен
🚀 Skills Watcher запущен
```

**Шаг 4:** Проверить статус:
```bash
curl http://localhost:8010/status | jq '.victoria_enhanced'
```

---

### Вариант 2: Локальный запуск

**Шаг 1:** Установить переменные окружения:
```bash
export USE_VICTORIA_ENHANCED=true
export ENABLE_EVENT_MONITORING=true
```

**Шаг 2:** Запустить сервер:
```bash
cd /Users/bikos/Documents/atra-web-ide
python -m src.agents.bridge.victoria_server
```

**Ожидаемые логи:**
```
🚀 Инициализация Victoria Enhanced при старте сервера...
✅ Victoria Enhanced мониторинг запущен при старте сервера
🚀 Event Bus запущен
...
```

---

## ✅ Проверка работы

### 1. Проверить статус

```bash
curl http://localhost:8010/status | jq '.victoria_enhanced'
```

**Ожидаемый результат:**
```json
{
  "enabled": true,
  "monitoring_started": true,
  "event_bus_available": true,
  "skill_registry_available": true,
  "skills_count": 0,
  "file_watcher_available": true,
  "service_monitor_available": true
}
```

### 2. Тест создания файла

```bash
# Создать файл
touch /tmp/test_victoria.py

# Проверить логи (должно быть событие FILE_CREATED)
docker logs victoria-agent | grep "FILE_CREATED"
```

### 3. Тест падения сервиса

```bash
# Остановить MLX Server
pkill -f mlx_api_server

# Проверить логи (должно быть событие SERVICE_DOWN)
docker logs victoria-agent | grep "SERVICE_DOWN"
```

---

## 📋 Текущий статус

**Код:** ✅ Готов  
**Конфигурация:** ✅ Настроена  
**Docker:** ⚠️ Требуется запуск Docker Desktop  

**После запуска Docker все компоненты автоматически запустятся!**

---

## 🔧 Решение проблем

### Docker не запускается

1. Открыть Docker Desktop
2. Дождаться полного запуска (иконка в трее)
3. Проверить: `docker ps`

### Контейнер не запускается

1. Проверить логи: `docker logs victoria-agent`
2. Проверить переменные окружения в `.env`
3. Проверить порты: `lsof -i :8010`

### Мониторинг не запускается

1. Проверить `.env`: `ENABLE_EVENT_MONITORING=true`
2. Проверить логи: `docker logs victoria-agent | grep "мониторинг"`
3. Проверить статус: `curl http://localhost:8010/status | jq '.victoria_enhanced'`

---

## 📚 Документация

- `HOW_TO_USE_VICTORIA_INITIATIVE.md` - полная инструкция
- `VICTORIA_INITIATIVE_READY.md` - готовность к использованию
- `VICTORIA_COMPATIBILITY_REPORT.md` - совместимость

---

**Все готово! Запустите Docker Desktop и выполните команды выше.** 🚀
