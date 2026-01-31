# 📦 Установка зависимостей для Victoria Server

**Проблема:** Отсутствует модуль `aiohttp` и другие зависимости

---

## 🔧 Установка зависимостей

### Вариант 1: Установка основных зависимостей

```bash
pip3 install aiohttp fastapi uvicorn pydantic
```

### Вариант 2: Установка всех зависимостей (рекомендуется)

```bash
cd /Users/bikos/Documents/atra-web-ide

# Основные зависимости для Victoria Server
pip3 install aiohttp fastapi uvicorn pydantic pydantic-settings

# Зависимости для Event-Driven Architecture
pip3 install watchdog asyncpg

# Зависимости для Knowledge OS (если используются)
pip3 install asyncpg psycopg2-binary

# Дополнительные зависимости
pip3 install httpx python-dotenv
```

### Вариант 3: Установка из requirements.txt (если есть)

```bash
cd /Users/bikos/Documents/atra-web-ide
pip3 install -r requirements.txt
```

---

## ✅ Проверка установки

```bash
python3 -c "import aiohttp, fastapi, uvicorn; print('✅ Все зависимости установлены')"
```

---

## 🚀 После установки

Запустите Victoria Server:

```bash
cd /Users/bikos/Documents/atra-web-ide
./START_VICTORIA_SIMPLE.sh
```

---

## 📋 Минимальный набор зависимостей

Для работы Victoria Server нужны:

- `aiohttp` - асинхронные HTTP запросы
- `fastapi` - веб-фреймворк
- `uvicorn` - ASGI сервер
- `pydantic` - валидация данных
- `watchdog` - для File Watcher (опционально)
- `asyncpg` - для работы с PostgreSQL (опционально)

---

**Установите зависимости и запустите сервер!** 🚀
