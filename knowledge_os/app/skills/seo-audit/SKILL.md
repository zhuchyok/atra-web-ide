---
name: seo-audit
description: Технический SEO аудит. Используй для анализа SEO оптимизации веб-сайтов, проверки мета-тегов, структуры заголовков, скорости загрузки и доступности.
---

# SEO Audit Skill

## Когда использовать

- Анализ веб-сайтов на SEO
- Проверка мета-тегов (title, description, og:)
- Аудит структуры заголовков (H1-H6)
- Оценка скорости загрузки
- Проверка accessibility и mobile-friendly
- Анализ sitemap.xml и robots.txt

## Процесс

### 1. Он-page SEO

- Проверь title (50-60 символов)
- Проверь meta description (150-160 символов)
- Проверь заголовки H1-H6
- Найди и проверь alt тексты изображений

### 2. Технический SEO

- Проверь robots.txt
- Проверь sitemap.xml
- Оцени скорость (GCF Lighthouse)
- Проверь mobile-friendly

### 3. Off-page SEO

- Проверь обратные ссылки
- Проверь социальные сигналы

## Чеклист

- [ ] Title < 60 символов
- [ ] Meta description < 160 символов
- [ ] Единственный H1
- [ ] semantic HTML
- [ ] Open Graph теги
- [ ] JSON-LD Schema
- [ ] Fast loading (<3s)
- [ ] Mobile responsive

## Output format

```json
{
  "score": 85,
  "issues": [...],
  "recommendations": [...]
}
```
