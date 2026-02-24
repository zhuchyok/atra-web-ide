# 🚀 Автозапуск Victoria — настроено

## ✅ Что уже работает

### 1. Victoria (Docker)

- **Статус:** ✅ `restart: always` в `docker-compose.yml`
- **Поведение:** Автоматически запускается при старте Docker/Mac
- **Порт:** 8010

### 2. MCP сервер

- **Настройка:** Запусти `bash scripts/quick_victoria_autostart.sh`
- **Результат:** MCP сервер будет запускаться автоматически при старте Mac
- **Порт:** 8012

---

## 🎯 Быстрая настройка (один раз)

```bash
cd /Users/zhuchyok/Documents/GITHUB/atra/atra
bash scripts/quick_victoria_autostart.sh
```

Это настроит:

- ✅ Автозапуск MCP сервера через launchd
- ✅ Victoria уже настроена (через Docker restart policy)

---

## 🔄 После настройки

### Вариант 1: Перезагрузи Mac

После перезагрузки Victoria и MCP сервер запустятся автоматически.

### Вариант 2: Запусти сейчас

```bash
# Запуск MCP сервера
launchctl start com.atra.victoria-mcp

# Проверка
curl http://localhost:8010/health
curl http://localhost:8012/sse
```

---

## 📋 Проверка автозапуска

```bash
# Проверить launchd service
launchctl list | grep victoria

# Логи MCP сервера
tail -f ~/Library/Logs/victoria-mcp.log

# Проверить Victoria
docker ps | grep victoria
```

---

## 🛠️ Ручной запуск (если нужно)

```bash
# Victoria
docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent

# MCP сервер
export PYTHONPATH=/Users/zhuchyok/Documents/GITHUB/atra/atra:$PYTHONPATH
python3 -m src.agents.bridge.victoria_mcp_server
```

---

## ✅ Итог

**После настройки:**

1. ✅ Victoria запускается автоматически (Docker)
2. ✅ MCP сервер запускается автоматически (launchd)
3. ✅ Всё готово сразу при открытии Cursor

**Использование:**

- Просто открой Cursor в любом проекте
- Используй `@victoria_run 'задача'` — всё работает!

---

_Обновлено: 2026-01-23_
