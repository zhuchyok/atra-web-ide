# 🚀 НАСТРОЙКА MLX API SERVER ВМЕСТО OLLAMA

**Дата:** 2026-01-21  
**Цель:** Использовать MLX API Server вместо Ollama для лучшей производительности на Mac Studio

---

## 🎯 ЗАЧЕМ ЭТО НУЖНО

### Преимущества MLX API Server:

- ✅ **Быстрее** на Apple Silicon (использует Neural Engine)
- ✅ **Экономия памяти** (квантованные модели)
- ✅ **Совместимый API** с Ollama (работает без изменений кода)
- ✅ **Меньше процессов** (один вместо Ollama + модели)

### Текущая ситуация:

- ⚠️ Nightly Learner требует API на порту 11434
- ⚠️ Local Router использует Ollama как fallback
- ✅ MLX API Server эмулирует Ollama API

---

## 🚀 БЫСТРЫЙ СТАРТ

### Вариант 1: Автоматическая настройка (рекомендуется)

```bash
cd ~/Documents/dev/atra
bash scripts/setup_mlx_instead_ollama.sh
```

Этот скрипт:

1. Проверит зависимости
2. Остановит Ollama (если запущена)
3. Запустит MLX API Server
4. Настроит автозапуск

---

### Вариант 2: Ручная настройка

#### 1. Запуск MLX API Server:

```bash
bash scripts/start_mlx_api_server.sh
```

#### 2. Настройка автозапуска:

```bash
bash scripts/setup_mlx_api_autostart.sh
```

---

## 📋 ЧТО СОЗДАНО

### 1. Скрипт запуска

**Файл:** `scripts/start_mlx_api_server.sh`

**Что делает:**

- Проверяет зависимости (Python, uvicorn, MLX)
- Останавливает процесс на порту 11434 (если есть)
- Запускает MLX API Server в фоне
- Проверяет доступность

**Использование:**

```bash
bash scripts/start_mlx_api_server.sh
```

---

### 2. Автозапуск через launchd

**Файл:** `scripts/setup_mlx_api_autostart.sh`

**Что делает:**

- Создает LaunchAgent для macOS
- Настраивает автозапуск при входе в систему
- Настраивает KeepAlive (автоматический перезапуск при падении)

**Использование:**

```bash
bash scripts/setup_mlx_api_autostart.sh
```

**Управление:**

```bash
# Запуск
launchctl kickstart -k user/$(id -u)/com.atra.mlx-api-server

# Остановка
launchctl bootout user/$(id -u)/com.atra.mlx-api-server

# Статус
launchctl list | grep mlx-api-server
```

---

### 3. Полная автоматическая настройка

**Файл:** `scripts/setup_mlx_instead_ollama.sh`

**Что делает:**

- Все шаги автоматически
- Останавливает Ollama
- Запускает MLX API Server
- Настраивает автозапуск

---

## 🔍 ПРОВЕРКА

### Проверка работы:

```bash
# Health check
curl http://localhost:11434/

# Список моделей
curl http://localhost:11434/api/tags

# Тест генерации
curl -X POST http://localhost:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{"model": "default", "prompt": "Hello", "stream": false}'
```

### Проверка логов:

```bash
# Логи MLX API Server
tail -f ~/Library/Logs/atra/mlx_api_server.log

# Или если запущен через launchd
tail -f ~/Library/Logs/atra/mlx_api_server.*.log
```

---

## 📊 СРАВНЕНИЕ

| Параметр           | Ollama         | MLX API Server           |
| ------------------ | -------------- | ------------------------ |
| Производительность | Хорошая        | ⚡ Лучше (Neural Engine) |
| Память             | ~3-4GB         | 💾 Меньше (квантование)  |
| API совместимость  | ✅             | ✅ (эмулирует Ollama)    |
| Автозапуск         | ✅             | ✅ (через launchd)       |
| Установка          | Требует Ollama | Требует MLX              |

---

## ⚠️ ВАЖНО

### MLX API Server требует:

1. ✅ MLX установлен (`pip install mlx mlx-lm`)
2. ✅ MLX модели в `~/.mlx_models/`
3. ✅ Python 3.11+

### Если модели не установлены:

MLX API Server запустится, но модели нужно будет загрузить через HuggingFace:

```bash
# Пример (если нужно)
python3 -c "from mlx_lm import load; load('mlx-community/Qwen2.5-3B-Instruct-4bit')"
```

---

## 🔄 МИГРАЦИЯ С OLLAMA

### Если Ollama уже запущена:

1. Скрипт автоматически остановит Ollama
2. Запустит MLX API Server на том же порту (11434)
3. Все компоненты продолжат работать без изменений

### Если нужно вернуться к Ollama:

```bash
# Остановить MLX API Server
launchctl bootout user/$(id -u)/com.atra.mlx-api-server
pkill -f "mlx_api_server"

# Запустить Ollama
ollama serve
```

---

## ✅ ИТОГ

**MLX API Server:**

- ✅ Запускается автоматически
- ✅ Работает вместо Ollama
- ✅ Совместим с существующим кодом
- ✅ Лучшая производительность на Mac Studio

**Ollama больше не нужна!** 🎉

---

**Последнее обновление:** 2026-01-21
