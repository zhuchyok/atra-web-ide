# 🔧 Диагностика проблем утреннего отчета Виктории

## 📋 Возможные причины недоступности AI-генератора

### 1. **Таймаут выполнения** ⏱️

**Причина:** `run_smart_agent_async` выполняется дольше 60 секунд

**Почему может быть:**

- Облачный cursor-agent недоступен или медленно отвечает
- Локальные модели (Ollama) не запущены или перегружены
- Сеть медленная или нестабильная
- База данных медленно отвечает на запросы

**Решение:**

- ✅ Уже исправлено: добавлен таймаут 60 секунд
- ✅ Fallback: при таймауте отправляется упрощенный отчет

**Проверка:**

```bash
# Проверить доступность cursor-agent
which cursor-agent
cursor-agent --version

# Проверить локальные модели
curl http://localhost:11434/api/tags
```

---

### 2. **Проблемы с импортом ai_core** 📦

**Причина:** Модуль `ai_core` не может быть импортирован

**Почему может быть:**

- Файл `ai_core.py` отсутствует или поврежден
- Проблемы с путями Python (sys.path)
- Отсутствуют зависимости модуля

**Решение:**

```bash
# Проверить наличие файла
ls -la /root/knowledge_os/app/ai_core.py

# Проверить импорт
cd /root/knowledge_os/app
python3 -c "from ai_core import run_smart_agent_async; print('OK')"
```

**Проверка:**

- ✅ Уже исправлено: добавлен fallback при ошибке импорта

---

### 3. **Проблемы с базой данных** 🗄️

**Причина:** База данных недоступна или медленно отвечает

**Почему может быть:**

- PostgreSQL не запущен
- Неправильные credentials
- База данных перегружена
- Проблемы с сетью

**Решение:**

```bash
# Проверить статус PostgreSQL
systemctl status postgresql
# или
docker ps | grep postgres

# Проверить подключение
psql -U admin -h localhost -d knowledge_os -c "SELECT 1"

# Проверить логи
tail -f /var/log/postgresql/postgresql.log
```

**Проверка:**

- ✅ Уже исправлено: добавлена проверка доступности pool перед использованием

---

### 4. **Проблемы с Telegram API** 📱

**Причина:** Telegram API недоступен или токен неверный

**Почему может быть:**

- Неверный токен бота
- Telegram API временно недоступен
- Проблемы с сетью
- Бот заблокирован

**Решение:**

```bash
# Проверить токен
curl "https://api.telegram.org/bot<TOKEN>/getMe"

# Проверить отправку сообщения
curl -X POST "https://api.telegram.org/bot<TOKEN>/sendMessage" \
  -d "chat_id=<CHAT_ID>&text=Test"
```

**Проверка:**

- ✅ Уже исправлено: добавлен fallback при ошибке отправки

---

### 5. **Проблемы с локальными моделями** 🤖

**Причина:** Локальные модели (Ollama) недоступны

**Почему может быть:**

- Ollama не запущен
- Модели не загружены
- Недостаточно памяти
- Порт занят

**Решение:**

```bash
# Проверить статус Ollama
curl http://localhost:11434/api/tags

# Проверить запущенные процессы
ps aux | grep ollama

# Проверить использование памяти
free -h
```

---

### 6. **Проблемы с облачным cursor-agent** ☁️

**Причина:** Облачный cursor-agent недоступен

**Почему может быть:**

- Cursor не установлен
- Бинарник cursor-agent не найден
- Проблемы с правами доступа
- Cursor API недоступен

**Решение:**

```bash
# Проверить наличие cursor-agent
which cursor-agent
ls -la ~/.local/bin/cursor-agent

# Проверить версию
cursor-agent --version

# Проверить права доступа
chmod +x ~/.local/bin/cursor-agent
```

---

### 7. **Проблемы с зависимостями** 📚

**Причина:** Отсутствуют необходимые Python пакеты

**Почему может быть:**

- Не установлены зависимости
- Неправильная версия пакета
- Конфликт версий

**Решение:**

