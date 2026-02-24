# Исправление проблемы отключения MLX API Server

**Дата:** 26.01.2026  
**Проблема:** MLX API Server становится недоступным во время выполнения задач

---

## 🔍 Найденные проблемы

1. **Несоответствие портов:**
   - `start_mlx_api_server.sh` использовал порт **11435**
   - Конфигурация ожидала порт **11434**
   - Монитор проверял **11435**

2. **Нет автозапуска:**
   - Процесс запускался через `nohup` вручную
   - Нет launchd plist для автозапуска при перезагрузке
   - Нет автоматического перезапуска при падении

3. **Слабая обработка ошибок:**
   - Исключения не обрабатывались в некоторых местах
   - Нет graceful shutdown
   - Нет проверки падения процесса после запуска

---

## ✅ Исправления

### 1. Унифицирован порт: 11434

**Исправлено:**

- ✅ `scripts/start_mlx_api_server.sh` — порт 11434
- ✅ `scripts/monitor_mlx_api_server.sh` — проверяет 11434
- ✅ `scripts/system_auto_recovery.sh` — проверяет 11434 (все места)
- ✅ `knowledge_os/app/mlx_api_server.py` — порт 11434 в `__main__`
- ✅ `scripts/mlx_api_server.py` — порт 11434
- ✅ `scripts/run_website_test.py` — порт 11434

### 2. Создан автозапуск через launchd

**Создан:** `scripts/setup_mlx_autostart.sh`

**Что делает:**

- Создает `~/Library/LaunchAgents/com.atra.mlx-api-server.plist`
- Автозапуск при загрузке Mac Studio (`RunAtLoad: true`)
- Автоматический перезапуск при падении (`KeepAlive: Crashed`)
- Логи: `~/Library/Logs/atra-mlx-api-server.log`

### 3. Улучшена обработка ошибок

**В `mlx_api_server.py`:**

- ✅ `get_model()` — обработка исключений при загрузке моделей
- ✅ `list_models()` — обработка ошибок с HTTPException
- ✅ Graceful shutdown при SIGTERM/SIGINT
- ✅ Очистка кэша моделей при завершении

**В `start_mlx_api_server.sh`:**

- ✅ Проверка падения процесса после запуска
- ✅ Сохранение PID в `~/Library/Logs/atra/mlx_api_server.pid`
- ✅ Таймауты и retry при проверке доступности
- ✅ Вывод последних строк логов при ошибке

---

## 🚀 Как применить исправления

### На Mac Studio:

```bash
cd /Users/bikos/Documents/atra-web-ide

# 1. Настроить автозапуск MLX API Server
bash scripts/setup_mlx_autostart.sh

# 2. Настроить монитор (опционально, но рекомендуется)
bash scripts/setup_system_auto_recovery.sh

# 3. Проверить статус
launchctl list | grep mlx
curl http://localhost:11434/api/tags
```

### Проверка:

```bash
# Статус launchd
launchctl list | grep -E "mlx|atra"

# Должны быть:
# - com.atra.mlx-api-server ✅
# - com.atra.mlx-monitor ✅ (если настроен)

# Проверка доступности
curl http://localhost:11434/api/tags

# Логи
tail -f ~/Library/Logs/atra/mlx_api_server.log
```

---

## 📊 Результат

**До исправлений:**

- ❌ Порт 11435 (не совпадал с конфигурацией)
- ❌ Нет автозапуска
- ❌ Нет автоперезапуска при падении
- ❌ Слабая обработка ошибок

**После исправлений:**

- ✅ Порт 11434 (унифицирован)
- ✅ Автозапуск через launchd
- ✅ Автоперезапуск при падении (KeepAlive)
- ✅ Монитор перезапускает при недоступности
- ✅ Улучшенная обработка ошибок и логирование

---

## 🔧 Если проблема повторится

1. **Проверить логи:**

   ```bash
   tail -50 ~/Library/Logs/atra/mlx_api_server.log
   tail -50 ~/Library/Logs/atra-mlx-api-server.error.log
   ```

2. **Проверить процесс:**

   ```bash
   ps aux | grep mlx_api_server
   lsof -i :11434
   ```

3. **Перезапустить:**

   ```bash
   launchctl stop com.atra.mlx-api-server
   launchctl start com.atra.mlx-api-server
   ```

4. **Если launchd не работает:**
   ```bash
   bash scripts/start_mlx_api_server.sh
   ```

---

_Исправления применены: 26.01.2026_
