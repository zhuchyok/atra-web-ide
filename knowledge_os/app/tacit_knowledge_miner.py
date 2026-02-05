"""
Tacit Knowledge Miner: Извлечение неявных стилевых предпочтений пользователя

Функционал:
- Анализ паттернов из interaction_logs и knowledge_nodes
- Извлечение стилевых предпочтений (naming conventions, error handling, testing style)
- Создание стилевого профиля пользователя
- Генерация кода в стиле пользователя
"""

import asyncio
import os
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import numpy as np

# Import database connection from evaluator
from evaluator import get_pool

# Import embedding function from semantic_cache
try:
    from semantic_cache import get_embedding
except ImportError:
    get_embedding = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

# Минимальное количество взаимодействий для создания профиля
MIN_INTERACTIONS_FOR_PROFILE = 10

# Порог similarity для стилевого совпадения
STYLE_SIMILARITY_THRESHOLD = 0.85


@dataclass
class StyleProfile:
    """Стилевой профиль пользователя"""
    user_identifier: str
    style_vector: List[float]  # Embedding вектор стиля
    preferences: Dict[str, any]  # {naming_convention, error_handling, testing_style, ...}
    similarity_score: float  # Cosine similarity с эталонным стилем
    created_at: datetime
    updated_at: datetime


