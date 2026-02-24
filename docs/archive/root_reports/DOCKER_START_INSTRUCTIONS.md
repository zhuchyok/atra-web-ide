# 🐳 Инструкция по запуску Docker

**Проблема:** Docker daemon недоступен

---

## ⚠️ Важно: Volume БД (рекомендации экспертов 2026-02-01)

Knowledge OS использует **общий volume** `atra_knowledge_postgres_data` (85+ экспертов, 26k+ узлов знаний).

- **НЕ выполняйте** `docker-compose down -v` — это удалит данные!
- Для остановки: `./scripts/safe_docker_down.sh` или `docker-compose down` (без -v)
- Проверка БД: `./scripts/backup_knowledge_os.sh` для бэкапа

---

## 🔧 Решение

### Вариант 1: Перезапуск Docker Desktop

1. **Закрыть Docker Desktop полностью**
   - В меню Docker Desktop: Quit Docker Desktop
   - Или через Activity Monitor: найти Docker и завершить процесс

2. **Запустить Docker Desktop заново**
   - Открыть Docker Desktop
   - Дождаться полного запуска (иконка в трее должна быть зеленой)

3. **Проверить работу:**

   ```bash
   docker ps
   ```

   Должно показать список контейнеров (может быть пустым, это нормально)

### Вариант 2: Проверка через Docker Desktop

1. Открыть Docker Desktop
2. Проверить статус в нижней части окна
3. Если есть ошибки - посмотреть в Settings → Troubleshoot

### Вариант 3: Запуск через терминал

```bash
# Открыть Docker Desktop
open -a Docker

# Подождать 10-15 секунд
sleep 15

# Проверить
docker ps
```

---

## ✅ После запуска Docker

Выполните команды:

```bash
cd /Users/bikos/Documents/atra-web-ide

# Полный запуск (проверка volume, БД, агенты)
./scripts/start_full_corporation.sh

# Или только Victoria Agent
docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent

# Проверить логи
docker logs -f victoria-agent

# Проверить статус
curl http://localhost:8010/status | jq '.victoria_enhanced'
```

---

## 🔍 Диагностика

### Проверить, запущен ли Docker:

```bash
# Проверить процессы
ps aux | grep -i docker

# Проверить socket
ls -la ~/.docker/run/docker.sock

# Проверить версию
docker --version
```

### Если Docker не запускается:

1. Проверить системные требования
2. Проверить логи Docker Desktop
3. Перезагрузить Mac (если нужно)

---

## 📋 Альтернатива: Локальный запуск

Если Docker не работает, можно запустить локально:

```bash
cd /Users/bikos/Documents/atra-web-ide

# Установить переменные
export USE_VICTORIA_ENHANCED=true
export ENABLE_EVENT_MONITORING=true

# Запустить сервер
python -m src.agents.bridge.victoria_server
```

---

**После запуска Docker выполните команды выше для запуска Victoria Agent.**
