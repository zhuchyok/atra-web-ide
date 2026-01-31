"""
Preview Router - Live Preview для веб-проектов
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from typing import Optional
import logging
from pathlib import Path
import mimetypes

from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


def get_safe_path(path: str) -> Path:
    """Получить безопасный путь внутри workspace"""
    workspace = Path(settings.workspace_root)
    
    if path.startswith("/"):
        path = path[1:]
    
    full_path = (workspace / path).resolve()
    
    if not str(full_path).startswith(str(workspace)):
        raise HTTPException(status_code=403, detail="Access denied")
    
    return full_path


@router.get("/")
async def preview_index() -> HTMLResponse:
    """
    Превью index.html из корня workspace
    """
    try:
        file_path = get_safe_path("index.html")
        
        if not file_path.exists():
            # Возвращаем базовый шаблон
            return HTMLResponse(content="""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ATRA Preview</title>
    <style>
        body {
            font-family: system-ui, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .container {
            text-align: center;
            padding: 2rem;
        }
        h1 { font-size: 2.5rem; margin-bottom: 1rem; }
        p { opacity: 0.8; font-size: 1.1rem; }
    </style>
</head>
<body>
    <div class="container">
        <h1>ATRA Web IDE</h1>
        <p>Create an index.html file to see your preview here</p>
    </div>
</body>
</html>
            """)
        
        content = file_path.read_text(encoding="utf-8")
        return HTMLResponse(content=content)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Preview index error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/file")
async def preview_file(
    path: str = Query(..., description="Путь к файлу")
) -> Response:
    """
    Превью любого файла с правильным content-type
    """
    try:
        file_path = get_safe_path(path)
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        if not file_path.is_file():
            raise HTTPException(status_code=400, detail="Not a file")
        
        # Определяем MIME type
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type is None:
            mime_type = "application/octet-stream"
        
        # Читаем файл
        if mime_type.startswith("text/") or mime_type in [
            "application/javascript",
            "application/json",
            "application/xml"
        ]:
            content = file_path.read_text(encoding="utf-8")
            return Response(content=content, media_type=mime_type)
        else:
            content = file_path.read_bytes()
            return Response(content=content, media_type=mime_type)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Preview file error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/html")
async def render_html(
    content: str = Query(..., description="HTML контент для рендера")
) -> HTMLResponse:
    """
    Рендер переданного HTML контента
    """
    # Базовая санитизация (в продакшене использовать bleach)
    dangerous = ["<script", "javascript:", "onerror=", "onload="]
    
    for d in dangerous:
        if d.lower() in content.lower():
            raise HTTPException(status_code=400, detail="Dangerous content detected")
    
    # Оборачиваем в базовый HTML если нужно
    if not content.strip().lower().startswith("<!doctype") and not content.strip().lower().startswith("<html"):
        content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Preview</title>
</head>
<body>
{content}
</body>
</html>
        """
    
    return HTMLResponse(content=content)
