"""
Files Router - Файловые операции (Улучшенная версия)
Безопасность, валидация, обработка ошибок
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
import os
import logging
from pathlib import Path
import shutil

from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


class FileInfo(BaseModel):
    """Информация о файле"""
    name: str
    path: str
    type: str  # "file" или "directory"
    size: Optional[int] = None
    modified: Optional[str] = None


class FileContent(BaseModel):
    """Содержимое файла"""
    path: str
    content: str
    encoding: str = "utf-8"


class WriteFileRequest(BaseModel):
    """Запрос на запись файла"""
    content: str = Field(..., min_length=0, max_length=settings.max_file_size)
    encoding: str = Field(default="utf-8", pattern="^(utf-8|utf-16|ascii|latin-1)$")
    
    @field_validator('content')
    @classmethod
    def validate_content_size(cls, v: str) -> str:
        """Проверка размера контента"""
        if len(v.encode('utf-8')) > settings.max_file_size:
            raise ValueError(f"Content size exceeds maximum {settings.max_file_size} bytes")
        return v


class CreateRequest(BaseModel):
    """Запрос на создание файла/папки"""
    type: str = Field(..., pattern="^(file|directory)$")
    content: Optional[str] = Field(default=None, max_length=settings.max_file_size)
    
    @field_validator('content')
    @classmethod
    def validate_content(cls, v: Optional[str], info) -> Optional[str]:
        """Проверка контента"""
        if info.data.get('type') == 'file' and v is None:
            v = ""  # Пустой файл по умолчанию
        return v


def get_safe_path(path: str) -> Path:
    """
    Получить безопасный путь внутри workspace
    
    Args:
        path: Путь к файлу/директории
    
    Returns:
        Path объект
    
    Raises:
        HTTPException: Если путь небезопасен
    """
    workspace = Path(settings.workspace_root)
    
    # Создаём workspace если не существует
    workspace.mkdir(parents=True, exist_ok=True)
    
    # Нормализуем путь
    if path.startswith("/"):
        path = path[1:]
    
    # Убираем .. и другие опасные символы
    path = os.path.normpath(path).lstrip('/')
    
    # Проверяем на попытку выхода за пределы workspace
    if ".." in path or path.startswith("/"):
        raise HTTPException(
            status_code=403,
            detail="Access denied: invalid path"
        )
    
    full_path = (workspace / path).resolve()
    
    # Проверяем что путь внутри workspace
    try:
        full_path.relative_to(workspace.resolve())
    except ValueError:
        raise HTTPException(
            status_code=403,
            detail="Access denied: path outside workspace"
        )
    
    return full_path


def validate_file_extension(path: Path) -> None:
    """Проверить разрешение файла"""
    if path.is_file():
        ext = path.suffix.lower()
        if ext and ext not in settings.allowed_file_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"File extension '{ext}' is not allowed. Allowed: {', '.join(settings.allowed_file_extensions)}"
            )


@router.get("/list", response_model=List[FileInfo])
async def list_files(
    path: str = Query(default="", description="Путь к директории", max_length=500)
) -> List[FileInfo]:
    """
    Список файлов в директории
    
    Returns:
        Список файлов и директорий
    """
    try:
        dir_path = get_safe_path(path)
        
        if not dir_path.exists():
            return []
        
        if not dir_path.is_dir():
            raise HTTPException(
                status_code=400,
                detail="Path is not a directory"
            )
        
        files = []
        for item in sorted(dir_path.iterdir()):
            try:
                stat = item.stat()
                files.append(FileInfo(
                    name=item.name,
                    path=str(item.relative_to(Path(settings.workspace_root))),
                    type="directory" if item.is_dir() else "file",
                    size=stat.st_size if item.is_file() else None,
                    modified=str(stat.st_mtime)
                ))
            except (OSError, PermissionError) as e:
                logger.warning(f"Cannot access {item}: {e}")
                continue
        
        return files
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List files error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error while listing files"
        )


@router.get("/read", response_model=FileContent)
async def read_file(
    path: str = Query(..., description="Путь к файлу", max_length=500)
) -> FileContent:
    """
    Прочитать файл
    
    Returns:
        Содержимое файла
    """
    try:
        file_path = get_safe_path(path)
        
        if not file_path.exists():
            raise HTTPException(
                status_code=404,
                detail="File not found"
            )
        
        if not file_path.is_file():
            raise HTTPException(
                status_code=400,
                detail="Path is not a file"
            )
        
        # Проверка размера файла
        file_size = file_path.stat().st_size
        if file_size > settings.max_file_size:
            raise HTTPException(
                status_code=413,
                detail=f"File too large: {file_size} bytes (max: {settings.max_file_size})"
            )
        
        # Читаем содержимое
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=400,
                detail="Cannot read binary file as text"
            )
        except Exception as e:
            logger.error(f"Read file error: {e}")
            raise HTTPException(
                status_code=500,
                detail="Error reading file"
            )
        
        return FileContent(
            path=path,
            content=content,
            encoding="utf-8"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Read file error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error while reading file"
        )


@router.post("/write")
async def write_file(
    path: str = Query(..., description="Путь к файлу", max_length=500),
    request: WriteFileRequest = None
) -> dict:
    """
    Записать файл
    
    Returns:
        Результат записи
    """
    if request is None:
        raise HTTPException(
            status_code=400,
            detail="Request body is required"
        )
    
    try:
        file_path = get_safe_path(path)
        
        # Проверяем расширение
        validate_file_extension(file_path)
        
        # Создаём родительские директории
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Записываем
        try:
            file_path.write_text(request.content, encoding=request.encoding)
        except Exception as e:
            logger.error(f"Write file error: {e}")
            raise HTTPException(
                status_code=500,
                detail="Error writing file"
            )
        
        return {
            "success": True,
            "path": path,
            "size": len(request.content.encode(request.encoding))
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Write file error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error while writing file"
        )


@router.post("/create")
async def create_item(
    path: str = Query(..., description="Путь", max_length=500),
    request: CreateRequest = None
) -> dict:
    """
    Создать файл или папку
    
    Returns:
        Результат создания
    """
    if request is None:
        raise HTTPException(
            status_code=400,
            detail="Request body is required"
        )
    
    try:
        item_path = get_safe_path(path)
        
        if item_path.exists():
            raise HTTPException(
                status_code=409,
                detail="Path already exists"
            )
        
        if request.type == "directory":
            item_path.mkdir(parents=True, exist_ok=True)
        else:
            # Проверяем расширение для файлов
            validate_file_extension(item_path)
            item_path.parent.mkdir(parents=True, exist_ok=True)
            item_path.write_text(request.content or "", encoding="utf-8")
        
        return {
            "success": True,
            "path": path,
            "type": request.type
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error while creating item"
        )


@router.delete("/delete")
async def delete_item(
    path: str = Query(..., description="Путь", max_length=500)
) -> dict:
    """
    Удалить файл или папку
    
    Returns:
        Результат удаления
    """
    try:
        item_path = get_safe_path(path)
        
        if not item_path.exists():
            raise HTTPException(
                status_code=404,
                detail="Path not found"
            )
        
        # Защита от удаления workspace root
        workspace = Path(settings.workspace_root).resolve()
        if item_path.resolve() == workspace:
            raise HTTPException(
                status_code=403,
                detail="Cannot delete workspace root"
            )
        
        try:
            if item_path.is_dir():
                shutil.rmtree(item_path)
            else:
                item_path.unlink()
        except (OSError, PermissionError) as e:
            logger.error(f"Delete error: {e}")
            raise HTTPException(
                status_code=500,
                detail="Error deleting item"
            )
        
        return {
            "success": True,
            "path": path
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error while deleting item"
        )


@router.post("/rename")
async def rename_item(
    old_path: str = Query(..., description="Старый путь", max_length=500),
    new_path: str = Query(..., description="Новый путь", max_length=500)
) -> dict:
    """
    Переименовать файл или папку
    
    Returns:
        Результат переименования
    """
    try:
        old = get_safe_path(old_path)
        new = get_safe_path(new_path)
        
        if not old.exists():
            raise HTTPException(
                status_code=404,
                detail="Source not found"
            )
        
        if new.exists():
            raise HTTPException(
                status_code=409,
                detail="Destination already exists"
            )
        
        # Проверяем расширение для файлов
        if old.is_file():
            validate_file_extension(new)
        
        new.parent.mkdir(parents=True, exist_ok=True)
        old.rename(new)
        
        return {
            "success": True,
            "old_path": old_path,
            "new_path": new_path
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Rename error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error while renaming item"
        )
