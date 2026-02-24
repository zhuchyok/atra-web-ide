# Обновление порта MLX API Server: 11434 → 11435

**Дата:** 26.01.2026  
**Изменение:** MLX API Server теперь работает на порту **11435** (по умолчанию)

---

## ✅ Применённые изменения

### 1. **MLX API Server (`knowledge_os/app/mlx_api_server.py`)**

- ✅ Порт по умолчанию: **11435** (через `MLX_API_PORT`)
- ✅ Поддержка переменной окружения `MLX_API_PORT`
- ✅ Улучшенные настройки uvicorn:
  - `timeout_keep_alive=120`
  - `limit_concurrency` с запасом
  - `workers=1` (MLX не поддерживает multiprocessing)

### 2. **Скрипты запуска и мониторинга**

#### `scripts/start_mlx_api_server.sh`

- ✅ Порт: **11435** (по умолчанию)
- ✅ Поддержка `MLX_API_PORT` для переопределения
- ✅ Улучшенная проверка доступности
- ✅ Сохранение PID для монитора

#### `scripts/monitor_mlx_api_server.sh`

- ✅ Проверка порта **11435**
- ✅ Поддержка `MLX_API_PORT`

#### `scripts/system_auto_recovery.sh`

- ✅ Все проверки обновлены на порт **11435**
- ✅ Поддержка `MLX_API_PORT`

#### `scripts/AUTO_START_MLX.sh`

- ✅ Порт: **11435**
- ✅ Поддержка `MLX_API_PORT`
- ✅ Экспорт переменной окружения для Python

#### `scripts/check_all_services.sh`

- ✅ Проверка порта **11435**
- ✅ Поддержка `MLX_API_PORT`

### 3. **Backend конфигурация**

#### `backend/app/config.py`

- ✅ Поддержка `MLX_API_URL` через `OLLAMA_URL`
- ✅ По умолчанию: `http://localhost:11434` (Ollama)
- ✅ Можно переопределить через `MLX_API_URL=http://localhost:11435`

---

## 🔧 Использование

### Запуск с портом по умолчанию (11435)

```bash
bash scripts/start_mlx_api_server.sh
```

### Запуск с кастомным портом

```bash
export MLX_API_PORT=11436
bash scripts/start_mlx_api_server.sh
```

### Использование в backend

**Вариант 1:** Через переменную окружения

```bash
export OLLAMA_URL=http://localhost:11435
# или
export MLX_API_URL=http://localhost:11435
```

**Вариант 2:** В `.env` файле

```env
OLLAMA_URL=http://localhost:11435
# или
MLX_API_URL=http://localhost:11435
```

---

## 📊 Проверка

### Проверка синтаксиса скриптов

```bash
bash -n scripts/start_mlx_api_server.sh      # ✅ OK
bash -n scripts/monitor_mlx_api_server.sh   # ✅ OK
bash -n scripts/system_auto_recovery.sh      # ✅ OK
```

### Проверка импорта MLX API Server

```bash
python3 -c "import sys; sys.path.insert(0, 'knowledge_os'); from app.mlx_api_server import app; print('OK')"
# ✅ OK (с предупреждением о psutil, если не установлен)
```

### Проверка доступности

```bash
# Проверка на порту 11435
curl http://localhost:11435/api/tags

# Проверка health
curl http://localhost:11435/health
```

---

## 🎯 Логика портов

- **Ollama:** `11434` (если используется)
- **MLX API Server:** `11435` (по умолчанию)
- **Можно запускать параллельно** — они не конфликтуют

---

## 📝 Заметки

1. **Переменная окружения `MLX_API_PORT`** имеет приоритет над значением по умолчанию
2. **Backend** использует `OLLAMA_URL` или `MLX_API_URL` для подключения
3. **Все скрипты** поддерживают `MLX_API_PORT` для гибкости
4. **Монитор** автоматически использует правильный порт

---

## ✅ Чек-лист проверки

- [x] `mlx_api_server.py` — порт 11435
- [x] `start_mlx_api_server.sh` — порт 11435
- [x] `monitor_mlx_api_server.sh` — порт 11435
- [x] `system_auto_recovery.sh` — порт 11435
- [x] `AUTO_START_MLX.sh` — порт 11435
- [x] `check_all_services.sh` — порт 11435
- [x] `config.py` — поддержка MLX_API_URL
- [x] Синтаксис всех скриптов проверен
- [x] Импорт MLX API Server работает

---

_Обновление применено: 26.01.2026_
