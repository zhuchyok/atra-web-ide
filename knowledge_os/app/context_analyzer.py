"""
Context Analyzer
Семантический анализ контекста для умного сокращения
Singularity 9.0: Predictive Context Compression
"""

import asyncio
import os
import json
import logging
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np

# Import database connection from evaluator
try:
    from evaluator import get_pool
except ImportError:
    get_pool = None

logger = logging.getLogger(__name__)

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

# Import embedding function
try:
    from semantic_cache import get_embedding
except ImportError:
    get_embedding = None
    logger.warning("semantic_cache not available, context analysis will be limited")

class ContextAnalyzer:
    """
    Анализирует контекст для определения релевантных частей.
    """
    
    def __init__(self, relevance_threshold: float = 0.7):
        """
        Args:
            relevance_threshold: Порог релевантности (0.0-1.0)
        """
        self.relevance_threshold = relevance_threshold
    
    async def analyze_context_relevance(
        self,
        context: str,
        query: str
    ) -> List[Tuple[str, float]]:
        """
        Анализирует релевантность частей контекста к запросу.
        
        Args:
            context: Полный контекст
            query: Запрос пользователя
        
        Returns:
            Список (часть_контекста, релевантность) отсортированный по релевантности
        """
        if not get_embedding:
            # Fallback: простая эвристика
            return self._simple_relevance(context, query)
        
        try:
            # Получаем эмбеддинг запроса
            query_embedding = await get_embedding(query)
            if not query_embedding:
                return self._simple_relevance(context, query)
            
            # Разбиваем контекст на части (по абзацам или предложениям)
            parts = self._split_context(context)
            
            # Вычисляем релевантность каждой части
            relevant_parts = []
            for part in parts:
                if not part.strip():
                    continue
                
                part_embedding = await get_embedding(part)
                if part_embedding:
                    similarity = self._cosine_similarity(query_embedding, part_embedding)
                    if similarity >= self.relevance_threshold:
                        relevant_parts.append((part, similarity))
            
            # Сортируем по релевантности
            relevant_parts.sort(key=lambda x: x[1], reverse=True)
            
            return relevant_parts
        except Exception as e:
            logger.error(f"❌ [CONTEXT ANALYZER] Error analyzing context: {e}")
            return self._simple_relevance(context, query)
    
    def _split_context(self, context: str) -> List[str]:
        """Разбивает контекст на части (сохраняя структуру)"""
        # Разбиваем по двойным переносам строк (абзацы)
        parts = context.split('\n\n')
        
        # Если части слишком большие, разбиваем дальше
        result = []
        for part in parts:
            if len(part) > 500:
                # Разбиваем по предложениям
                sentences = part.split('. ')
                current_chunk = []
                current_length = 0
                
                for sentence in sentences:
                    if current_length + len(sentence) > 500:
                        if current_chunk:
                            result.append('. '.join(current_chunk) + '.')
                        current_chunk = [sentence]
                        current_length = len(sentence)
                    else:
                        current_chunk.append(sentence)
                        current_length += len(sentence) + 2
                
                if current_chunk:
                    result.append('. '.join(current_chunk))
            else:
                result.append(part)
        
        return result
    
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
    
    def _simple_relevance(self, context: str, query: str) -> List[Tuple[str, float]]:
        """Простая эвристика релевантности (fallback)"""
        query_words = set(query.lower().split())
        parts = self._split_context(context)
        
        relevant_parts = []
        for part in parts:
            part_words = set(part.lower().split())
            common_words = query_words.intersection(part_words)
            
            if len(query_words) > 0:
                relevance = len(common_words) / len(query_words)
                if relevance >= self.relevance_threshold:
                    relevant_parts.append((part, relevance))
        
        relevant_parts.sort(key=lambda x: x[1], reverse=True)
        return relevant_parts
    
    async def compress_context(
        self,
        context: str,
        query: str,
        max_length: int = 2000
    ) -> str:
        """
        Сжимает контекст, оставляя только релевантные части.
        
        Args:
            context: Полный контекст
            query: Запрос пользователя
            max_length: Максимальная длина сжатого контекста
        
        Returns:
            Сжатый контекст
        """
        # Анализируем релевантность
        relevant_parts = await self.analyze_context_relevance(context, query)
        
        # Собираем релевантные части до max_length
        compressed = []
        current_length = 0
        
        for part, relevance in relevant_parts:
            part_length = len(part)
            if current_length + part_length <= max_length:
                compressed.append(part)
                current_length += part_length
            else:
                # Добавляем частично, если есть место
                remaining = max_length - current_length
                if remaining > 100:  # Минимум 100 символов
                    compressed.append(part[:remaining] + "...")
                break
        
        if not compressed:
            # Если ничего не релевантно, возвращаем начало контекста
            return context[:max_length]
        
        return '\n\n'.join(compressed)
    
    async def predict_next_query(self, current_query: str, user_identifier: Optional[str] = None, limit: int = 3) -> List[str]:
        """
        Предсказывает следующие запросы на основе истории (Singularity 9.0).
        
        Args:
            current_query: Текущий запрос пользователя
            user_identifier: Идентификатор пользователя (опционально)
            limit: Количество предсказанных запросов
        
        Returns:
            Список предсказанных запросов
        """
        if not get_pool:
            return []
        
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                # Получаем историю запросов
                if user_identifier:
                    rows = await conn.fetch("""
                        SELECT user_query
                        FROM interaction_logs
                        WHERE metadata->>'user_identifier' = $1
                        ORDER BY created_at DESC
                        LIMIT 20
                    """, user_identifier)
                else:
                    rows = await conn.fetch("""
                        SELECT user_query
                        FROM interaction_logs
                        WHERE created_at > NOW() - INTERVAL '1 hour'
                        ORDER BY created_at DESC
                        LIMIT 20
                    """)
                
                if not rows:
                    return []
                
                # Анализируем паттерны последовательностей
                queries = [row['user_query'] for row in rows]
                
                # Простая эвристика: если текущий запрос похож на предыдущий, следующий вероятно связан
                predicted_queries = []
                
                # Ищем похожие запросы в истории
                current_keywords = set(re.findall(r'\b\w+\b', current_query.lower()))
                
                for i in range(len(queries) - 1):
                    query = queries[i]
                    next_query = queries[i + 1]
                    
                    query_keywords = set(re.findall(r'\b\w+\b', query.lower()))
                    common_keywords = current_keywords.intersection(query_keywords)
                    
                    # Если есть общие ключевые слова, следующий запрос вероятно релевантен
                    if len(common_keywords) > 0:
                        if next_query not in predicted_queries:
                            predicted_queries.append(next_query)
                    
                    if len(predicted_queries) >= limit:
                        break
                
                return predicted_queries[:limit]
        except Exception as e:
            logger.error(f"❌ [CONTEXT ANALYZER] Error predicting next query: {e}")
            return []
    
    async def precompress_context(self, context: str, predicted_queries: List[str], max_length: int = 2000) -> Dict[str, str]:
        """
        Предварительно сжимает контекст для предсказанных запросов (Singularity 9.0).
        
        Args:
            context: Полный контекст
            predicted_queries: Список предсказанных запросов
            max_length: Максимальная длина сжатого контекста
        
        Returns:
            Словарь {query: compressed_context}
        """
        precompressed = {}
        
        for query in predicted_queries:
            try:
                compressed = await self.compress_context(context, query, max_length)
                precompressed[query] = compressed
            except Exception as e:
                logger.debug(f"⚠️ [CONTEXT ANALYZER] Error precompressing for query '{query}': {e}")
        
        return precompressed
    
    async def get_precompressed_context(self, query: str, user_identifier: Optional[str] = None) -> Optional[str]:
        """
        Получает предсжатый контекст для запроса (Singularity 9.0).
        
        Args:
            query: Запрос пользователя
            user_identifier: Идентификатор пользователя (опционально)
        
        Returns:
            Предсжатый контекст или None, если не найден
        """
        if not get_pool:
            return None
        
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                # Проверяем, есть ли предсжатый контекст в кэше
                # Это может быть реализовано через отдельную таблицу или через semantic_cache
                # Пока используем простую проверку через semantic_cache
                row = await conn.fetchrow("""
                    SELECT response_text
                    FROM semantic_ai_cache
                    WHERE query_text = $1
                      AND metadata->>'precompressed' = 'true'
                    ORDER BY created_at DESC
                    LIMIT 1
                """, query)
                
                if row:
                    return row['response_text']
                
                return None
        except Exception as e:
            logger.debug(f"⚠️ [CONTEXT ANALYZER] Error getting precompressed context: {e}")
            return None


