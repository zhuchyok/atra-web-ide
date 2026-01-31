# 🚀 Быстрый запуск всех сервисов на Mac Studio

**Дата:** 2026-01-25  
**Для:** Mac Studio (когда Cursor запущен)

---

## ⚡ БЫСТРЫЙ СТАРТ

### На Mac Studio выполните:

```bash
cd ~/Documents/atra-web-ide
bash scripts/start_all_on_mac_studio.sh
```

Скрипт автоматически:
1. ✅ Проверит Docker
2. ✅ Создаст сеть atra-network
3. ✅ Проверит MLX/Ollama
4. ✅ Импортирует данные с Mac Studio (если есть)
5. ✅ Запустит все контейнеры
6. ✅ Проверит доступность всех сервисов

---

## 📋 ЧТО ЗАПУСТИТСЯ

- ✅ **Victoria Agent** (8010) - Team Lead
- ✅ **Veronica Agent** (8011) - Web Researcher  
- ✅ **Victoria MCP** (8012) - MCP для Cursor
- ✅ **Knowledge OS Database** (5432) - PostgreSQL
- ✅ **Knowledge OS API** (8000) - REST API
- ✅ **Ollama/MLX** (11434) - Локальные модели (должен быть запущен на хосте)

---

## 🔍 ПРОВЕРКА

После запуска проверьте:

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

## 🌐 ДОСТУПНОСТЬ

### Локально на Mac Studio:
- `http://localhost:8010` - Victoria
- `http://localhost:8011` - Veronica
- `http://localhost:11434` - Ollama/MLX

### С Mac Studio:
- `http://192.168.1.64:8010` - Victoria
- `http://192.168.1.64:8011` - Veronica
- `http://192.168.1.64:11434` - Ollama/MLX

### Из интернета (через SSH туннель):
- `http://185.177.216.15:8010` - Victoria
- `http://185.177.216.15:8011` - Veronica
- `http://185.177.216.15:11434` - Ollama/MLX

---

## ⚠️ ТРЕБОВАНИЯ

1. **Docker Desktop** должен быть запущен
2. **MLX/Ollama** должен быть запущен на хосте (или скрипт попытается запустить)

---

## 🐛 УСТРАНЕНИЕ ПРОБЛЕМ

### Docker не запущен
```bash
open -a Docker
```

### MLX/Ollama недоступен
```bash
bash scripts/start_mlx_api_server.sh
```

### Контейнеры не запускаются
```bash
docker-compose -f knowledge_os/docker-compose.yml logs
```

---

*Документ создан 2026-01-25*
