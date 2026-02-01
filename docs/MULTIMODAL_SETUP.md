# Настройка мультимодальных компонентов (Фаза 4, Неделя 4)

Краткое руководство по подключению обработки изображений и документов в RAG/чат пайплайне.

---

## Обзор

- **Изображения:** Moondream Station (MLX) → Ollama vision (moondream, llava) для описания или ответа по изображению.
- **Документы:** PDF, DOCX, TXT, HTML, ODT, RTF (10+ форматов) — извлечение текста для RAG.
- **Маршрутизация:** по типу контента (image / document) в едином процессоре и API.

---

## Реализация

- **Сервис:** `backend/app/services/multimodal_processor.py` — `MultimodalProcessor`, `get_multimodal_processor()`.
- **API:** `POST /api/multimodal/process-image`, `POST /api/multimodal/process-document`, `GET /api/multimodal/content-type`.
- **Конфиг:** `MOONDREAM_STATION_URL`, `MULTIMODAL_VISION_ENABLED`, `MULTIMODAL_VISION_TIMEOUT`.

---

## Изображения

1. **Moondream Station (приоритет):** `http://localhost:2020` — REST API `/v1/query` с `{ "image": "<base64>", "prompt": "..." }`.
2. **Ollama fallback:** модели `moondream`, `llava:7b` через `POST /api/generate` с `images: [base64]`.
3. **Переменные:** `MOONDREAM_STATION_URL`, `MULTIMODAL_VISION_ENABLED`, `MULTIMODAL_VISION_TIMEOUT` (сек).

---

## Документы

1. **PDF:** PyMuPDF (`pip install pymupdf`) — извлечение текста по страницам.
2. **DOCX:** python-docx (`pip install python-docx`) — параграфы.
3. **Пайплайн:** загрузка файла → `extract_document_text(file_path=..., content=...)` → текст для RAG или ответа.
4. **Лимиты:** ответ API обрезается до 100 000 символов.

---

## Конфигурация

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `MOONDREAM_STATION_URL` | `http://localhost:2020` | URL Moondream Station (MLX) |
| `MULTIMODAL_VISION_ENABLED` | `true` | Включить обработку изображений |
| `MULTIMODAL_VISION_TIMEOUT` | `60.0` | Таймаут Vision-запроса (сек) |

Ollama URL берётся из `OLLAMA_URL` (общий с чатом).

---

## API

- **POST /api/multimodal/process-image** — тело: `{ "image_base64": "...", "prompt": "Опиши изображение" }`. Ответ: `{ "text": "...", "content_type": "image" }`.
- **POST /api/multimodal/process-document** — multipart: PDF, DOCX, TXT, HTML, ODT, RTF. Ответ: `{ "text": "...", "content_type": "document" }`.
- **GET /api/multimodal/content-type?filename=file.pdf** — определение типа для маршрутизации.

---

## Интеграция в пайплайн

- Чат/RAG: при получении вложения с типом image или document вызвать `get_multimodal_processor().get_text_for_rag(content_type, ...)` и подставить полученный текст в контекст или запрос.
- Определение типа: `detect_content_type(filename=..., content_type=...)` → `"image"` | `"document"` | `"unknown"`.

Подробный план — в `docs/PHASE4_PLAN.md` (Неделя 4).
