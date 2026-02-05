"""
Вероника: Локальная модель с веб-поиском
Интеграция локальных моделей с веб-поиском без использования токенов
Singularity 5.0: Web-Enabled Local Intelligence
"""

import asyncio
import logging
import os
from typing import Optional, List, Dict, Any
import httpx

# DuckDuckGo search with fallback
try:
    from duckduckgo_search import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS = None
    DDGS_AVAILABLE = False

logger = logging.getLogger(__name__)

# Config: в Docker используем host.docker.internal
_is_docker = os.path.exists('/.dockerenv') or os.getenv('DOCKER_CONTAINER', 'false').lower() == 'true'
if _is_docker:
    _default_ollama = os.getenv('OLLAMA_API_URL') or os.getenv('OLLAMA_BASE_URL') or 'http://host.docker.internal:11434'
    _default_mlx = os.getenv('MLX_API_URL') or 'http://host.docker.internal:11435'
else:
    _default_ollama = os.getenv('MAC_LLM_URL') or os.getenv('OLLAMA_API_URL') or 'http://localhost:11434'
    _default_mlx = os.getenv('MLX_API_URL') or 'http://localhost:11435'

MAC_LLM_URL = os.getenv('MAC_LLM_URL') or _default_ollama
SERVER_LLM_URL = os.getenv('SERVER_LLM_URL') or os.getenv('OLLAMA_API_URL') or _default_ollama

class VeronicaWebResearcher:
    """
    Вероника: Локальная модель с возможностью веб-поиска.
    Работает без токенов, используя локальные модели на Mac Studio.
    """
    
    def __init__(self):
        ollama_url = MAC_LLM_URL or SERVER_LLM_URL or _default_ollama
        mlx_url = os.getenv('MLX_API_URL') or _default_mlx
        self.nodes = [
            {"name": "Mac Studio (Ollama)", "url": ollama_url, "priority": 1},
            {"name": "Mac Studio (MLX)", "url": mlx_url, "priority": 2}
        ]
    
    async def web_search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Веб-поиск через DuckDuckGo (без токенов).
        """
        if not DDGS_AVAILABLE:
            logger.warning("⚠️ [WEB SEARCH] duckduckgo_search не установлен. Установите: pip install duckduckgo-search")
            return []
        
        try:
            logger.info(f"🔍 [WEB SEARCH] Вероника ищет: {query}")
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
            
            formatted_results = []
            for res in results:
                formatted_results.append({
                    "title": res.get('title', ''),
                    "url": res.get('href', ''),
                    "snippet": res.get('body', ''),
                    "source": "duckduckgo"
                })
            
            logger.info(f"✅ [WEB SEARCH] Найдено {len(formatted_results)} результатов")
            return formatted_results
        except Exception as e:
            logger.error(f"❌ [WEB SEARCH] Ошибка: {e}")
            return []
    
    async def process_with_local_model(
        self, 
        prompt: str, 
        web_results: Optional[List[Dict]] = None,
        category: str = "research"
    ) -> str:
        """
        Обработка запроса локальной моделью (без токенов).
        Может использовать результаты веб-поиска.
        """
        # Выбираем лучший узел
        healthy_node = await self._get_healthy_node()
        if not healthy_node:
            return "❌ Нет доступных локальных моделей"
        
        # Формируем промпт с веб-результатами
        full_prompt = prompt
        if web_results:
            full_prompt += "\n\n📚 РЕЗУЛЬТАТЫ ВЕБ-ПОИСКА:\n"
            for i, result in enumerate(web_results[:3], 1):
                full_prompt += f"\n{i}. {result['title']}\n"
                full_prompt += f"   URL: {result['url']}\n"
                full_prompt += f"   {result['snippet'][:200]}...\n"
            full_prompt += "\nИспользуй эту информацию для ответа.\n"
        
        # Выбираем модель в зависимости от категории (MLX модели Mac Studio)
        model_map = {
            "research": "deepseek-r1-distill-llama:70b",  # MLX модель (Mac Studio)
            "coding": "qwen2.5-coder:32b",  # MLX модель (Mac Studio)
            "fast": "phi3.5:3.8b",  # Ollama модель
            "default": "qwen2.5-coder:32b"  # MLX модель (Mac Studio)
        }
        model = model_map.get(category, model_map["default"])
        
        try:
            logger.info(f"🤖 [VERONICA] Обработка через {healthy_node['name']} (модель: {model})")
            
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{healthy_node['url']}/api/generate",
                    json={
                        "model": model,
                        "prompt": full_prompt,
                        "stream": False
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    answer = result.get('response', '')
                    logger.info(f"✅ [VERONICA] Ответ получен ({len(answer)} символов)")
                    return answer
                else:
                    logger.error(f"❌ [VERONICA] Ошибка: {response.status_code}")
                    return f"❌ Ошибка локальной модели: {response.status_code}"
        except Exception as e:
            logger.error(f"❌ [VERONICA] Ошибка: {e}")
            return f"❌ Ошибка: {e}"
    
    async def _get_healthy_node(self) -> Optional[Dict]:
        """Получение здорового узла"""
        async with httpx.AsyncClient(timeout=5.0) as client:
            for node in self.nodes:
                try:
                    response = await client.get(f"{node['url']}/api/tags", timeout=2.0)
                    if response.status_code == 200:
                        return node
                except:
                    continue
        return None
    
    async def research_and_analyze(
        self, 
        query: str, 
        category: str = "research",
        use_web: bool = True
    ) -> Dict[str, Any]:
        """
        Полный цикл: веб-поиск + анализ локальной моделью (без токенов).
        """
        logger.info(f"🔬 [VERONICA RESEARCH] Запрос: {query}")
        
        # Шаг 1: Веб-поиск (если нужен)
        web_results = []
        if use_web:
            web_results = await self.web_search(query, max_results=5)
        
        # Шаг 2: Анализ локальной моделью
        analysis_prompt = f"""
        Проанализируй следующий запрос и предоставь подробный ответ.
        Если есть результаты веб-поиска, используй их для обогащения ответа.
        
        ЗАПРОС: {query}
        """
        
        answer = await self.process_with_local_model(
            analysis_prompt,
            web_results=web_results if web_results else None,
            category=category
        )
        
        return {
            "query": query,
            "web_results": web_results,
            "analysis": answer,
            "tokens_used": 0,  # Локальная модель = 0 токенов
            "source": "veronica_local"
        }

async def test_veronica_web_research():
    """Тест Вероники с веб-поиском"""
    print("🧪 Тест: Вероника с веб-поиском\n")
    
    veronica = VeronicaWebResearcher()
    
    # Тест 1: Простой запрос без веб-поиска
    print("📤 Тест 1: Простой запрос (без веб-поиска)")
    result1 = await veronica.process_with_local_model(
        "Объясни, что такое алгоритмическая торговля",
        category="research"
    )
    print(f"✅ Ответ получен ({len(result1)} символов)")
    print(f"   Первые 200 символов: {result1[:200]}...\n")
    
    # Тест 2: Запрос с веб-поиском
    print("📤 Тест 2: Запрос с веб-поиском")
    result2 = await veronica.research_and_analyze(
        "новые тренды в алгоритмической торговле 2025",
        category="research",
        use_web=True
    )
    print(f"✅ Исследование завершено")
    print(f"   Веб-результатов: {len(result2['web_results'])}")
    print(f"   Анализ: {len(result2['analysis'])} символов")
    print(f"   Токенов использовано: {result2['tokens_used']} (0 = бесплатно!)")
    
    return True

if __name__ == "__main__":
    asyncio.run(test_veronica_web_research())

