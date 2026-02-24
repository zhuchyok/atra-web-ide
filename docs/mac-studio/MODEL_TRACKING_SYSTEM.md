# 🔄 Система отслеживания моделей

**Дата:** 2026-01-25  
**Статус:** ✅ Реализовано

---

## 🎯 Назначение

Автоматическое отслеживание доступных моделей Ollama/MLX и сохранение информации в базу знаний Knowledge OS. Система уведомляет Викторию, Веронику и корпорацию о новых моделях и их характеристиках.

---

## 📦 Компоненты

### 1. Model Tracker (`knowledge_os/app/model_tracker.py`)

**Функции:**

- ✅ Периодически проверяет доступные модели через API (`/api/tags`)
- ✅ Сохраняет информацию о моделях в базу знаний
- ✅ Отслеживает изменения (новые/удаленные модели)
- ✅ Определяет категорию модели (Coding, Reasoning, Vision, Fast, Complex)
- ✅ Форматирует размеры и параметры моделей

**Интервал проверки:** 1 час (настраивается через `MODEL_TRACKER_INTERVAL`)

### 2. Model Notifier (`knowledge_os/app/model_notifier.py`)

**Функции:**

- ✅ Уведомляет Викторию (Team Lead) о новых моделях
- ✅ Уведомляет Веронику (Local Developer) о новых моделях
- ✅ Сохраняет уведомления в базу знаний

---

## 🚀 Запуск

### Вариант 1: Через скрипт (рекомендуется)

```bash
bash scripts/start_model_tracker.sh
```

### Вариант 2: Напрямую через Python

```bash
cd knowledge_os
python3 -m app.model_tracker
```

### Вариант 3: Как сервис (systemd/launchd)

Создайте файл `~/Library/LaunchAgents/com.atra.model_tracker.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.atra.model_tracker</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>-m</string>
        <string>app.model_tracker</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/atra-web-ide/knowledge_os</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>DATABASE_URL</key>
        <string>postgresql://zhuchyok@localhost:5432/knowledge_os</string>
        <key>OLLAMA_BASE_URL</key>
        <string>http://localhost:11434</string>
        <key>MODEL_TRACKER_INTERVAL</key>
        <string>3600</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/model_tracker.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/model_tracker.error.log</string>
</dict>
</plist>
```

Запуск:

```bash
launchctl load ~/Library/LaunchAgents/com.atra.model_tracker.plist
```

---

## ⚙️ Настройка

### Переменные окружения

| Переменная               | Описание                     | По умолчанию                                        |
| ------------------------ | ---------------------------- | --------------------------------------------------- |
| `DATABASE_URL`           | URL базы данных              | `postgresql://zhuchyok@localhost:5432/knowledge_os` |
| `OLLAMA_BASE_URL`        | URL Ollama/MLX API           | `http://localhost:11434`                            |
| `MODEL_TRACKER_INTERVAL` | Интервал проверки (секунды)  | `3600` (1 час)                                      |
| `VICTORIA_URL`           | URL Виктории для уведомлений | `http://localhost:8010`                             |
| `VERONICA_URL`           | URL Вероники для уведомлений | `http://localhost:8011`                             |

---

## 📊 Что отслеживается

### Информация о моделях

Для каждой модели сохраняется:

- ✅ Имя модели
- ✅ Размер (в GB/MB)
- ✅ Количество параметров
- ✅ Формат (gguf, mlx)
- ✅ Уровень квантования
- ✅ Семейство модели
- ✅ Категория (Coding, Reasoning, Vision, Fast, Complex)
- ✅ Дата последнего обновления
- ✅ Digest (хеш модели)

### Изменения

Система отслеживает:

- 🆕 Новые модели (автоматически добавляются)
- ⚠️ Удаленные модели (отмечаются в сводке)
- 📊 Общее количество доступных моделей

---

## 💾 Хранение в базе знаний

### Домен: "AI Models"

Все модели сохраняются в домен "AI Models" как `knowledge_nodes`:

