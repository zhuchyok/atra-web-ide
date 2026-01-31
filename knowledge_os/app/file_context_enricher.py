"""
File Context Enricher - Мировые практики передачи кода экспертам

Реализует:
1. Context Window Management (chunking для больших файлов)
2. Metadata-based file references
3. Selective context injection (только релевантные части)
4. Smart file reading с кэшированием

Основано на практиках:
- LangChain Document Loaders
- AutoGPT File Context
- GitHub Copilot Context Management
"""

import os
import logging
from typing import Optional, Dict, List, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# Константы для context window management
MAX_CONTEXT_LENGTH = 8000  # Максимальная длина контекста для LLM (оставляем запас)
MAX_FILE_SIZE = 50000  # Максимальный размер файла для полного чтения (50KB)
CHUNK_SIZE = 3000  # Размер чанка для больших файлов
OVERLAP_SIZE = 200  # Перекрытие между чанками для контекста

class FileContextEnricher:
    """
    Обогащает задачи контекстом файлов по мировым практикам.
    """
    
    def __init__(self, base_path: Optional[str] = None):
        """
        Инициализация enricher.
        
        Args:
            base_path: Базовый путь к проекту (по умолчанию - корень knowledge_os)
        """
        if base_path is None:
            # Определяем базовый путь автоматически
            current_file = Path(__file__).resolve()
            # knowledge_os/app/file_context_enricher.py -> knowledge_os/
            self.base_path = current_file.parent.parent
        else:
            self.base_path = Path(base_path)
    
    def read_file_safe(self, file_path: str) -> Optional[str]:
        """
        Безопасное чтение файла с обработкой ошибок.
        
        Args:
            file_path: Путь к файлу (относительный или абсолютный)
            
        Returns:
            Содержимое файла или None при ошибке
        """
        try:
            # Пробуем относительный путь от base_path
            full_path = self.base_path / file_path
            if not full_path.exists():
                # Пробуем абсолютный путь
                full_path = Path(file_path)
                if not full_path.exists():
                    logger.warning(f"Файл не найден: {file_path}")
                    return None
            
            # Проверяем размер файла
            file_size = full_path.stat().st_size
            if file_size > MAX_FILE_SIZE * 2:  # Если файл очень большой (>100KB)
                logger.warning(f"Файл слишком большой ({file_size} байт): {file_path}, используем chunking")
                return self._read_file_chunked(full_path)
            
            # Читаем файл
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            logger.info(f"✅ Файл прочитан: {file_path} ({len(content)} символов)")
            return content
            
        except Exception as e:
            logger.error(f"Ошибка чтения файла {file_path}: {e}")
            return None
    
    def _read_file_chunked(self, file_path: Path) -> str:
        """
        Читает большой файл по частям (chunking).
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            Первые чанки файла с информацией о размере
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Читаем первые чанки
                chunks = []
                total_read = 0
                
                while total_read < MAX_CONTEXT_LENGTH and len(chunks) < 3:  # Максимум 3 чанка
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    total_read += len(chunk)
                
                content = '\n\n[...пропущено для экономии контекста...]\n\n'.join(chunks)
                
                # Добавляем информацию о размере файла
                file_size = file_path.stat().st_size
                header = f"⚠️ ФАЙЛ БОЛЬШОЙ ({file_size} байт). Показаны первые {total_read} символов:\n\n"
                
                return header + content
                
        except Exception as e:
            logger.error(f"Ошибка chunking файла {file_path}: {e}")
            return f"⚠️ Ошибка чтения файла: {e}"
    
    def extract_relevant_sections(self, content: str, keywords: List[str]) -> str:
        """
        Извлекает релевантные секции файла по ключевым словам.
        
        Args:
            content: Содержимое файла
            keywords: Ключевые слова для поиска
            
        Returns:
            Релевантные секции файла
        """
        if not keywords:
            return content
        
        lines = content.split('\n')
        relevant_lines = []
        context_before = 5  # Строк контекста до
        context_after = 10  # Строк контекста после
        
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(keyword.lower() in line_lower for keyword in keywords):
                # Добавляем контекст до и после
                start = max(0, i - context_before)
                end = min(len(lines), i + context_after + 1)
                relevant_lines.extend(lines[start:end])
                relevant_lines.append("---")  # Разделитель
        
        if relevant_lines:
            return '\n'.join(relevant_lines)
        else:
            # Если ничего не найдено, возвращаем начало файла
            return '\n'.join(lines[:100])
    
    def enrich_task_with_file_context(
        self,
        task_description: str,
        file_path: Optional[str] = None,
        metadata: Optional[Dict] = None,
        keywords: Optional[List[str]] = None
    ) -> str:
        """
        Обогащает описание задачи контекстом файла.
        
        Args:
            task_description: Исходное описание задачи
            file_path: Путь к файлу (из metadata или напрямую)
            metadata: Метаданные задачи (может содержать file_path)
            keywords: Ключевые слова для извлечения релевантных секций
            
        Returns:
            Обогащенное описание задачи
        """
        # Определяем путь к файлу
        if not file_path and metadata:
            file_path = metadata.get('file_path') or metadata.get('file')
        
        if not file_path:
            return task_description
        
        # Читаем файл
        file_content = self.read_file_safe(file_path)
        if not file_content:
            return task_description + f"\n\n⚠️ Не удалось прочитать файл: {file_path}"
        
        # Извлекаем релевантные секции если есть keywords
        if keywords:
            file_content = self.extract_relevant_sections(file_content, keywords)
        
        # Обогащаем описание
        enriched = f"""{task_description}

---
📁 КОНТЕКСТ ФАЙЛА: {file_path}
---

```python
{file_content}
```

---
💡 ИНСТРУКЦИЯ: Используй этот код для анализа и исправления. НЕ придумывай технологии, которых нет в коде!
"""
        
        # Проверяем размер контекста
        if len(enriched) > MAX_CONTEXT_LENGTH:
            logger.warning(f"Контекст слишком большой ({len(enriched)} символов), обрезаем")
            # Обрезаем до MAX_CONTEXT_LENGTH
            enriched = enriched[:MAX_CONTEXT_LENGTH] + "\n\n[...контекст обрезан для экономии...]"
        
        return enriched
    
    def enrich_task_with_multiple_files(
        self,
        task_description: str,
        file_paths: List[str],
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Обогащает задачу контекстом нескольких файлов.
        
        Args:
            task_description: Исходное описание задачи
            file_paths: Список путей к файлам
            metadata: Метаданные задачи
            
        Returns:
            Обогащенное описание задачи
        """
        enriched = task_description + "\n\n---\n📁 КОНТЕКСТ ФАЙЛОВ:\n---\n\n"
        
        total_length = len(enriched)
        
        for file_path in file_paths[:3]:  # Максимум 3 файла
            file_content = self.read_file_safe(file_path)
            if file_content:
                file_section = f"### {file_path}\n\n```python\n{file_content}\n```\n\n"
                
                # Проверяем, не превысим ли лимит
                if total_length + len(file_section) > MAX_CONTEXT_LENGTH:
                    enriched += f"\n\n[...остальные файлы пропущены для экономии контекста...]"
                    break
                
                enriched += file_section
                total_length += len(file_section)
        
        return enriched

# Глобальный экземпляр для использования в других модулях
_enricher = None

def get_file_enricher() -> FileContextEnricher:
    """Получить глобальный экземпляр FileContextEnricher."""
    global _enricher
    if _enricher is None:
        _enricher = FileContextEnricher()
    return _enricher
