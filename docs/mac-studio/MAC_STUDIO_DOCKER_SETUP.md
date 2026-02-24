# 🐳 Настройка Docker на Mac Studio

**Дата:** 2026-01-25  
**Важно:** Docker на Mac Studio и Mac Studio - это разные системы!

---

## ⚠️ ВАЖНО: Mac Studio перезагружен

После перезагрузки Mac Studio нужно:

1. ✅ Запустить Docker Desktop
2. ✅ Запустить все сервисы через docker-compose
3. ✅ Проверить доступность всех сервисов

---

## 🚀 БЫСТРЫЙ ЗАПУСК

### На Mac Studio выполните:

```bash
cd ~/Documents/atra-web-ide
bash scripts/setup_mac_studio_docker.sh
```

Скрипт автоматически:

- ✅ Проверит Docker
- ✅ Создаст сеть atra-network
- ✅ Проверит MLX/Ollama API Server
- ✅ Запустит все контейнеры
- ✅ Проверит доступность сервисов

---

## 📋 ЧТО ЗАПУСКАЕТСЯ

1. **Victoria Agent** (порт 8010)
2. **Veronica Agent** (порт 8011)
3. **Victoria MCP** (порт 8012)
4. **Knowledge OS Database** (порт 5432)
5. **Knowledge OS API** (порт 8000)
6. **Ollama/MLX** (порт 11434) - должен быть запущен на хосте

---

## 🔍 ПРОВЕРКА ДОСТУПНОСТИ

### Локально на Mac Studio:

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

### С Mac Studio (через сеть):

```bash
# Victoria
curl http://192.168.1.64:8010/health

# Veronica
curl http://192.168.1.64:8011/health

# Ollama/MLX
curl http://192.168.1.64:11434/api/tags
```

---

## 🐛 УСТРАНЕНИЕ ПРОБЛЕМ

### Docker не запущен

```bash
# Запустите Docker Desktop вручную
open -a Docker
```

### MLX/Ollama недоступен

```bash
# Запустите MLX API Server
bash scripts/start_mlx_api_server.sh

# Или Ollama
brew install ollama
ollama serve
```

### Контейнеры не запускаются

```bash
# Проверьте логи
docker-compose -f knowledge_os/docker-compose.yml logs

# Пересоздайте контейнеры
docker-compose -f knowledge_os/docker-compose.yml up -d --force-recreate
```

---

## 🔄 АВТОЗАПУСК

### Настройка автозапуска Docker Desktop:

1. Откройте Docker Desktop
2. Settings → General
3. Включите "Start Docker Desktop when you log in"

### Автозапуск контейнеров:

Контейнеры с `restart: always` автоматически запускаются при старте Docker.

---

## 📝 РАЗНИЦА МЕЖДУ Mac Studio И MAC STUDIO

|            | Mac Studio                 | Mac Studio                 |
| ---------- | -------------------------- | -------------------------- |
| **Docker** | Локальный Docker Desktop   | Свой Docker Desktop        |
| **Проект** | `~/Documents/atra-web-ide` | `~/Documents/atra-web-ide` |
| **IP**     | 192.168.1.38 (примерно)    | 192.168.1.64               |
| **Роль**   | Клиент                     | Сервер                     |
| **Модели** | Нет (или через туннель)    | Все модели локально        |

---

## ✅ ПОСЛЕ ЗАПУСКА

После успешного запуска все сервисы должны быть доступны:

- ✅ Локально на Mac Studio: `localhost:8010`, `localhost:8011`, и т.д.
- ✅ С Mac Studio: `192.168.1.64:8010`, `192.168.1.64:8011`, и т.д.
- ✅ Из интернета: `185.177.216.15:8010` (через SSH туннель)

---

_Документ создан 2026-01-25_
