---
name: vision-processing
description: Vision Processing - анализ изображений, скриншотов и PDF через moondream и llava
category: multimodal
version: 1.0.0
author: ATRA Corporation
metadata:
  {
    "clawdbot":
      {
        "requires": { "bins": ["python"] },
        "emoji": "👁️",
        "homepage": "https://github.com/vikhyat/moondream",
      },
  }
---

# Vision Processing Skill

Навык для обработки изображений и PDF через локальные vision модели (moondream для скриншотов, llava:7b для PDF).

## Когда использовать

Используй этот навык для:

- Анализа скриншотов кода
- Обработки диаграмм и схем
- Чтения PDF документов
- Анализа изображений интерфейсов
- Обработки фотографий из Telegram

## Модели

- **moondream** (1.6 GB) - для скриншотов и изображений
- **llava:7b** (4.7 GB) - для PDF и сложных изображений

## Методология

Vision Processing работает через:

1. **Image Download** - Скачивание изображения (из Telegram, URL, файла)
2. **Base64 Encoding** - Конвертация в base64
3. **Model Selection** - Выбор модели (moondream для скриншотов, llava для PDF)
4. **Analysis** - Анализ через Vision Processor
5. **Description** - Генерация текстового описания

## Примеры использования

```
Пользователь отправляет скриншот кода в Telegram

Vision Processing:
1. Скачивание изображения
2. Конвертация в base64
3. Анализ через moondream
4. Извлечение кода и описание
5. Ответ пользователю с анализом
```

## Интеграция

- Telegram Bot: Автоматическая обработка фото/PDF
- Vision Processor: `knowledge_os/app/vision_processor.py`
- MLX API Server: Локальная обработка на Apple Silicon

## Источник

- Moondream: https://github.com/vikhyat/moondream
- LLaVA: https://llava-vl.github.io/
- Файл: `knowledge_os/app/vision_processor.py`
