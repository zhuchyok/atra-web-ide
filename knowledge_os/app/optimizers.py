"""
Оптимизации для экономии токенов, улучшения интеллекта и скорости
Singularity 5.0: Advanced Optimizations
"""

import asyncio
import logging
from typing import List, Dict, Optional, Any, Tuple
import hashlib
import json

logger = logging.getLogger(__name__)

class PromptOptimizer:
    """
    Оптимизация промптов для экономии токенов
    """
    
    @staticmethod
    def compress_prompt(prompt: str, max_length: int = 2000) -> str:
        """Сжатие промпта до максимальной длины"""
        if len(prompt) <= max_length:
            return prompt
        
        # Удаляем лишние пробелы
        prompt = " ".join(prompt.split())
        
        # Если все еще длинный, обрезаем
        if len(prompt) > max_length:
            # Обрезаем с сохранением структуры
            prompt = prompt[:max_length-50] + "...\n[Текст обрезан для экономии токенов]"
        
        return prompt
    
    @staticmethod
    def remove_redundancy(prompt: str) -> str:
        """Удаление избыточности из промпта"""
        lines = prompt.split('\n')
        seen = set()
        result = []
        
        for line in lines:
            line_stripped = line.strip()
            # Пропускаем пустые строки и дубликаты
            if line_stripped and line_stripped not in seen:
                seen.add(line_stripped)
                result.append(line)
        
        return '\n'.join(result)

class BatchProcessor:
    """
    Batch processing для множественных запросов (экономия токенов)
    """
    
    def __init__(self):
        self.batch_queue = []
        self.batch_size = 5
        self.batch_timeout = 2.0  # секунды
    
    async def add_to_batch(self, prompt: str, category: str) -> str:
        """Добавляет запрос в batch и возвращает результат"""
        # Для простых запросов можно объединить
        if len(self.batch_queue) < self.batch_size:
            self.batch_queue.append((prompt, category))
            # Ждем накопления batch или timeout
            await asyncio.sleep(self.batch_timeout)
        
        # Обрабатываем batch
        if self.batch_queue:
            return await self._process_batch()
        return None
    
    async def _process_batch(self) -> str:
        """Обработка batch запросов"""
        # Объединяем запросы в один промпт
        combined_prompt = "\n\n".join([f"Запрос {i+1}: {p[0]}" for i, p in enumerate(self.batch_queue)])
        
        # Очищаем очередь
        self.batch_queue = []
        
        # Обрабатываем объединенный запрос
        # (здесь должна быть логика обработки)
        return combined_prompt

