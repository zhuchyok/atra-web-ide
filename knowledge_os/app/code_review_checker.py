"""
Code Review Checker - авто-чекер перед изменениями
Концепция из agent.md: проверка на дубликаты, хардкоды, структуру перед применением изменений
"""

import logging
import re
import os
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from codebase_understanding import CodebaseUnderstanding
except ImportError:
    CodebaseUnderstanding = None


class CodeReviewChecker:
    """
    Автоматический чекер кода перед изменениями
    
    Функции:
    - Поиск дубликатов кода
    - Проверка на хардкод
    - Валидация структуры проекта
    - Предложение переиспользования
    """
    
    # Паттерны хардкода
    HARDCODE_PATTERNS = [
        r'=\s*(?:0\.\d+|1\.\d+|\d+)\s*[,\n\)]',  # Числовые константы
        r'["\'](?:localhost|127\.0\.0\.1|api\.|http://|https://)',  # URL/API endpoints
        r'["\'](?:password|secret|key|token)\s*=\s*["\'][^"\']+["\']',  # Секреты в коде
        r'if\s+.*==\s*["\'](?:test|dev|prod)["\']',  # Хардкод окружений
    ]
    
    # Паттерны временных файлов/директорий
    TEMP_FILE_PATTERNS = [
        r'temp',
        r'tmp',
        r'test_',
        r'debug',
        r'_old',
        r'_backup',
    ]
    
    def __init__(self, codebase_understanding: Optional[CodebaseUnderstanding] = None):
        """
        Инициализация чекера
        
        Args:
            codebase_understanding: Codebase Understanding модуль (опционально)
        """
        self.codebase_understanding = codebase_understanding or (
            CodebaseUnderstanding() if CodebaseUnderstanding else None
        )
    
    async def check_before_changes(
        self,
        task: str,
        affected_files: List[str]
    ) -> Dict[str, Any]:
        """
        Проверяет код перед изменениями
        
        Args:
            task: Описание задачи
            affected_files: Список файлов, которые будут изменены
        
        Returns:
            Dict[str, Any]: Результаты проверки
        """
        results = {
            'duplicates': [],
            'hardcoded_values': [],
            'structure_issues': [],
            'reuse_suggestions': [],
            'warnings': [],
        }
        
        # Проверяем каждый файл
        for file_path in affected_files:
            try:
                # Проверка на дубликаты
                duplicates = await self.find_duplicates(file_path)
                if duplicates:
                    results['duplicates'].extend(duplicates)
                
                # Проверка на хардкод
                hardcoded = await self.check_hardcoded_values(file_path)
                if hardcoded:
                    results['hardcoded_values'].extend(hardcoded)
                
                # Проверка структуры
                structure = await self.validate_structure([file_path])
                if not structure.get('valid', True):
                    results['structure_issues'].append({
                        'file': file_path,
                        'issues': structure.get('issues', [])
                    })
            except Exception as e:
                logger.debug(f"⚠️ [CODE REVIEW] Ошибка проверки {file_path}: {e}")
        
        # Предложения по переиспользованию
        if self.codebase_understanding:
            try:
                analysis = await self.codebase_understanding.analyze_existing_code(task)
                if analysis.get('recommendations'):
                    results['reuse_suggestions'] = analysis['recommendations']
            except Exception as e:
                logger.debug(f"⚠️ [CODE REVIEW] Ошибка анализа кодовой базы: {e}")
        
        logger.info(f"📋 [CODE REVIEW] Проверка завершена: найдено {len(results['duplicates'])} дубликатов, {len(results['hardcoded_values'])} хардкодов")
        
        return results
    
    async def find_duplicates(self, new_code: str) -> List[str]:
        """
        Находит дубликаты кода
        
        Args:
            new_code: Новый код (путь к файлу или содержимое)
        
        Returns:
            List[str]: Список похожих файлов
        """
        # Если это путь к файлу, читаем содержимое
        if os.path.exists(new_code):
            try:
                with open(new_code, 'r', encoding='utf-8') as f:
                    code_content = f.read()
            except Exception:
                return []
        else:
            code_content = new_code
        
        if not self.codebase_understanding:
            return []
        
        # Сканируем кодовую базу
        components = self.codebase_understanding._scan_codebase([])
        
        # Ищем похожие компоненты
        duplicates = []
        code_lower = code_content.lower()
        
        # Простой поиск по ключевым словам
        keywords = set(re.findall(r'\b\w{4,}\b', code_lower))
        
        for component in components:
            file_path = component['file']
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        existing_content = f.read().lower()
                    
                    # Проверяем совпадение ключевых слов
                    existing_keywords = set(re.findall(r'\b\w{4,}\b', existing_content))
                    overlap = len(keywords & existing_keywords)
                    
                    if overlap > 5:  # Если больше 5 общих ключевых слов
                        duplicates.append(file_path)
                except Exception:
                    pass
        
        return duplicates[:5]  # Максимум 5 дубликатов
    
    async def check_hardcoded_values(self, code: str) -> List[str]:
        """
        Проверяет код на хардкод
        
        Args:
            code: Код (путь к файлу или содержимое)
        
        Returns:
            List[str]: Список найденных хардкодов
        """
        # Если это путь к файлу, читаем содержимое
        if os.path.exists(code):
            try:
                with open(code, 'r', encoding='utf-8') as f:
                    code_content = f.read()
            except Exception:
                return []
        else:
            code_content = code
        
        hardcoded = []
        
        # Проверяем каждый паттерн
        for pattern in self.HARDCODE_PATTERNS:
            matches = re.finditer(pattern, code_content, re.IGNORECASE)
            for match in matches:
                line_num = code_content[:match.start()].count('\n') + 1
                hardcoded.append(f"Строка {line_num}: {match.group(0)[:50]}")
        
        return hardcoded[:10]  # Максимум 10 хардкодов
    
    async def validate_structure(self, files: List[str]) -> Dict[str, bool]:
        """
        Валидирует структуру проекта
        
        Args:
            files: Список файлов
        
        Returns:
            Dict[str, bool]: Результаты валидации
        """
        results = {
            'valid': True,
            'issues': [],
        }
        
        for file_path in files:
            path = Path(file_path)
            
            # Проверка на временные файлы
            file_name = path.name.lower()
            if any(pattern in file_name for pattern in self.TEMP_FILE_PATTERNS):
                results['valid'] = False
                results['issues'].append(f"Временный файл: {file_path}")
            
            # Проверка на правильную директорию
            if 'src/' not in str(path) and 'knowledge_os/' not in str(path) and 'rust-atra/' not in str(path):
                if not any(ignore in str(path) for ignore in ['tests/', 'docs/', 'scripts/']):
                    results['issues'].append(f"Файл вне стандартных директорий: {file_path}")
        
        return results