```sql
SELECT content, metadata
FROM knowledge_nodes
WHERE domain_id = (SELECT id FROM domains WHERE name = 'AI Models')
ORDER BY created_at DESC;
```

### Структура метаданных

```json
{
  "type": "model",
  "model_name": "qwen2.5-coder:32b",
  "size_bytes": 21474836480,
  "size_formatted": "20.00 GB",
  "parameter_size": "32B",
  "format": "gguf",
  "quantization_level": "Q8_0",
  "families": ["qwen2"],
  "category": "Coding - разработка кода",
  "modified_at": "2026-01-25T10:30:00Z",
  "digest": "abc123...",
  "last_tracked": "2026-01-25T12:00:00Z"
}
```

---

## 🔔 Уведомления

### Виктория (Team Lead)

Получает уведомления о:

- 🆕 Новых моделях с полной информацией
- 📊 Характеристиках моделей
- 💡 Рекомендации по использованию

### Вероника (Local Developer)

Получает уведомления о:

- 🆕 Новых моделях (краткая информация)
- 💡 Возможности использования для разработки

---

## 📈 Мониторинг

### Логи

Логи отслеживания сохраняются в:

- Стандартный вывод (stdout)
- Файл логов (если настроен через systemd/launchd)

### Проверка работы

```bash
# Проверить последние записи в базе знаний
psql -d knowledge_os -c "
SELECT content, created_at
FROM knowledge_nodes
WHERE domain_id = (SELECT id FROM domains WHERE name = 'AI Models')
ORDER BY created_at DESC
LIMIT 5;
"
```

---

## 🔧 Интеграция с системой

### Victoria Agent

Виктория автоматически получает уведомления о новых моделях и может:

- Обновить конфигурацию выбора моделей
- Рекомендовать использование новых моделей
- Анализировать производительность моделей

### Veronica Agent

Вероника получает уведомления и может:

- Использовать новые модели для разработки
- Тестировать новые модели на задачах

### Knowledge OS

Информация о моделях доступна через:

- Поиск в базе знаний: "модели", "AI Models"
- MCP инструменты: `capture_knowledge`, `search_knowledge`
- REST API: `/knowledge?domain=AI Models`

---

## 🐛 Устранение неполадок

### Модели не отслеживаются

1. Проверьте доступность API:

   ```bash
   curl http://localhost:11434/api/tags
   ```

2. Проверьте подключение к БД:

   ```bash
   psql -d knowledge_os -c "SELECT COUNT(*) FROM domains WHERE name = 'AI Models';"
   ```

3. Проверьте логи:
   ```bash
   tail -f /tmp/model_tracker.log
   ```

### Уведомления не отправляются

1. Проверьте доступность агентов:

   ```bash
   curl http://localhost:8010/health  # Victoria
   curl http://localhost:8011/health  # Veronica
   ```

2. Проверьте переменные окружения:
   ```bash
   echo $VICTORIA_URL
   echo $VERONICA_URL
   ```

---

## 📝 Примеры использования

### Ручная проверка моделей

```python
from knowledge_os.app.model_tracker import ModelTracker

tracker = ModelTracker()
await tracker.track_models()
```

### Получение списка моделей из базы знаний

```python
import asyncpg

conn = await asyncpg.connect("postgresql://zhuchyok@localhost:5432/knowledge_os")
models = await conn.fetch("""
    SELECT content, metadata
    FROM knowledge_nodes
    WHERE domain_id = (SELECT id FROM domains WHERE name = 'AI Models')
    AND metadata->>'type' = 'model'
    ORDER BY created_at DESC
""")
```

---

## ✅ Чек-лист настройки

- [ ] Установлены зависимости (`asyncpg`, `httpx`)
- [ ] Настроены переменные окружения
- [ ] Проверена доступность Ollama/MLX API
- [ ] Проверена доступность базы данных
- [ ] Создан домен "AI Models" (создается автоматически)
- [ ] Запущен Model Tracker
- [ ] Проверены уведомления Виктории и Вероники

---

**Версия:** 1.0  
**Обновлено:** 2026-01-25