class PredictiveCache:
    """
    Предсказательное кэширование - пред-генерирует ответы на вероятные запросы.
    Анализирует календарь/историю для предсказания запросов.
    """
    
    def __init__(self, cache_manager, db_url: Optional[str] = None):
        self.cache = cache_manager
        self.prediction_queue = []
        self.db_url = db_url or os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')
        self.query_patterns = {}  # Паттерны запросов для анализа
        self._background_task_running = False  # Флаг для отслеживания фоновой задачи
        
        # Импорт для работы с БД
        try:
            import asyncpg
            self.asyncpg = asyncpg
        except ImportError:
            self.asyncpg = None
        
    
    async def analyze_query_history(self, hours: int = 24) -> Dict[str, Any]:
        """Анализирует историю запросов для выявления паттернов"""
        if not self.asyncpg or not self.db_url:
            return {}
        
        try:
            conn = await self.asyncpg.connect(self.db_url)
            try:
                # Получаем последние запросы из semantic_ai_cache с группировкой по пользователю/сессии
                rows = await conn.fetch("""
                    SELECT query_text, created_at, expert_name
                    FROM semantic_ai_cache
                    WHERE created_at > NOW() - INTERVAL '1 hour' * $1
                    ORDER BY created_at ASC
                    LIMIT 200
                """, hours)
                
                if not rows:
                    return {}
                
                # Анализируем паттерны
                patterns = {
                    "keywords": {},  # Частота ключевых слов
                    "sequences": {},  # Последовательности запросов
                    "contexts": {},  # Контекстные паттерны (что идет вместе)
                    "temporal": {},  # Временные паттерны
                    "categories": {}  # Категории запросов
                }
                
                queries = []
                for row in rows:
                    query = row['query_text'].lower()
                    queries.append({
                        'text': query,
                        'timestamp': row['created_at'],
                        'expert': row.get('expert_name', 'unknown')
                    })
                    
                    # Извлекаем ключевые слова
                    keywords = self._extract_keywords(query)
                    for keyword in keywords:
                        patterns["keywords"][keyword] = patterns["keywords"].get(keyword, 0) + 1
                    
                    # Определяем категорию
                    category = self._categorize_query(query)
                    patterns["categories"][category] = patterns["categories"].get(category, 0) + 1
                
                # Анализ последовательностей (что следует после чего)
                for i in range(len(queries) - 1):
                    current = queries[i]
                    next_query = queries[i + 1]
                    
                    # Проверяем, что запросы близки по времени (в пределах 10 минут)
                    time_diff = (next_query['timestamp'] - current['timestamp']).total_seconds()
                    if time_diff < 600:  # 10 минут
                        current_keywords = self._extract_keywords(current['text'])
                        next_keywords = self._extract_keywords(next_query['text'])
                        
                        # Создаем паттерн последовательности
                        if current_keywords and next_keywords:
                            pattern_key = f"{current_keywords[0]} -> {next_keywords[0]}"
                            patterns["sequences"][pattern_key] = patterns["sequences"].get(pattern_key, 0) + 1
                
                # Анализ контекстных паттернов (запросы в одной сессии)
                expert_queries = {}
                for query in queries:
                    expert = query['expert']
                    if expert not in expert_queries:
                        expert_queries[expert] = []
                    expert_queries[expert].append(query)
                
                for expert, expert_qs in expert_queries.items():
                    if len(expert_qs) >= 2:
                        # Анализируем, какие ключевые слова часто идут вместе
                        for i in range(len(expert_qs) - 1):
                            for j in range(i + 1, min(i + 3, len(expert_qs))):  # Следующие 2 запроса
                                keywords_i = set(self._extract_keywords(expert_qs[i]['text']))
                                keywords_j = set(self._extract_keywords(expert_qs[j]['text']))
                                common = keywords_i & keywords_j
                                if common:
                                    context_key = " & ".join(sorted(common))
                                    patterns["contexts"][context_key] = patterns["contexts"].get(context_key, 0) + 1
                
                # Временные паттерны (день недели, час дня)
                for query in queries:
                    timestamp = query['timestamp']
                    day_of_week = timestamp.strftime('%A')
                    hour = timestamp.hour
                    
                    time_key = f"{day_of_week}_{hour}"
                    patterns["temporal"][time_key] = patterns["temporal"].get(time_key, 0) + 1
                
                return patterns
            finally:
                await conn.close()
        except Exception as e:
            logger.warning(f"⚠️ Ошибка анализа истории запросов: {e}")
            return {}
    
    def _categorize_query(self, query: str) -> str:
        """Определяет категорию запроса"""
        query_lower = query.lower()
        
        if any(kw in query_lower for kw in ["код", "функция", "класс", "программируй"]):
            return "coding"
        elif any(kw in query_lower for kw in ["ошибка", "баг", "исправить", "проблема"]):
            return "error"
        elif any(kw in query_lower for kw in ["тест", "проверка", "валидация"]):
            return "testing"
        elif any(kw in query_lower for kw in ["объясни", "что такое", "как работает"]):
            return "explanation"
        elif any(kw in query_lower for kw in ["оптимизац", "улучш", "рефакторинг"]):
            return "optimization"
        else:
            return "general"
    
    def _extract_keywords(self, query: str) -> List[str]:
        """Извлекает ключевые слова из запроса"""
        # Простая эвристика: ищем технические термины
        tech_keywords = [
            "код", "функция", "класс", "тест", "ошибка", "баг", "рефакторинг",
            "оптимизация", "производительность", "архитектура", "дизайн",
            "база данных", "api", "endpoint", "миграция", "деплой"
        ]
        
        found_keywords = []
        for keyword in tech_keywords:
            if keyword in query:
                found_keywords.append(keyword)
        
        return found_keywords
    
    async def predict_next_queries(self, current_query: str) -> List[str]:
        """Предсказывает следующие запросы на основе текущего и истории с улучшенным анализом паттернов"""
        predictions = []
        query_lower = current_query.lower()
        
        # Анализ истории для выявления паттернов
        history_patterns = await self.analyze_query_history(hours=24)
        
        # Извлекаем ключевые слова из текущего запроса
        current_keywords = self._extract_keywords(current_query)
        current_category = self._categorize_query(current_query)
        
        # 1. Предсказания на основе последовательностей из истории
        if history_patterns.get("sequences"):
            sequences = history_patterns["sequences"]
            # Ищем последовательности, начинающиеся с текущих ключевых слов
            for seq_key, count in sorted(sequences.items(), key=lambda x: x[1], reverse=True)[:5]:
                if " -> " in seq_key:
                    start_keyword, next_keyword = seq_key.split(" -> ", 1)
                    if any(kw in current_query.lower() for kw in [start_keyword]):
                        # Генерируем предсказание на основе следующего ключевого слова
                        predictions.append(f"пример использования {next_keyword}")
        
        # 2. Предсказания на основе контекстных паттернов
        if history_patterns.get("contexts"):
            contexts = history_patterns["contexts"]
            # Ищем контексты, которые часто идут вместе с текущими ключевыми словами
            for context_key, count in sorted(contexts.items(), key=lambda x: x[1], reverse=True)[:3]:
                context_keywords = context_key.split(" & ")
                # Если есть пересечение с текущими ключевыми словами
                if any(kw in current_keywords for kw in context_keywords):
                    # Предсказываем запросы с другими ключевыми словами из контекста
                    for kw in context_keywords:
                        if kw not in current_keywords:
                            predictions.append(f"как использовать {kw}")
        
        # 3. Предсказания на основе категорий (что обычно следует после этой категории)
        category_transitions = {
            "coding": ["тест", "оптимизация", "документация", "рефакторинг"],
            "error": ["исправить", "причина", "предотвратить", "логирование"],
            "testing": ["запустить", "покрытие", "еще тесты", "интеграция"],
            "explanation": ["пример", "детали", "использование", "лучшие практики"],
            "optimization": ["измерить", "профилирование", "бенчмарки", "альтернативы"]
        }
        
        if current_category in category_transitions:
            for next_action in category_transitions[current_category]:
                predictions.append(f"{next_action} для этого")
        
        # 4. Базовые предсказания на основе текущего запроса (fallback)
        if "код" in query_lower or "функция" in query_lower:
            predictions.extend([
                "напиши тест для этого кода",
                "как оптимизировать этот код",
                "какой сложности этот код",
                "как улучшить читаемость этого кода"
            ])
        
        if "ошибка" in query_lower or "баг" in query_lower:
            predictions.extend([
                "как исправить эту ошибку",
                "в чем причина этой ошибки",
                "как предотвратить эту ошибку в будущем"
            ])
        
        if "тест" in query_lower:
            predictions.extend([
                "как запустить этот тест",
                "как улучшить покрытие тестами",
                "какие еще тесты нужны"
            ])
        
        # 5. Предсказания на основе топ ключевых слов из истории
        if history_patterns.get("keywords"):
            top_keywords = sorted(history_patterns["keywords"].items(), key=lambda x: x[1], reverse=True)[:3]
            for keyword, count in top_keywords:
                if keyword not in current_keywords and count >= 3:  # Минимум 3 использования
                    predictions.append(f"пример использования {keyword}")
        
        # 6. Временные паттерны (анализ времени дня)
        from datetime import datetime
        current_time = datetime.now()
        current_hour = current_time.hour
        day_of_week = current_time.strftime('%A')
        
        if history_patterns.get("temporal"):
            temporal = history_patterns["temporal"]
            # Ищем паттерны для текущего времени
            time_key = f"{day_of_week}_{current_hour}"
            similar_time_keys = [k for k in temporal.keys() if k.startswith(day_of_week)]
            
            if similar_time_keys:
                # Если есть паттерны для этого дня недели, используем их
                pass  # Можно добавить специфичные предсказания
        
        if 6 <= current_hour < 12:  # Утро
            predictions.extend([
                "какие задачи на сегодня",
                "какой план работы",
                "какие приоритеты"
            ])
        elif 18 <= current_hour < 22:  # Вечер
            predictions.extend([
                "какие результаты за день",
                "что сделано сегодня",
                "какие проблемы возникли"
            ])
        
        # Удаляем дубликаты и ограничиваем количество
        unique_predictions = []
        seen = set()
        for pred in predictions:
            pred_lower = pred.lower()
            if pred_lower not in seen:
                seen.add(pred_lower)
                unique_predictions.append(pred)
        
        return unique_predictions[:5]  # Ограничиваем до 5 предсказаний
    
    async def predict_and_cache(self, current_query: str, expert_name: str):
        """Предсказывает следующие запросы и пред-кэширует ответы"""
        predictions = await self.predict_next_queries(current_query)
        
        # Пред-кэшируем в фоновом режиме
        for pred_query in predictions:
            # Проверяем, нет ли уже в кэше
            cached = await self.cache.get_cached_response(pred_query, expert_name)
            if not cached:
                # Добавляем в очередь для пред-генерации (выполняется в фоне)
                self.prediction_queue.append((pred_query, expert_name))
        
        # Запускаем фоновую задачу для пред-генерации
        if self.prediction_queue:
            asyncio.create_task(self._warm_cache_background())
        
        return len(predictions)
    
    async def _warm_cache_background(self):
        """Фоновая задача для пред-генерации ответов"""
        while self.prediction_queue:
            pred_query, expert_name = self.prediction_queue.pop(0)
            try:
                # Генерируем ответ через ai_core
                from ai_core import run_smart_agent_async
                response = await run_smart_agent_async(pred_query, expert_name=expert_name)
                
                if response:
                    # Сохраняем в кэш
                    await self.cache.save_to_cache(pred_query, response, expert_name)
                    logger.debug(f"✅ [PREDICTIVE CACHE] Пред-кэширован ответ для: {pred_query[:50]}...")
            except Exception as e:
                logger.warning(f"⚠️ [PREDICTIVE CACHE] Ошибка пред-кэширования: {e}")

