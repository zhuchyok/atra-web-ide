---
name: firecrawl-scape
description: Веб-скрапінг та збір даних. Використовуй для надійного збору контенту з веб-сторінок, коли потрібні структуровані дані.
---

# Firecrawl Skill

## Когда использовать
- Сбор контента с веб-сайтов
- Извлечение структурированных данных
- Парсинг таблиц и списков
- Исследование конкурентов
- Сбор ценовой информации

## Установка
```bash
pip install firecrawl
```

## Использование

### CLI
```bash
# Простой scrape
firecrawl https://example.com

# Сохранить в файл
firecrawl https://example.com --format markdown -o output.md

# JSON вывод
firecrawl https://example.com --format json
```

### Python API
```python
from firecrawl import Firecrawl

app = Firecrawl()
result = app.scrape_url('https://example.com')
print(result.markdown)
```

## Особенности

### Что делает хорошо
- JavaScript рендеринг
- Cloudflare绕过
- Структурированный вывод
- Markdown формат
- JSON Schema

### Что не делает
- Не логинится (нужен отдельный код)
- Не делает скриншоты
- Ограниченная скорость

## Output форматы
- **Markdown** - для контента
- **JSON** - для данных
- **HTML** - для анализа

## Примеры

### Продуктовый анализ
```bash
firecrawl https://shop.com/products --crawl --max 20
```

### Job listings
```bash
firecrawl https://careers.example.com/jobs --json
```

###Pricing
```bash
firecrawl https://pricing.example.com --format json
```