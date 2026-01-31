"""
File Processor
Обработка файлов (PDF, текстовые форматы) для multi-modal поддержки
Singularity 8.0: New Capabilities
"""

import asyncio
import logging
import os
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import pypdf
    PYPDF_AVAILABLE = True
except ImportError:
    try:
        import pdfplumber
        PDFPLUMBER_AVAILABLE = True
    except ImportError:
        PDFPLUMBER_AVAILABLE = False
    PYPDF_AVAILABLE = False
    logger.warning("⚠️ pypdf и pdfplumber не установлены, обработка PDF недоступна")

class FileProcessor:
    """
    Процессор файлов для извлечения текста из различных форматов.
    Поддерживает PDF, текстовые файлы.
    """
    
    def __init__(self):
        """Инициализация процессора файлов"""
        self.supported_formats = {
            '.pdf': self._process_pdf,
            '.txt': self._process_text,
            '.md': self._process_text,
            '.py': self._process_text,
            '.js': self._process_text,
            '.ts': self._process_text,
            '.json': self._process_text,
        }
    
    async def process_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Обрабатывает файл и извлекает текст.
        
        Args:
            file_path: Путь к файлу
        
        Returns:
            Словарь с извлеченным текстом и метаданными или None при ошибке
        """
        if not os.path.exists(file_path):
            logger.error(f"❌ [FILE PROCESSOR] Файл не найден: {file_path}")
            return None
        
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext not in self.supported_formats:
            logger.warning(f"⚠️ [FILE PROCESSOR] Неподдерживаемый формат: {file_ext}")
            return None
        
        try:
            processor_func = self.supported_formats[file_ext]
            result = await processor_func(file_path)
            
            if result:
                result['file_path'] = file_path
                result['file_type'] = file_ext
                result['file_size'] = os.path.getsize(file_path)
            
            return result
        except Exception as e:
            logger.error(f"❌ [FILE PROCESSOR] Ошибка обработки файла {file_path}: {e}")
            return None
    
    async def _process_pdf(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Обрабатывает PDF файл"""
        if not PYPDF_AVAILABLE and not PDFPLUMBER_AVAILABLE:
            logger.error("❌ [FILE PROCESSOR] PDF библиотеки не установлены")
            return None
        
        try:
            text_parts = []
            
            if PYPDF_AVAILABLE:
                with open(file_path, 'rb') as f:
                    pdf_reader = pypdf.PdfReader(f)
                    for page_num, page in enumerate(pdf_reader.pages):
                        text = page.extract_text()
                        if text:
                            text_parts.append(f"--- Страница {page_num + 1} ---\n{text}")
            elif PDFPLUMBER_AVAILABLE:
                import pdfplumber
                with pdfplumber.open(file_path) as pdf:
                    for page_num, page in enumerate(pdf.pages):
                        text = page.extract_text()
                        if text:
                            text_parts.append(f"--- Страница {page_num + 1} ---\n{text}")
            
            full_text = "\n\n".join(text_parts)
            
            return {
                "text": full_text,
                "page_count": len(text_parts),
                "format": "pdf"
            }
        except Exception as e:
            logger.error(f"❌ [FILE PROCESSOR] Ошибка обработки PDF: {e}")
            return None
    
    async def _process_text(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Обрабатывает текстовый файл"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
            
            return {
                "text": text,
                "line_count": len(text.split('\n')),
                "format": "text"
            }
        except UnicodeDecodeError:
            # Пробуем другие кодировки
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    text = f.read()
                return {
                    "text": text,
                    "line_count": len(text.split('\n')),
                    "format": "text"
                }
            except Exception as e:
                logger.error(f"❌ [FILE PROCESSOR] Ошибка чтения текстового файла: {e}")
                return None
        except Exception as e:
            logger.error(f"❌ [FILE PROCESSOR] Ошибка обработки текстового файла: {e}")
            return None
    
    def is_supported(self, file_path: str) -> bool:
        """
        Проверяет, поддерживается ли формат файла.
        
        Args:
            file_path: Путь к файлу
        
        Returns:
            True если формат поддерживается
        """
        file_ext = Path(file_path).suffix.lower()
        return file_ext in self.supported_formats

# Singleton instance
_file_processor_instance: Optional[FileProcessor] = None

def get_file_processor() -> FileProcessor:
    """Получить singleton экземпляр процессора файлов"""
    global _file_processor_instance
    if _file_processor_instance is None:
        _file_processor_instance = FileProcessor()
    return _file_processor_instance

