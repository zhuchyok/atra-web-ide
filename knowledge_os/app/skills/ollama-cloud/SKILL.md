---
name: ollama-cloud
description: Ollama Cloud Models - использование облачных моделей без локального GPU
category: infrastructure
version: 1.0.0
author: ATRA Corporation
metadata: {"clawdbot": {"requires": {"env": ["OLLAMA_API_KEY"]}, "emoji": "☁️", "homepage": "https://docs.ollama.com/cloud"}}
---

# Ollama Cloud Skill

Навык на основе **Ollama Cloud Models**. Использование облачных моделей без необходимости локального GPU.

## Когда использовать

Используй этот навык для:
- Запуска больших моделей без локального GPU
- Использования моделей, которые не помещаются на локальной машине
- Масштабирования на облачные ресурсы
- Доступа к новейшим облачным моделям

## Поддерживаемые Cloud модели

- **gpt-oss:120b-cloud** - 120B параметров (очень мощная)
- **gpt-oss:20b-cloud** - 20B параметров (средняя мощность)
- **qwen3-coder-cloud** - Coding модель
- **glm-4.7-cloud** - Reasoning модель

## Методология

Ollama Cloud работает через:
1. **Authentication** - Аутентификация через OLLAMA_API_KEY
2. **Model Selection** - Выбор cloud модели
3. **API Request** - Запрос к https://ollama.com API
4. **Cloud Processing** - Обработка в облаке Ollama
5. **Response** - Получение результата

## Примеры использования

```
Использование Cloud модели:

1. Установка API ключа:
   export OLLAMA_API_KEY=your_api_key

2. Использование в коде:
   client = OllamaClient(use_cloud=True)
   result = await client.generate(
       prompt="Сложная задача",
       model="gpt-oss:120b-cloud"
   )
```

## Интеграция

- OllamaClient: Поддержка `use_cloud=True`
- Переменная окружения: `OLLAMA_API_KEY`
- URL: `https://ollama.com` (Cloud API)

## Источник

- Ollama Cloud Documentation
- Файл: `backend/app/services/ollama.py`