class ResponseStreamer:
    """
    Стриминг ответов для улучшения воспринимаемой скорости
    """
    
    @staticmethod
    async def stream_response(response: str, chunk_size: int = 50):
        """Стриминг ответа по частям"""
        words = response.split()
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i+chunk_size])
            yield chunk
            await asyncio.sleep(0.05)  # Небольшая задержка для восприятия

class SmartRouter:
    """
    Умный роутер для выбора оптимального пути (экономия токенов + скорость)
    """
    
    def __init__(self):
        self.route_cache = {}  # Кэш решений роутинга
    
    async def choose_optimal_route(
        self, 
        prompt: str, 
        category: Optional[str] = None,
        history: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Выбирает оптимальный маршрут на основе:
        - Сложности запроса
        - Истории запросов
        - Доступности узлов
        - Ожидаемой экономии токенов
        """
        # Простая эвристика для начала
        route = {
            "use_local": True,
            "use_web": False,
            "use_cache": True,
            "expected_tokens": 0,
            "expected_latency": 0.5
        }
        
        # Определяем сложность
        complexity = self._estimate_complexity(prompt, category)
        
        if complexity == "simple":
            route["use_local"] = True
            route["expected_tokens"] = 0
            route["expected_latency"] = 0.3
        elif complexity == "medium":
            route["use_local"] = True
            route["use_web"] = any(kw in prompt.lower() for kw in ["новости", "тренды", "сейчас"])
            route["expected_tokens"] = 0
            route["expected_latency"] = 1.0
        else:  # complex
            route["use_local"] = False  # Используем облако для сложных задач
            route["expected_tokens"] = 2000
            route["expected_latency"] = 3.0
        
        return route
    
    def _estimate_complexity(self, prompt: str, category: Optional[str]) -> str:
        """Оценка сложности запроса"""
        simple_keywords = ["объясни", "что такое", "как работает", "пример"]
        complex_keywords = ["архитектура", "стратегия", "проектирование", "дизайн"]
        
        prompt_lower = prompt.lower()
        
        if any(kw in prompt_lower for kw in complex_keywords):
            return "complex"
        elif any(kw in prompt_lower for kw in simple_keywords):
            return "simple"
        else:
            return "medium"

class EmbeddingCache:
    """
    Кэш эмбеддингов для ускорения семантического поиска
    """
    
    def __init__(self, db_url: str):
        self.db_url = db_url
        self.memory_cache = {}  # In-memory кэш
        self.cache_size = 1000
    
    async def get_or_compute_embedding(self, text: str) -> List[float]:
        """Получает эмбеддинг из кэша или вычисляет"""
        # Хэш текста для ключа
        text_hash = hashlib.md5(text.encode()).hexdigest()
        
        # Проверяем memory cache
        if text_hash in self.memory_cache:
            return self.memory_cache[text_hash]
        
        # Вычисляем эмбеддинг (здесь должна быть логика)
        # embedding = await compute_embedding(text)
        
        # Сохраняем в кэш
        if len(self.memory_cache) >= self.cache_size:
            # Удаляем старые (FIFO)
            oldest_key = next(iter(self.memory_cache))
            del self.memory_cache[oldest_key]
        
        # self.memory_cache[text_hash] = embedding
        # return embedding
        
        return []  # Placeholder

class ParallelProcessor:
    """
    Параллельная обработка для ускорения
    """
    
    def __init__(self, max_concurrent: int = 3):
        """
        Args:
            max_concurrent: Максимальное количество одновременных задач
        """
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_parallel(self, tasks: List[Any]) -> List[Any]:
        """
        Параллельная обработка задач с контролем нагрузки.
        
        Args:
            tasks: Список async функций для выполнения
        
        Returns:
            Список результатов
        """
        async def process_with_semaphore(task):
            async with self.semaphore:
                return await task
        
        results = await asyncio.gather(*[process_with_semaphore(task) for task in tasks], return_exceptions=True)
        
        # Обрабатываем исключения
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"❌ [PARALLEL] Task {i} failed: {result}")
                processed_results.append(None)
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def process_batch_parallel(
        self,
        prompts: List[str],
        expert_name: str,
        category: Optional[str] = None
    ) -> List[str]:
        """
        Параллельная обработка множественных промптов.
        
        Args:
            prompts: Список промптов
            expert_name: Имя эксперта
            category: Категория задачи
        
        Returns:
            Список результатов
        """
        from ai_core import run_smart_agent_async
        
        # Создаем задачи
        tasks = [
            run_smart_agent_async(prompt, expert_name=expert_name, category=category)
            for prompt in prompts
        ]
        
        # Обрабатываем параллельно
        return await self.process_parallel(tasks)

class FrugalPrompt:
    """
    FrugalPrompt - улучшенная техника сжатия промптов на основе мировых практик 2024-2025.
    Удаляет избыточность, сжимает инструкции, оптимизирует структуру.
    """
    
    # Шаблоны для замены длинных инструкций на короткие
    INSTRUCTION_PATTERNS = {
        # Длинные инструкции -> короткие эквиваленты
        r'пожалуйста\s+(?:будьте\s+)?(?:уверены|убедитесь|убедись)\s+что': 'убедись:',
        r'я\s+хочу\s+чтобы\s+ты\s+': 'сделай:',
        r'можешь\s+(?:ли\s+ты\s+)?(?:пожалуйста\s+)?': '',
        r'если\s+возможно[,\s]*': '',
        r'\s+и\s+также\s+': ', ',
        r'\s+в\s+дополнение\s+к\s+': '+',
        r'пожалуйста\s+': '',
        r'\s+очень\s+': ' ',
        r'\s+действительно\s+': ' ',
        r'\s+на самом деле\s+': ' ',
    }
    
    # Стоп-слова для удаления
    STOP_WORDS = {
        'конечно', 'разумеется', 'безусловно', 'очевидно', 'понятно',
        'ясно', 'естественно', 'конечно же', 'разумеется же'
    }
    
    @staticmethod
    def compress_instruction(instruction: str) -> str:
        """Сжимает одну инструкцию, удаляя избыточность"""
        import re
        compressed = instruction.strip().lower()
        
        # Заменяем длинные паттерны на короткие
        for pattern, replacement in FrugalPrompt.INSTRUCTION_PATTERNS.items():
            compressed = re.sub(pattern, replacement, compressed, flags=re.IGNORECASE)
        
        # Удаляем стоп-слова
        words = compressed.split()
        words = [w for w in words if w.lower() not in FrugalPrompt.STOP_WORDS]
        compressed = ' '.join(words)
        
        # Удаляем множественные пробелы
        compressed = re.sub(r'\s+', ' ', compressed)
        
        return compressed.strip()
    
    @staticmethod
    def remove_boilerplate(prompt: str) -> str:
        """Удаляет шаблонные части из промпта"""
        lines = prompt.split('\n')
        filtered = []
        
        # Удаляем строки с типичными шаблонами
        boilerplate_patterns = [
            r'^(здравствуйте|привет|добрый\s+(?:день|вечер|утро))',
            r'^(спасибо|благодарю|благодарность)',
            r'^(надеюсь|надеемся)\s+',
            r'^(с\s+уважением|с\s+наилучшими\s+пожеланиями)',
        ]
        
        import re
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue
            
            is_boilerplate = False
            for pattern in boilerplate_patterns:
                if re.match(pattern, line_stripped, re.IGNORECASE):
                    is_boilerplate = True
                    break
            
            if not is_boilerplate:
                filtered.append(line)
        
        return '\n'.join(filtered)
    
    @staticmethod
    def compress_structure(prompt: str) -> str:
        """Оптимизирует структуру промпта"""
        # Разделяем на части
        sections = prompt.split('\n\n')
        compressed_sections = []
        
        for section in sections:
            section = section.strip()
            if not section:
                continue
            
            # Если секция начинается с маркера списка, оптимизируем
            if any(section.startswith(marker) for marker in ['-', '*', '•', '1.', '2.']):
                # Компрессия списков
                lines = section.split('\n')
                compressed_lines = []
                for line in lines:
                    compressed_line = FrugalPrompt.compress_instruction(line)
                    if compressed_line:
                        compressed_lines.append(compressed_line)
                section = '\n'.join(compressed_lines)
            else:
                section = FrugalPrompt.compress_instruction(section)
            
            if section:
                compressed_sections.append(section)
        
        return '\n\n'.join(compressed_sections)
    
    @classmethod
    def compress(cls, prompt: str, max_length: int = 2000, aggressive: bool = True) -> str:
        """
        Основной метод сжатия промпта по технике FrugalPrompt.
        
        Args:
            prompt: Исходный промпт
            max_length: Максимальная длина
            aggressive: Агрессивное сжатие (удаляет больше)
        
        Returns:
            Сжатый промпт
        """
        if len(prompt) <= max_length and not aggressive:
            return prompt
        
        # Шаг 1: Удаление boilerplate
        compressed = cls.remove_boilerplate(prompt)
        
        # Шаг 2: Компрессия структуры
        compressed = cls.compress_structure(compressed)
        
        # Шаг 3: Удаление избыточности (как в PromptOptimizer)
        compressed = PromptOptimizer.remove_redundancy(compressed)
        
        # Шаг 4: Финальное сжатие до max_length
        if len(compressed) > max_length:
            # Если все еще длинный, применяем более агрессивное сжатие
            compressed = PromptOptimizer.compress_prompt(compressed, max_length)
        
        return compressed

class BETokenManager:
    """
    BE-Token (Behavior-Equivalent Token) Manager.
    Заменяет длинные инструкции одним токеном/шаблоном для экономии токенов.
    """
    
    # Словарь BE-Token: токен -> полная инструкция
    _token_map: Dict[str, str] = {}
    
    # Словарь обратный: паттерн -> токен
    _pattern_map: Dict[str, str] = {}
    
    # Статистика использования токенов
    _usage_stats: Dict[str, int] = {}
    
    def __init__(self):
        """Инициализация с базовыми токенами"""
        self._initialize_base_tokens()
    
    def _initialize_base_tokens(self):
        """Инициализация базовых BE-Token"""
        base_tokens = {
            # Торговля
            'TRADE_SIGNAL': 'проанализируй рынок и выдай торговый сигнал с entry/tp/sl',
            'BACKTEST': 'проведи бэктест стратегии на исторических данных',
            'RISK_ANALYSIS': 'рассчитай риски и position sizing',
            
            # Программирование
            'CODE_REVIEW': 'проведи code review и найди проблемы',
            'WRITE_TEST': 'напиши unit-тесты для функции',
            'REFACTOR': 'отрефакторь код для улучшения читаемости',
            'OPTIMIZE': 'оптимизируй производительность кода',
            'FIX_BUG': 'найди и исправь баг',
            
            # Документация
            'WRITE_DOCS': 'напиши документацию для функции/класса',
            'EXPLAIN': 'объясни как работает код',
            
            # Общее
            'ANALYZE': 'проанализируй и выдай выводы',
            'SUMMARIZE': 'кратко суммируй основное',
        }
        
        for token, instruction in base_tokens.items():
            self.register_token(token, instruction)
    
    def register_token(self, token: str, instruction: str, pattern: Optional[str] = None):
        """
        Регистрирует новый BE-Token.
        
        Args:
            token: Название токена (например, 'TRADE_SIGNAL')
            instruction: Полная инструкция
            pattern: Опциональный паттерн для распознавания (если None, использует instruction)
        """
        self._token_map[token] = instruction
        pattern_key = pattern or instruction.lower()
        self._pattern_map[pattern_key] = token
        self._usage_stats[token] = 0
    
    def find_token(self, prompt: str) -> Optional[str]:
        """
        Ищет подходящий BE-Token для промпта.
        
        Args:
            prompt: Промпт пользователя
        
        Returns:
            Название токена или None
        """
        prompt_lower = prompt.lower()
        
        # Ищем точные совпадения паттернов
        for pattern, token in self._pattern_map.items():
            if pattern in prompt_lower:
                self._usage_stats[token] = self._usage_stats.get(token, 0) + 1
                return token
        
        # Ищем частичные совпадения (если паттерн содержит ключевые слова)
        for token, instruction in self._token_map.items():
            instruction_words = set(instruction.lower().split())
            prompt_words = set(prompt_lower.split())
            
            # Если >50% слов совпадают, считаем совпадением
            common_words = instruction_words.intersection(prompt_words)
            if len(instruction_words) > 0:
                similarity = len(common_words) / len(instruction_words)
                if similarity >= 0.5:
                    self._usage_stats[token] = self._usage_stats.get(token, 0) + 1
                    return token
        
        return None
    
    def replace_with_token(self, prompt: str) -> Tuple[str, Optional[str]]:
        """
        Заменяет промпт на BE-Token, если подходящий найден.
        
        Args:
            prompt: Исходный промпт
        
        Returns:
            (сжатый_промпт, токен_или_None)
        """
        token = self.find_token(prompt)
        if token:
            # Заменяем длинную инструкцию на короткий токен
            compressed = f"[BE:{token}] {prompt}"  # Сохраняем оригинал для контекста
            return compressed, token
        return prompt, None
    
    def expand_token(self, token: str) -> Optional[str]:
        """
        Разворачивает BE-Token обратно в полную инструкцию.
        
        Args:
            token: Название токена
        
        Returns:
            Полная инструкция или None
        """
        return self._token_map.get(token)
    
    def get_usage_stats(self) -> Dict[str, int]:
        """Возвращает статистику использования токенов"""
        return self._usage_stats.copy()
    
    def learn_from_history(self, prompts: List[str], instructions: List[str]):
        """
        Обучение BE-Token на основе истории запросов.
        Автоматически создает новые токены для часто используемых паттернов.
        
        Args:
            prompts: Список промптов
            instructions: Список соответствующих инструкций
        """
        # Простой анализ: находим общие паттерны в инструкциях
        from collections import Counter
        
        instruction_counts = Counter()
        for instruction in instructions:
            instruction_counts[instruction.lower()] += 1
        
        # Если инструкция встречается >= 3 раза, создаем токен
        for instruction, count in instruction_counts.items():
            if count >= 3 and len(instruction) > 50:  # Длинные инструкции
                token_name = f"CUSTOM_{count}_{hash(instruction) % 10000}"
                if token_name not in self._token_map:
                    self.register_token(token_name, instruction)
                    logger.info(f"📝 [BE-TOKEN] Автоматически создан токен: {token_name}")

# Singleton instance для BETokenManager
_betoken_manager = None

def get_betoken_manager() -> BETokenManager:
    """Получает singleton instance BETokenManager"""
    global _betoken_manager
    if _betoken_manager is None:
        _betoken_manager = BETokenManager()
    return _betoken_manager

# Экспорт всех оптимизаторов
__all__ = [
    'PromptOptimizer',
    'FrugalPrompt',
    'BETokenManager',
    'get_betoken_manager',
    'BatchProcessor',
    'PredictiveCache',
    'ResponseStreamer',
    'SmartRouter',
    'EmbeddingCache',
    'ParallelProcessor'
]