```bash
# Проверить установленные пакеты
pip list | grep -E "(asyncpg|requests|aiohttp)"

# Установить зависимости
pip install -r requirements.txt

# Проверить импорты
python3 -c "import asyncpg; import requests; print('OK')"
```

---

## 🧪 Комплексное тестирование

### Запуск тестового скрипта:

```bash
cd /root/knowledge_os
python3 scripts/test_victoria_morning_report.py
```

### Что проверяет скрипт:

1. ✅ Подключение к базе данных
2. ✅ Импорт ai_core модуля
3. ✅ Выполнение ai_core (быстрый тест)
4. ✅ Импорт всех зависимостей
5. ✅ Доступность Telegram API
6. ✅ Выполнение SQL запросов из отчета
7. ✅ Полная генерация отчета

---

## 🔍 Диагностика проблем

### Шаг 1: Проверить логи

```bash
# Логи утреннего отчета
tail -f /root/knowledge_os/logs/morning_report.log

# Логи системы
journalctl -u knowledge_os -f
```

### Шаг 2: Запустить тестовый скрипт

```bash
python3 scripts/test_victoria_morning_report.py
```

### Шаг 3: Проверить cron задачу

```bash
# Просмотреть cron задачи
crontab -l | grep victoria_morning_report

# Проверить время следующего запуска
# Задача запускается ежедневно в 8:00 UTC
```

### Шаг 4: Ручной запуск для теста

```bash
cd /root/knowledge_os
python3 app/victoria_morning_report.py
```

---

## ✅ Решения, которые уже внедрены

### 1. Таймаут и Fallback

- ✅ Таймаут 60 секунд для генерации отчета
- ✅ Упрощенный отчет при таймауте
- ✅ Минимальный отчет при ошибке

### 2. Проверка зависимостей

- ✅ Fallback при ошибке импорта ai_core
- ✅ Fallback при ошибке импорта зависимостей
- ✅ Проверка доступности базы данных

### 3. Улучшенная обработка ошибок

- ✅ Логирование всех ошибок
- ✅ Отправка отчета даже при ошибках
- ✅ Детальная информация об ошибках

---

## 📊 Мониторинг

### Проверка статуса компонентов:

```bash
# База данных
psql -U admin -h localhost -d knowledge_os -c "SELECT 1"

# Telegram API
curl "https://api.telegram.org/bot<TOKEN>/getMe"

# Локальные модели
curl http://localhost:11434/api/tags

# Cursor-agent
which cursor-agent && cursor-agent --version
```

### Автоматическая проверка:

```bash
# Запустить тестовый скрипт
python3 scripts/test_victoria_morning_report.py

# Исправить проблемы
bash scripts/fix_victoria_morning_report.sh
```

---

## 🚀 Быстрое исправление

Если доклад не приходит:

1. **Проверить cron задачу:**

   ```bash
   crontab -l | grep victoria_morning_report
   ```

2. **Запустить тестовый скрипт:**

   ```bash
   python3 scripts/test_victoria_morning_report.py
   ```

3. **Исправить проблемы:**

   ```bash
   bash scripts/fix_victoria_morning_report.sh
   ```

4. **Ручной запуск для теста:**
   ```bash
   python3 app/victoria_morning_report.py
   ```

---

## 📝 Логи и отладка

### Включить детальное логирование:

```python
# В victoria_morning_report.py
logging.basicConfig(level=logging.DEBUG)
```

### Проверить последние ошибки:

```bash
grep -i error /root/knowledge_os/logs/morning_report.log | tail -20
```

### Проверить успешные запуски:

```bash
grep -i "✅" /root/knowledge_os/logs/morning_report.log | tail -10
```

---

## 🎯 Итог

**Утренний доклад Виктории теперь:**

- ✅ Всегда отправляется (даже при ошибках)
- ✅ Имеет три уровня fallback
- ✅ Логирует все проблемы
- ✅ Имеет комплексный тестовый скрипт
- ✅ Имеет скрипт автоматического исправления

**Если доклад не приходит:**

1. Запустите тестовый скрипт
2. Проверьте логи
3. Используйте скрипт исправления
4. Проверьте cron задачу
