# 🔍 Проверка и запуск контейнеров на Mac Studio

**Дата:** 2026-01-26

---

## ⚡ БЫСТРАЯ ПРОВЕРКА

### На Mac Studio выполните:

```bash
cd ~/Documents/atra-web-ide
bash scripts/check_and_start_containers.sh
```

Скрипт автоматически:
1. ✅ Проверит Docker
2. ✅ Создаст сеть (если нужно)
3. ✅ Проверит статус контейнеров
4. ✅ Запустит не запущенные контейнеры
5. ✅ Проверит доступность всех сервисов

---

## 📋 РУЧНАЯ ПРОВЕРКА

### 1. Проверка Docker

```bash
export PATH="/usr/local/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"
docker info
```

### 2. Проверка статуса контейнеров

```bash
cd ~/Documents/atra-web-ide
export PATH="/usr/local/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"
docker-compose -f knowledge_os/docker-compose.yml ps
```

### 3. Запуск контейнеров

```bash
docker-compose -f knowledge_os/docker-compose.yml up -d
```

### 4. Проверка сервисов

```bash
# Victoria
curl http://localhost:8010/health

# Veronica
curl http://localhost:8011/health

# Ollama/MLX
curl http://localhost:11434/api/tags

# Knowledge OS
curl http://localhost:8000/health
```

---

## 🐛 УСТРАНЕНИЕ ПРОБЛЕМ

### Контейнеры не запускаются

```bash
# Проверьте логи
docker-compose -f knowledge_os/docker-compose.yml logs

# Пересоздайте контейнеры
docker-compose -f knowledge_os/docker-compose.yml up -d --force-recreate
```

### Docker не найден

```bash
# Убедитесь, что Docker Desktop запущен
open -a Docker

# Проверьте PATH
export PATH="/usr/local/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"
which docker
```

### Порт занят

```bash
# Проверьте, что занимает порт
lsof -i :8010
lsof -i :8011

# Остановите конфликтующий процесс или измените порт в docker-compose.yml
```

---

## ✅ ОЖИДАЕМЫЙ РЕЗУЛЬТАТ

После запуска должны работать:

- ✅ Victoria Agent на порту 8010
- ✅ Veronica Agent на порту 8011
- ✅ Knowledge OS Database на порту 5432
- ✅ Knowledge OS API на порту 8000
- ✅ Ollama/MLX на порту 11434

---

*Документ создан: 2026-01-26*
