# MLX API Server — Диагностика и решение проблем

**Дата:** 26.01.2026  
**Проблема:** MLX API Server становится недоступным во время выполнения задач сотрудниками

---

## 🔍 Причины отключения

### 1. **Процесс завершается (crash)**

- **Причины:**
  - OOM (Out of Memory) — большие модели (70B+) занимают много RAM
  - Ошибки в коде (исключения не обработаны)
  - Конфликт портов (11434 занят другим процессом)
  - Проблемы с MLX библиотекой

### 2. **Нет автозапуска**

- Процесс запускается вручную через `nohup`, но нет launchd для автоперезапуска
- При перезагрузке Mac Studio сервер не запускается автоматически

### 3. **Монитор не настроен**

- `monitor_mlx_api_server.sh` должен перезапускать при падении, но может не быть запущен через launchd

### 4. **Проблемы с портом**

- **Было:** `start_mlx_api_server.sh` использовал порт 11435, но конфигурация ожидала 11434
- **Исправлено:** Все скрипты теперь используют 11434

---

## ✅ Решения (реализовано)

### 1. **Исправлен порт: 11435 → 11434**

- ✅ `scripts/start_mlx_api_server.sh` — порт 11434
- ✅ `scripts/monitor_mlx_api_server.sh` — проверяет 11434
- ✅ `scripts/system_auto_recovery.sh` — проверяет 11434
- ✅ `knowledge_os/app/mlx_api_server.py` — порт 11434 в `__main__`

### 2. **Создан launchd plist для автозапуска**

- ✅ `scripts/setup_mlx_autostart.sh` — создает `com.atra.mlx-api-server.plist`
- ✅ Автозапуск при загрузке Mac Studio
- ✅ KeepAlive — автоматический перезапуск при падении
- ✅ Логи: `~/Library/Logs/atra-mlx-api-server.log`

### 3. **Улучшена обработка ошибок**

- ✅ `mlx_api_server.py`: обработка исключений в `get_model()`, `list_models()`
- ✅ Graceful shutdown при SIGTERM/SIGINT
- ✅ Логирование всех ошибок

### 4. **Улучшен скрипт запуска**

- ✅ Проверка падения процесса после запуска
- ✅ Сохранение PID в `~/Library/Logs/atra/mlx_api_server.pid`
- ✅ Таймауты и retry при проверке доступности
- ✅ Вывод последних строк логов при ошибке

---

## 🚀 Настройка автозапуска

### Шаг 1: Настроить автозапуск MLX API Server

```bash
cd /Users/bikos/Documents/atra-web-ide
bash scripts/setup_mlx_autostart.sh
```

**Что делает:**

- Создает `~/Library/LaunchAgents/com.atra.mlx-api-server.plist`
- Загружает в launchd
- Автозапуск при загрузке Mac Studio
- Автоматический перезапуск при падении (KeepAlive)

### Шаг 2: Настроить монитор (опционально, но рекомендуется)

```bash
bash scripts/setup_system_auto_recovery.sh
```

**Что делает:**

- Создает `com.atra.mlx-monitor.plist` для мониторинга
- Проверяет MLX каждые 30 секунд
- Перезапускает при недоступности (до 5 раз/час)

---

## 🔧 Проверка и диагностика

### Проверка статуса

```bash
# Проверка процесса
ps aux | grep mlx_api_server

# Проверка порта
lsof -i :11434

# Проверка доступности
curl http://localhost:11434/api/tags

# Проверка launchd
launchctl list | grep mlx
```

### Логи

```bash
# Логи MLX API Server
tail -f ~/Library/Logs/atra/mlx_api_server.log

# Логи монитора
tail -f ~/Library/Logs/atra-mlx-monitor.log

# Ошибки
tail -f ~/Library/Logs/atra-mlx-api-server.error.log
```

### Ручной перезапуск

```bash
# Остановить
pkill -f "uvicorn.*mlx_api_server"
# или
launchctl stop com.atra.mlx-api-server

# Запустить
bash scripts/start_mlx_api_server.sh
# или
launchctl start com.atra.mlx-api-server
```

---

## 🐛 Типичные проблемы

### 1. "Порт 11434 уже занят"

```bash
# Найти процесс
lsof -i :11434

# Остановить
kill $(lsof -ti:11434)

# Или перезапустить через launchd
launchctl stop com.atra.mlx-api-server
launchctl start com.atra.mlx-api-server
```

### 2. "Модель не найдена"

**Проблема:** Модели не в `~/mlx-models/` или пути неверные

**Решение:**

```bash
# Проверить модели
ls -la ~/mlx-models/

# Проверить конфигурацию
grep MODEL_PATHS knowledge_os/app/mlx_api_server.py
```

### 3. "Out of Memory"

**Проблема:** Большие модели (70B+) занимают всю RAM

**Решение:**

- Использовать меньшие модели (32B, 7B)
- Ограничить количество одновременно загруженных моделей
- Освобождать память после использования

### 4. "Процесс падает сразу после запуска"

**Диагностика:**

```bash
# Проверить логи
tail -50 ~/Library/Logs/atra/mlx_api_server.log

# Проверить зависимости
python3 -c "import mlx_lm, uvicorn, fastapi; print('OK')"
```

---

## 📊 Мониторинг

### Автоматический мониторинг

После настройки `setup_mlx_autostart.sh` и `setup_system_auto_recovery.sh`:

1. **MLX API Server** — автозапуск через launchd
2. **Монитор** — проверка каждые 30 секунд, перезапуск при падении
3. **System Auto Recovery** — общая проверка всех сервисов каждые 5 минут

### Проверка работы

```bash
# Статус launchd сервисов
launchctl list | grep -E "mlx|atra"

# Должны быть:
# - com.atra.mlx-api-server (MLX API Server)
# - com.atra.mlx-monitor (монитор, если настроен)
```

---

## ✅ Чек-лист настройки

- [ ] Порт исправлен: все скрипты используют 11434
- [ ] `bash scripts/setup_mlx_autostart.sh` — автозапуск MLX
- [ ] `bash scripts/setup_system_auto_recovery.sh` — монитор
- [ ] Проверка: `launchctl list | grep mlx`
- [ ] Проверка: `curl http://localhost:11434/api/tags`
- [ ] Логи: `tail -f ~/Library/Logs/atra/mlx_api_server.log`

---

## 🎯 Рекомендации

1. **Всегда используйте launchd** для автозапуска (не `nohup` вручную)
2. **Монитор обязателен** — перезапускает при падении
3. **Проверяйте логи** при проблемах
4. **Ограничьте модели** — не загружайте все сразу (экономия RAM)

---

_Документ обновлен: 26.01.2026_
