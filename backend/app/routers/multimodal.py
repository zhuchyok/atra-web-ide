"""
Фаза 4, Неделя 4: API мультимодальной обработки (изображения, документы).

Маршрутизация по типу контента: image → Vision (Moondream/Ollama), document → извлечение текста.
"""

import base64
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.services.multimodal_processor import (
    detect_content_type,
    get_multimodal_processor,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class ProcessImageRequest(BaseModel):
    """Запрос на описание изображения (base64)."""
    image_base64: str = Field(..., description="Base64 изображения (или data:image/...;base64,...)")
    prompt: Optional[str] = Field(default="Опиши это изображение подробно.", max_length=2000)


class ProcessResponse(BaseModel):
    """Ответ: извлечённый/описанный текст для RAG или чата."""
    text: Optional[str] = None
    content_type: str = "unknown"
    error: Optional[str] = None


@router.post("/process-image", response_model=ProcessResponse)
async def process_image(body: ProcessImageRequest) -> ProcessResponse:
    """
    Обработка изображения через Vision (Moondream Station → Ollama).
    Возвращает текстовое описание для RAG или ответа в чате.
    """
    processor = get_multimodal_processor()
    try:
        text = await processor.process_image(
            image_base64=body.image_base64,
            prompt=body.prompt or "Опиши это изображение подробно.",
        )
        if text is None:
            return ProcessResponse(text=None, content_type="image", error="Vision unavailable or failed")
        return ProcessResponse(text=text, content_type="image")
    except Exception as e:
        logger.exception("process_image failed")
        return ProcessResponse(text=None, content_type="image", error=str(e))


@router.post("/process-document", response_model=ProcessResponse)
async def process_document(file: UploadFile = File(...)) -> ProcessResponse:
    """
    Извлечение текста из документов для RAG (PDF, DOCX, TXT, HTML, ODT, RTF и др.).
    Загрузка файла через multipart/form-data.
    """
    content_type = detect_content_type(filename=file.filename, content_type=file.content_type)
    if content_type != "document":
        raise HTTPException(400, f"Expected document (PDF/DOCX/TXT/HTML/ODT/RTF), got: {file.content_type or file.filename}")

    processor = get_multimodal_processor()
    try:
        content = await file.read()
        text = processor.extract_document_text(content=content, filename_hint=file.filename)
        if text is None:
            return ProcessResponse(
                text=None,
                content_type="document",
                error="Document extraction failed (install pymupdf for PDF, python-docx for DOCX; TXT/HTML/ODT/RTF built-in)",
            )
        return ProcessResponse(text=text[:100000], content_type="document")  # лимит для ответа
    except Exception as e:
        logger.exception("process_document failed")
        return ProcessResponse(text=None, content_type="document", error=str(e))


@router.get("/content-type")
async def get_content_type(filename: Optional[str] = None, content_type: Optional[str] = None) -> dict:
    """Определение типа контента для маршрутизации (image | document | unknown)."""
    return {"content_type": detect_content_type(filename=filename, content_type=content_type)}