async def run_predictive_compression():
    """Запускает цикл предварительного сжатия контекста (Singularity 9.0)"""
    logger.info("🚀 [PREDICTIVE COMPRESSION] Starting predictive compression cycle...")
    
    if not get_pool:
        logger.warning("⚠️ [PREDICTIVE COMPRESSION] Database pool not available")
        return
    
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Получаем последние запросы пользователей
            rows = await conn.fetch("""
                SELECT DISTINCT metadata->>'user_identifier' as user_id
                FROM interaction_logs
                WHERE metadata->>'user_identifier' IS NOT NULL
                  AND created_at > NOW() - INTERVAL '1 hour'
                LIMIT 10
            """)
            
            analyzer = ContextAnalyzer()
            processed_count = 0
            
            for row in rows:
                user_id = row['user_id']
                if not user_id:
                    continue
                
                try:
                    # Получаем последний запрос пользователя
                    last_query_row = await conn.fetchrow("""
                        SELECT user_query, assistant_response
                        FROM interaction_logs
                        WHERE metadata->>'user_identifier' = $1
                        ORDER BY created_at DESC
                        LIMIT 1
                    """, user_id)
                    
                    if not last_query_row:
                        continue
                    
                    current_query = last_query_row['user_query']
                    context = last_query_row['assistant_response'] or ""
                    
                    if not context:
                        continue
                    
                    # Предсказываем следующие запросы
                    predicted_queries = await analyzer.predict_next_query(current_query, user_id, limit=3)
                    
                    if predicted_queries:
                        # Предварительно сжимаем контекст
                        precompressed = await analyzer.precompress_context(context, predicted_queries, max_length=2000)
                        
                        # Сохраняем предсжатый контекст (можно через semantic_cache или отдельную таблицу)
                        # Пока просто логируем
                        logger.info(f"✅ [PREDICTIVE COMPRESSION] Precompressed context for user {user_id}: {len(precompressed)} queries")
                        processed_count += 1
                except Exception as e:
                    logger.error(f"❌ [PREDICTIVE COMPRESSION] Error processing user {user_id}: {e}")
            
            logger.info(f"✅ [PREDICTIVE COMPRESSION] Processed {processed_count} users")
    except Exception as e:
        logger.error(f"❌ [PREDICTIVE COMPRESSION] Error in compression cycle: {e}")


if __name__ == "__main__":
    asyncio.run(run_predictive_compression())

