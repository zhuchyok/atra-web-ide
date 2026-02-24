# 📚 Ollama - Доступные модели и возможности

**Дата:** 2026-01-30  
**Статус:** Обзор моделей Ollama

---

## 🔄 АВТОВЫБОР МОДЕЛЕЙ (НОВОЕ!)

**Система автоматически сканирует и выбирает лучшие модели:**

- При запуске сканируются Ollama (11434) и MLX (11435)
- Выбираются самые мощные из каждого списка
- Нет необходимости указывать модель вручную

```bash
# Проверить доступные модели
curl http://localhost:11434/api/tags
curl http://localhost:11435/api/tags
```

---

## 🔍 Текущие модели в системе Mac Studio

```bash
ollama list
```

**Установлено на Mac Studio:**

- ✅ `qwq:32b` - reasoning (самая мощная)
- ✅ `qwen2.5-coder:32b` - coding
- ✅ `glm-4.7-flash:q8_0` - fast reasoning
- ✅ `llava:7b` - vision
- ✅ `phi3.5:3.8b` - fast general
- ✅ `moondream:latest` - vision small
- ✅ `tinyllama:1.1b-chat` - tiny fallback

---

## 🎯 Категории моделей Ollama

### 1. 📝 Текстовые модели (LLM)

#### Быстрые модели:

- `tinyllama:1.1b-chat` (637 MB) - ✅ **УЖЕ УСТАНОВЛЕНА**
- `phi3:mini` (2.3 GB) - быстрая, хорошее качество
- `phi3.5:3.8b` (2.5 GB) - улучшенная версия phi3
- `qwen2.5:3b` (2 GB) - хорошо понимает русский

#### Средние модели:

- `llama3.2:3b` (2 GB) - Meta Llama 3.2
- `mistral:7b` (4.1 GB) - Mistral 7B
- `gemma2:9b` (5.4 GB) - Google Gemma 2

#### Мощные модели:

- `llama3.1:8b` (4.7 GB) - Meta Llama 3.1
- `qwen2.5:7b` (4.7 GB) - Qwen 2.5
- `deepseek-r1:7b` (4.7 GB) - Reasoning модель
- `llama3.1:70b` (40 GB) - Очень мощная

---

### 2. 🖼️ Vision модели (Multimodal)

#### Для обработки изображений:

- `moondream` (1.6 GB) - ⚠️ **НЕ УСТАНОВЛЕНА** - анализ изображений
- `llava:7b` (4.7 GB) - LLaVA - vision-language модель
- `llava:13b` (7.3 GB) - более мощная версия
- `qwen2.5-vl:7b` (4.7 GB) - Qwen 2.5 Vision-Language
- `gemma3:9b` (5.4 GB) - Google Gemma 3 с vision

#### Новые мощные vision модели (2025):

- `llama4:scout` (109B MoE) - Meta Llama 4 Scout
- `llama4:maverick` (400B MoE) - Meta Llama 4 Maverick
- `qwen3-vl` - самый мощный vision-language модель в семействе Qwen

---

### 3. 📄 Модели для работы с документами

#### PDF и документы:

**⚠️ Важно:** Ollama не имеет специальных моделей ТОЛЬКО для PDF, но:

1. **Vision модели могут читать PDF:**
   - `llava:7b` - может анализировать изображения страниц PDF
   - `qwen2.5-vl:7b` - может обрабатывать документы
   - `gemma3:9b` - поддерживает множественные изображения

2. **Специализированные инструменты:**
   - **olmOCR** - отдельный инструмент для PDF (не модель Ollama)
   - Использует vision-language модели для обработки PDF

#### Как работать с PDF в Ollama:

**Вариант 1: Конвертировать PDF в изображения**

```bash
# Конвертировать PDF в изображения страниц
# Затем использовать vision модель:
ollama run llava:7b "Опиши это изображение" < page1.png
```

**Вариант 2: Использовать текстовые модели с извлеченным текстом**

```bash
# Извлечь текст из PDF (через pdftotext или подобное)
# Затем использовать текстовую модель:
ollama run llama3.1:8b "Проанализируй этот документ: [текст]"
```

---

### 4. 💻 Coding модели

- `qwen2.5-coder:7b` (4.7 GB) - для программирования
- `qwen2.5-coder:32b` (20 GB) - более мощная версия
- `deepseek-coder:6.7b` (3.8 GB) - DeepSeek Coder
- `codellama:7b` (3.8 GB) - Code Llama

---

### 5. 🧠 Reasoning модели

- `deepseek-r1:7b` (4.7 GB) - для сложных рассуждений
- `deepseek-r1:32b` (20 GB) - более мощная версия
- `llama3.1:70b` (40 GB) - для сложных задач

---

## 📊 Рекомендуемые модели для ваших задач

### Для обработки скриншотов:

```bash
ollama pull moondream        # 1.6 GB - быстрая, легкая
# или
ollama pull llava:7b         # 4.7 GB - более мощная
```

### Для чтения PDF:

```bash
# Vision модель для анализа страниц PDF как изображений
ollama pull llava:7b         # 4.7 GB
# или
ollama pull qwen2.5-vl:7b    # 4.7 GB - лучше для документов
```

### Для текстовых задач:

```bash
ollama pull phi3.5:3.8b      # 2.5 GB - быстрая
ollama pull qwen2.5:7b        # 4.7 GB - хорошо понимает русский
ollama pull llama3.1:8b       # 4.7 GB - мощная
```

---

## 🚀 Как установить модели

```bash
# Установить модель
ollama pull <model-name>

# Примеры:
ollama pull moondream
ollama pull llava:7b
ollama pull qwen2.5-vl:7b
ollama pull phi3.5:3.8b
```

---

## 📚 Полный список моделей

Посмотреть все доступные модели:

- **Онлайн:** https://ollama.com/library
- **Фильтр по vision:** https://ollama.com/library?q=vision
- **Фильтр по multimodal:** https://ollama.com/library?q=multimodal

---

## ⚠️ Важно для PDF

**Ollama не имеет встроенной поддержки PDF напрямую!**

Для работы с PDF нужно:

1. Конвертировать PDF в изображения (страницы)
2. Использовать vision модель для анализа
3. Или извлечь текст и использовать текстовую модель

**Альтернатива:** Использовать специализированные инструменты:

- **olmOCR** - для массовой обработки PDF
- **PyPDF2** / **pdfplumber** - для извлечения текста
- Затем использовать Ollama для анализа текста

---

## ✅ Итог

**Текущее состояние:**

- ✅ 1 модель установлена: `tinyllama:1.1b-chat`
- ⚠️ Нет vision моделей (нужна `moondream` или `llava`)
- ⚠️ Нет моделей для PDF (нужны vision модели)

**Рекомендации:**

1. Установить `moondream` для скриншотов
2. Установить `llava:7b` или `qwen2.5-vl:7b` для PDF
3. Установить `phi3.5:3.8b` для текстовых задач
