# Moondream Station (Moondream 3 Preview с MLX) - Установка и настройка

**Дата:** 2026-01-27  
**Статус:** ✅ **УСТАНОВЛЕНО И НАСТРОЕНО**

---

## 🎯 Что это?

**Moondream Station** - это локальный сервис для обработки изображений с использованием **Moondream 3 Preview**, оптимизированный для **Apple Silicon (MLX)**.

### Преимущества:

- ✅ **MLX Native** - полностью оптимизирован для Apple Silicon
- ✅ **Быстрая обработка** - более 35 токенов/сек на M1 Max
- ✅ **Локальная обработка** - без отправки в облако
- ✅ **Moondream 3 Preview** - последняя версия с улучшенными возможностями

---

## 📦 Установка

### 1. Установка Moondream Station

Пакет **moondream-station** даёт и сервер (порт 2020), и Python-клиент (`import moondream as md`). Уже добавлен в `knowledge_os/requirements.txt` и `knowledge_os/app/requirements.txt`.

```bash
# В виртуальном окружении knowledge_os
cd knowledge_os
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# или только vision:
pip install moondream-station Pillow
```

Если видите предупреждение «moondream не установлен» — установите зависимости выше; после этого `import moondream as md` и Moondream Station клиент будут доступны.

### 2. Проверка установки

```bash
moondream-station --help
```

---

## 🚀 Запуск

### Вариант 1: Через скрипт (рекомендуется)

```bash
# Bash скрипт
bash scripts/start_moondream_station.sh

# Или Python скрипт
python3 knowledge_os/scripts/start_moondream_station.py
```

### Вариант 2: Напрямую

```bash
moondream-station
```

**По умолчанию работает на порту:** `http://localhost:2020`

---

## ⚙️ Конфигурация

### Переменные окружения

Добавьте в `.env` файл:

```bash
# Moondream Station (MLX)
MOONDREAM_STATION_URL=http://localhost:2020
MOONDREAM_STATION_ENABLED=true

# Fallback на Ollama (если Moondream Station недоступен)
VISION_MODEL=moondream
MAC_LLM_URL=http://localhost:11434
```

### Приоритет обработки изображений

Система пробует в следующем порядке:

1. **Moondream Station (MLX)** - прямой Python клиент
2. **Moondream Station REST API** - через HTTP
3. **Ollama** - fallback на старый способ

---

## 🔧 Интеграция

### VisionProcessor

`VisionProcessor` автоматически использует Moondream Station, если он доступен:

```python
from vision_processor import get_vision_processor

processor = get_vision_processor()

# Обработка изображения
result = await processor.describe_image(
    image_path="/path/to/image.jpg"
)

# Анализ скриншота кода
result = await processor.analyze_code_screenshot(
    image_base64=base64_image
)
```

### Использование в агентах

Агенты (Victoria, Veronica) автоматически используют Moondream Station при получении изображений:

```python
# В ai_core.py автоматически обрабатываются изображения
result = await run_smart_agent_async(
    prompt="Проанализируй это изображение",
    images=[base64_image],
    expert_name="Виктория"
)
```

---

## 📊 API Endpoints

### Moondream Station REST API

**Base URL:** `http://localhost:2020/v1`

#### Query (запрос к изображению)

```bash
POST /v1/query
{
    "image": "base64_encoded_image",
    "prompt": "Что на этом изображении?"
}
```

#### Caption (описание изображения)

```bash
POST /v1/caption
{
    "image": "base64_encoded_image",
    "length": "normal"  # или "short"
}
```

#### Detect (обнаружение объектов)

```bash
POST /v1/detect
{
    "image": "base64_encoded_image",
    "prompt": "найди все машины"
}
```

---

## 🧪 Тестирование

### Проверка работы Moondream Station

```python
import moondream as md
from PIL import Image

# Подключение
model = md.vl(endpoint="http://localhost:2020/v1")

# Загрузка изображения
image = Image.open("test_image.jpg")

# Запрос
result = model.query(image, "Что на этом изображении?")
print(result["answer"])
```

### Проверка через VisionProcessor

```python
import asyncio
from vision_processor import get_vision_processor

async def test():
    processor = get_vision_processor()
    result = await processor.describe_image(image_path="test_image.jpg")
    print(result)

asyncio.run(test())
```

---

## 🔍 Мониторинг

### Логи Moondream Station

Логи выводятся в консоль при запуске через скрипт.

### Проверка статуса

```bash
# Проверка, работает ли сервис
curl http://localhost:2020/health

# Или через Python
import httpx
response = httpx.get("http://localhost:2020/health")
print(response.json())
```

---

## 🐛 Устранение неполадок

### Moondream Station не запускается

1. Проверьте установку:

   ```bash
   pip list | grep moondream
   ```

2. Проверьте порт 2020:

   ```bash
   lsof -i :2020
   ```

3. Запустите с явным указанием порта:
   ```bash
   MOONDREAM_STATION_PORT=2020 moondream-station
   ```

### VisionProcessor не использует Moondream Station

1. Проверьте переменные окружения:

   ```bash
   echo $MOONDREAM_STATION_ENABLED
   echo $MOONDREAM_STATION_URL
   ```

2. Проверьте логи:

   ```bash
   grep "VISION" logs/*.log
   ```

3. Убедитесь, что Moondream Station запущен:
   ```bash
   curl http://localhost:2020/health
   ```

---

## 📚 Дополнительная информация

- **Документация Moondream:** https://docs.moondream.ai/
- **Moondream Station:** https://docs.moondream.ai/station/
- **Moondream 3 Preview:** https://moondream.ai/blog/moondream-station-m3-preview

---

## ✅ Статус

- ✅ Moondream Station установлен
- ✅ VisionProcessor обновлен для работы с MLX
- ✅ Скрипты запуска созданы
- ✅ Документация создана

**Следующий шаг:** Запустите Moondream Station и протестируйте обработку изображений!