class TacitKnowledgeMiner:
    """Класс для извлечения неявных стилевых предпочтений"""
    
    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url
    
    async def extract_style_patterns(self, user_identifier: str) -> Optional[Dict[str, any]]:
        """
        Извлекает стилевые паттерны из истории взаимодействий пользователя.
        
        Args:
            user_identifier: Идентификатор пользователя (из metadata->>'user_identifier')
        
        Returns:
            Словарь с предпочтениями стиля или None, если недостаточно данных
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Получаем все взаимодействия пользователя с кодом
            interactions = await conn.fetch("""
                SELECT 
                    il.user_query,
                    il.assistant_response,
                    il.metadata,
                    il.created_at
                FROM interaction_logs il
                WHERE il.metadata->>'user_identifier' = $1
                  AND (il.user_query ILIKE '%def %' 
                       OR il.user_query ILIKE '%class %'
                       OR il.assistant_response ILIKE '%def %'
                       OR il.assistant_response ILIKE '%class %')
                ORDER BY il.created_at DESC
                LIMIT 100
            """, user_identifier)
            
            if len(interactions) < MIN_INTERACTIONS_FOR_PROFILE:
                logger.debug(f"Insufficient interactions for user {user_identifier}: {len(interactions)}")
                return None
            
            # Анализируем паттерны
            code_samples = []
            for interaction in interactions:
                # Извлекаем код из ответа
                code = self._extract_code(interaction['assistant_response'])
                if code:
                    code_samples.append(code)
            
            if not code_samples:
                return None
            
            # Анализируем стилевые предпочтения
            preferences = {
                'naming_convention': self._detect_naming_convention(code_samples),
                'error_handling': self._detect_error_handling_style(code_samples),
                'testing_style': self._detect_testing_style(code_samples),
                'documentation_style': self._detect_documentation_style(code_samples),
                'code_structure': self._detect_code_structure(code_samples),
                'variable_naming': self._detect_variable_naming(code_samples),
                'function_style': self._detect_function_style(code_samples)
            }
            
            # Создаем текстовое представление стиля для embedding
            style_text = self._create_style_text(preferences)
            
            # Генерируем embedding вектора стиля
            style_vector = None
            if get_embedding:
                try:
                    style_vector = await get_embedding(style_text)
                except Exception as e:
                    logger.error(f"Error generating embedding: {e}")
            
            if not style_vector:
                # Fallback: создаем простой вектор на основе предпочтений
                style_vector = self._create_fallback_vector(preferences)
            
            return {
                'preferences': preferences,
                'style_vector': style_vector,
                'style_text': style_text,
                'code_samples_count': len(code_samples)
            }
    
    def _extract_code(self, text: str) -> Optional[str]:
        """Извлекает код из текста (Python блоки в markdown)"""
        # Ищем блоки кода в markdown
        code_pattern = r'```(?:python)?\n(.*?)```'
        matches = re.findall(code_pattern, text, re.DOTALL)
        if matches:
            return '\n'.join(matches)
        
        # Если нет markdown, ищем блоки с def/class
        lines = text.split('\n')
        code_lines = []
        in_code = False
        for line in lines:
            if line.strip().startswith(('def ', 'class ', 'import ', 'from ')):
                in_code = True
            if in_code:
                code_lines.append(line)
            if in_code and line.strip() == '':
                break
        
        return '\n'.join(code_lines) if code_lines else None
    
    def _detect_naming_convention(self, code_samples: List[str]) -> str:
        """Определяет конвенцию именования (snake_case, camelCase, etc.)"""
        snake_case_count = 0
        camel_case_count = 0
        
        for code in code_samples:
            # Ищем определения функций и переменных
            functions = re.findall(r'def\s+([a-zA-Z_][a-zA-Z0-9_]*)', code)
            variables = re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*=', code)
            
            for name in functions + variables:
                if '_' in name:
                    snake_case_count += 1
                elif name[0].islower() and any(c.isupper() for c in name[1:]):
                    camel_case_count += 1
        
        if snake_case_count > camel_case_count * 2:
            return 'snake_case'
        elif camel_case_count > snake_case_count * 2:
            return 'camelCase'
        else:
            return 'snake_case'  # По умолчанию
    
    def _detect_error_handling_style(self, code_samples: List[str]) -> str:
        """Определяет стиль обработки ошибок"""
        try_except_count = 0
        if_checks_count = 0
        no_handling_count = 0
        
        for code in code_samples:
            if 'try:' in code or 'except' in code:
                try_except_count += 1
            elif 'if' in code and ('error' in code.lower() or 'none' in code.lower()):
                if_checks_count += 1
            else:
                no_handling_count += 1
        
        total = len(code_samples)
        if try_except_count / total > 0.3:
            return 'defensive_with_exceptions'
        elif if_checks_count / total > 0.3:
            return 'defensive_with_checks'
        else:
            return 'minimal'  # По умолчанию
    
    def _detect_testing_style(self, code_samples: List[str]) -> str:
        """Определяет стиль тестирования"""
        test_patterns = {
            'pytest': r'(pytest|@pytest)',
            'unittest': r'(unittest|TestCase)',
            'assert': r'assert\s+'
        }
        
        test_counts = {key: 0 for key in test_patterns}
        for code in code_samples:
            for test_type, pattern in test_patterns.items():
                if re.search(pattern, code, re.IGNORECASE):
                    test_counts[test_type] += 1
        
        if test_counts['pytest'] > 0:
            return 'tdd_with_pytest'
        elif test_counts['unittest'] > 0:
            return 'tdd_with_unittest'
        elif test_counts['assert'] > 0:
            return 'basic_asserts'
        else:
            return 'minimal'  # По умолчанию
    
    def _detect_documentation_style(self, code_samples: List[str]) -> str:
        """Определяет стиль документации"""
        docstring_count = 0
        comment_count = 0
        
        for code in code_samples:
            if '"""' in code or "'''" in code:
                docstring_count += 1
            if '#' in code:
                comment_count += 1
        
        total = len(code_samples)
        if docstring_count / total > 0.3:
            return 'detailed_docstrings'
        elif comment_count / total > 0.3:
            return 'inline_comments'
        else:
            return 'minimal'  # По умолчанию
    
    def _detect_code_structure(self, code_samples: List[str]) -> str:
        """Определяет структуру кода"""
        class_count = 0
        function_count = 0
        
        for code in code_samples:
            class_count += len(re.findall(r'class\s+', code))
            function_count += len(re.findall(r'def\s+', code))
        
        total_functions = function_count
        total_classes = class_count
        
        if total_classes > 0 and total_classes / (total_functions + total_classes) > 0.3:
            return 'oop_oriented'
        else:
            return 'functional'  # По умолчанию
    
    def _detect_variable_naming(self, code_samples: List[str]) -> str:
        """Определяет стиль именования переменных"""
        descriptive_count = 0
        short_count = 0
        
        for code in code_samples:
            variables = re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*=', code)
            for var in variables:
                if len(var) > 10:
                    descriptive_count += 1
                elif len(var) <= 3:
                    short_count += 1
        
        if descriptive_count > short_count * 2:
            return 'descriptive_names'
        elif short_count > descriptive_count * 2:
            return 'short_names'
        else:
            return 'balanced'  # По умолчанию
    
    def _detect_function_style(self, code_samples: List[str]) -> str:
        """Определяет стиль функций"""
        async_count = 0
        generator_count = 0
        simple_count = 0
        
        for code in code_samples:
            functions = re.findall(r'(?:async\s+)?def\s+([a-zA-Z_][a-zA-Z0-9_]*)', code)
            for func_def in re.findall(r'def\s+[^:]+:', code):
                if 'async' in func_def:
                    async_count += 1
                elif 'yield' in code:
                    generator_count += 1
                else:
                    simple_count += 1
        
        total = async_count + generator_count + simple_count
        if total == 0:
            return 'simple'
        
        if async_count / total > 0.3:
            return 'async_heavy'
        elif generator_count / total > 0.3:
            return 'generator_heavy'
        else:
            return 'simple'  # По умолчанию
    
    def _create_style_text(self, preferences: Dict[str, any]) -> str:
        """Создает текстовое представление стиля для embedding"""
        style_parts = []
        for key, value in preferences.items():
            style_parts.append(f"{key}: {value}")
        return "; ".join(style_parts)
    
    def _create_fallback_vector(self, preferences: Dict[str, any]) -> List[float]:
        """Создает простой вектор на основе предпочтений (fallback)"""
        # Размер 768 = nomic-embed-text; knowledge_nodes.embedding vector(768)
        vector = [0.0] * 768
        style_text = self._create_style_text(preferences)
        
        for i, char in enumerate(style_text):
            idx = (i * ord(char)) % 768
            vector[idx] += ord(char) / 1000.0
        
        # Нормализуем вектор
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = [v / norm for v in vector]
        
        return vector
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Вычисляет косинусное сходство между векторами"""
        try:
            v1 = np.array(vec1)
            v2 = np.array(vec2)
            
            dot_product = np.dot(v1, v2)
            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            return float(dot_product / (norm1 * norm2))
        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {e}")
            return 0.0
    
    async def get_style_profile(self, user_identifier: str) -> Optional[StyleProfile]:
        """Получает стилевой профиль пользователя из БД"""
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT 
                    id,
                    user_identifier,
                    style_vector,
                    preferences,
                    similarity_score,
                    created_at,
                    updated_at
                FROM user_style_profiles
                WHERE user_identifier = $1
                ORDER BY updated_at DESC
                LIMIT 1
            """, user_identifier)
            
            if not row:
                return None
            
            return StyleProfile(
                user_identifier=row['user_identifier'],
                style_vector=row['style_vector'] or [],
                preferences=row['preferences'] or {},
                similarity_score=float(row['similarity_score'] or 0.0),
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
    
    async def save_style_profile(self, user_identifier: str, style_data: Dict[str, any]) -> Optional[str]:
        """Сохраняет стилевой профиль пользователя в БД"""
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Проверяем, существует ли профиль
            existing = await conn.fetchrow("""
                SELECT id FROM user_style_profiles WHERE user_identifier = $1
            """, user_identifier)
            
            if existing:
                # Обновляем существующий профиль
                await conn.execute("""
                    UPDATE user_style_profiles
                    SET style_vector = $1,
                        preferences = $2,
                        updated_at = NOW()
                    WHERE user_identifier = $3
                """, style_data['style_vector'], json.dumps(style_data['preferences']), user_identifier)
                profile_id = str(existing['id'])
            else:
                # Создаем новый профиль
                profile_id = await conn.fetchval("""
                    INSERT INTO user_style_profiles 
                    (user_identifier, style_vector, preferences, similarity_score)
                    VALUES ($1, $2, $3, $4)
                    RETURNING id
                """, 
                user_identifier,
                style_data['style_vector'],
                json.dumps(style_data['preferences']),
                0.0  # similarity_score будет вычислен позже
                )
                profile_id = str(profile_id) if profile_id else None
            
            logger.info(f"✅ Saved style profile for user {user_identifier}: {profile_id}")
            return profile_id
    
    async def calculate_style_similarity(self, generated_code: str, user_identifier: str) -> float:
        """
        Вычисляет similarity между сгенерированным кодом и стилем пользователя.
        
        Args:
            generated_code: Сгенерированный код
            user_identifier: Идентификатор пользователя
        
        Returns:
            Cosine similarity (0.0-1.0)
        """
        # Получаем профиль пользователя
        profile = await self.get_style_profile(user_identifier)
        if not profile or not profile.style_vector:
            return 0.0
        
        # Извлекаем стиль из сгенерированного кода
        generated_style = self._extract_code(generated_code)
        if not generated_style:
            return 0.0
        
        # Анализируем стиль сгенерированного кода
        code_samples = [generated_style]
        preferences = {
            'naming_convention': self._detect_naming_convention(code_samples),
            'error_handling': self._detect_error_handling_style(code_samples),
            'testing_style': self._detect_testing_style(code_samples),
            'documentation_style': self._detect_documentation_style(code_samples),
            'code_structure': self._detect_code_structure(code_samples),
            'variable_naming': self._detect_variable_naming(code_samples),
            'function_style': self._detect_function_style(code_samples)
        }
        
        # Создаем embedding вектора для сгенерированного стиля
        style_text = self._create_style_text(preferences)
        generated_vector = None
        
        if get_embedding:
            try:
                generated_vector = await get_embedding(style_text)
            except Exception as e:
                logger.error(f"Error generating embedding for similarity: {e}")
        
        if not generated_vector:
            generated_vector = self._create_fallback_vector(preferences)
        
        # Вычисляем cosine similarity
        similarity = self._cosine_similarity(profile.style_vector, generated_vector)
        
        return similarity


async def update_style_profiles():
    """Обновляет стилевые профили для всех пользователей"""
    logger.info("🎨 Starting style profile update...")
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        # Получаем уникальных пользователей
        users = await conn.fetch("""
            SELECT DISTINCT metadata->>'user_identifier' as user_id
            FROM interaction_logs
            WHERE metadata->>'user_identifier' IS NOT NULL
            LIMIT 50
        """)
        
        miner = TacitKnowledgeMiner()
        updated_count = 0
        
        for user_row in users:
            user_id = user_row['user_id']
            if not user_id:
                continue
            
            try:
                # Извлекаем стилевые паттерны
                style_data = await miner.extract_style_patterns(user_id)
                if style_data:
                    # Сохраняем профиль
                    await miner.save_style_profile(user_id, style_data)
                    updated_count += 1
                    logger.info(f"✅ Updated style profile for user {user_id}")
            except Exception as e:
                logger.error(f"❌ Error updating style profile for user {user_id}: {e}")
        
        logger.info(f"✅ Updated {updated_count} style profiles")


if __name__ == "__main__":
    asyncio.run(update_style_profiles())

