# ✅ РЕАЛИЗАЦИЯ: Передача кода экспертам по мировым практикам

**Дата:** 2026-01-28  
**Статус:** ✅ **РЕАЛИЗОВАНО**

---

## 🎯 ПРОБЛЕМА

Эксперты не видели реальный код дашборда и давали примеры для технологий, которых нет в системе (например, популярные технологии из общих знаний, но не используемые в проекте).

---

## ✅ РЕШЕНИЕ (МИРОВЫЕ ПРАКТИКИ)

### 1. **File Context Enricher** (`knowledge_os/app/file_context_enricher.py`)

Реализует лучшие практики:

- ✅ **Context Window Management** - chunking для больших файлов
- ✅ **Metadata-based file references** - пути к файлам в metadata
- ✅ **Selective context injection** - только релевантные части
- ✅ **Smart file reading** - безопасное чтение с обработкой ошибок

**Основано на:**

- LangChain Document Loaders
- AutoGPT File Context
- GitHub Copilot Context Management

### 2. **Обновлен Smart Worker** (`knowledge_os/app/smart_worker_autonomous.py`)

**Изменения:**

- ✅ Автоматическое чтение файлов из `metadata.file_path`
- ✅ Обогащение описания задачи кодом файла
- ✅ Поддержка нескольких файлов через `metadata.file_paths`
- ✅ Извлечение релевантных секций по keywords

**Код:**

```python
# Автоматически читаем файлы из metadata
from file_context_enricher import get_file_enricher
enricher = get_file_enricher()

file_path = task_metadata.get('file_path')
if file_path:
    task_description = enricher.enrich_task_with_file_context(
        task_description,
        file_path=file_path,
        metadata=task_metadata,
        keywords=keywords
    )
```

### 3. **Обновлен Code Auditor** (`knowledge_os/app/code_auditor.py`)

**Изменения:**

- ✅ Автоматическое извлечение `file_path` из описания задачи
- ✅ Добавление `file_path` в `metadata` при создании задачи
- ✅ Извлечение keywords для selective context

**Паттерны поиска:**

- `Местоположение: app.py`
- `файл: app.py`
- `file: app.py`
- Автоматическое определение для dashboard → `knowledge_os/dashboard/app.py`

---

## 📋 КАК ЭТО РАБОТАЕТ

### Поток обработки задачи:

```
1. Code Auditor создает задачу
   └─> Извлекает file_path из описания
   └─> Добавляет в metadata: {"file_path": "knowledge_os/dashboard/app.py"}

2. Smart Worker берет задачу
   └─> Читает metadata.file_path
   └─> Вызывает FileContextEnricher
   └─> Читает файл (с chunking если большой)
   └─> Обогащает описание задачи кодом

3. Эксперт получает промпт:
   └─> system_prompt (роль)
   └─> title (название задачи)
   └─> description (обогащенное с кодом файла)
   └─> Инструкции о работе с кодом

4. Эксперт видит РЕАЛЬНЫЙ КОД и анализирует его
```

---

## 🔧 КОНФИГУРАЦИЯ

### Константы (file_context_enricher.py):

```python
MAX_CONTEXT_LENGTH = 8000  # Максимальная длина контекста для LLM
MAX_FILE_SIZE = 50000      # Максимальный размер файла (50KB)
CHUNK_SIZE = 3000          # Размер чанка для больших файлов
OVERLAP_SIZE = 200         # Перекрытие между чанками
```

### Metadata задачи:

```json
{
  "file_path": "knowledge_os/dashboard/app.py",
  "keywords": ["error", "except", "connection"],
  "source": "code_auditor",
  "severity": "high"
}
```

---

## 📊 ПРИМЕРЫ

### Пример 1: Задача dashboard_audit

**До:**

```
Задача: "Исправить ошибки в дашборде"
Описание: "Местоположение: app.py - все табы"
```

**После:**

````
Задача: "Исправить ошибки в дашборде"
Описание: "Местоположение: app.py - все табы

---
📁 КОНТЕКСТ ФАЙЛА: knowledge_os/dashboard/app.py
---

```python
import streamlit as st
import psycopg2
# ... реальный код файла ...
VECTOR_CORE_URL = "http://localhost:8001"
def get_embedding(text: str) -> list:
    # ... реальный код ...
````

```

### Пример 2: Большой файл (chunking)

Если файл > 50KB:
```

⚠️ ФАЙЛ БОЛЬШОЙ (120000 байт). Показаны первые 8000 символов:

```python
# ... первые чанки ...
[...пропущено для экономии контекста...]
```

````

---

## 🎯 РЕЗУЛЬТАТЫ

### ✅ Что исправлено:

1. **Эксперты видят реальный код** - не работают "вслепую"
2. **Нет галлюцинаций** - эксперты не придумывают технологии
3. **Selective context** - только релевантные части больших файлов
4. **Context window management** - автоматический chunking

### ✅ Что улучшено:

1. **Автоматическое извлечение file_path** из описания задачи
2. **Умное чтение файлов** с обработкой ошибок
3. **Инструкции экспертам** о работе с кодом
4. **Поддержка нескольких файлов**

---

## 📚 МИРОВЫЕ ПРАКТИКИ

### 1. **Context Window Management**
- ✅ Chunking для больших файлов
- ✅ Ограничение размера контекста (8000 символов)
- ✅ Перекрытие между чанками для контекста

### 2. **Metadata-based References**
- ✅ Пути к файлам в metadata, не в description
- ✅ Гибкость: один файл или несколько
- ✅ Keywords для selective extraction

### 3. **Selective Context Injection**
- ✅ Извлечение релевантных секций по keywords
- ✅ Контекст до/после найденных строк
- ✅ Fallback на начало файла если ничего не найдено

### 4. **Error Handling**
- ✅ Безопасное чтение с обработкой ошибок
- ✅ Fallback на базовое описание при ошибках
- ✅ Логирование для отладки

---

## 🚀 ИСПОЛЬЗОВАНИЕ

### Создание задачи с file_path:

```python
task_metadata = {
    "file_path": "knowledge_os/dashboard/app.py",
    "keywords": ["error", "except"],
    "source": "code_auditor"
}

await conn.execute("""
    INSERT INTO tasks (title, description, metadata)
    VALUES ($1, $2, $3)
""", "Исправить ошибки", "Описание задачи", json.dumps(task_metadata))
````

### Несколько файлов:

```python
task_metadata = {
    "file_paths": [
        "knowledge_os/dashboard/app.py",
        "knowledge_os/app/main.py"
    ],
    "source": "code_auditor"
}
```

---

## 📝 ДОКУМЕНТАЦИЯ

- `file_context_enricher.py` - основной модуль
- `smart_worker_autonomous.py` - интеграция
- `code_auditor.py` - извлечение file_path

---

**Дата реализации:** 2026-01-28  
**Автор:** ATRA Corporation (Victoria Agent)  
**Статус:** ✅ **ГОТОВО К ИСПОЛЬЗОВАНИЮ**
