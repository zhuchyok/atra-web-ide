"""
Department Heads System - Иерархическая оркестрация через Department Heads
На основе практик Anthropic (Hierarchical Orchestration) и Meta (Supervisor-Worker)
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.debug("asyncpg не доступен, БД функции будут недоступны")

logger = logging.getLogger(__name__)

# Department Heads — отделы из configs/experts/employees.md (58 сотрудников, 27 отделов)
DEPARTMENT_HEADS = {
    "Leadership": "Виктория",
    "Backend": "Игорь",
    "ML/AI": "Дмитрий",
    "DevOps/Infra": "Сергей",
    "Risk Management": "Мария",
    "Strategy/Data": "Максим",
    "Frontend": "Андрей",
    "Security": "Алексей",
    "Database": "Роман",
    "Performance": "Ольга",
    "QA": "Анна",
    "Architecture": "Александр",
    "Documentation": "Татьяна",
    "Monitoring": "Елена",
    "Web/Frontend": "София",
    "Trading": "Павел",
    "Marketing": "Дарья",
    "Product": "Анастасия",
    "Legal": "Юлия",
    "HR": "Алла",
    "Support": "Зоя",
    "Development": "Вероника",
}

# Маппинг ключевых слов к департаментам (определение отдела по задаче)
DEPARTMENT_KEYWORDS = {
    "Leadership": ["координация", "архитектура", "решения", "team lead", "оркестрация"],
    "Backend": ["api", "backend", "сервер", "endpoint", "rest", "graphql", "создай файл", "создай код", "напиши файл", ".py"],
    "ML/AI": ["ml", "ai", "модель", "обучение", "нейросеть", "tensorflow", "pytorch"],
    "DevOps/Infra": ["devops", "docker", "kubernetes", "deploy", "ci/cd", "инфраструктура"],
    "Risk Management": ["риск", "risk", "position sizing", "drawdown", "var"],
    "Strategy/Data": ["стратегия", "strategy", "анализ", "data", "аналитика", "метрики"],
    "Frontend": ["frontend", "ui", "ux", "интерфейс", "react", "vue", "angular", "сайт", "веб", "web", "html", "css", "javascript", "одностраничный", "landing", "создай html", "создай страницу", ".html", ".css", ".js"],
    "Security": ["security", "безопасность", "защита", "encryption", "auth", "api keys"],
    "Database": ["database", "база данных", "sql", "postgres", "mysql", "миграции"],
    "Performance": ["performance", "производительность", "оптимизация", "speed", "latency"],
    "QA": ["qa", "тестирование", "test", "testing", "quality", "покрытие", "юнит-тест"],
    "Marketing": ["seo", "маркетинг", "marketing", "реклама", "продвижение", "контент"],
    "Documentation": ["документация", "documentation", "api docs", "runbook", "отчёт"],
    "Monitoring": ["мониторинг", "prometheus", "grafana", "алерты", "логи", "observability"],
    "Trading": ["торговля", "trading", "стратегия", "бэктест", "индикаторы"],
    "Product": ["продукт", "product", "требования", "roadmap"],
    "Legal": ["legal", "compliance", "юридический", "договор"],
    "HR": ["hr", "кадры", "онбординг"],
    "Support": ["support", "поддержка", "тикеты"],
    "Development": ["разработка", "veronica", "agent", "local developer"],
}


class TaskComplexity(Enum):
    """Сложность задачи"""
    SIMPLE = "simple"  # Один эксперт
    COMPLEX = "complex"  # Department Head координирует
    CRITICAL = "critical"  # Swarm Intelligence


@dataclass
class DepartmentTask:
    """Задача для отдела"""
    task_id: str
    goal: str
    department: str
    complexity: TaskComplexity
    assigned_to: Optional[str] = None
    subtasks: List[str] = None
    result: Optional[str] = None


class DepartmentHeadsSystem:
    """
    Система Department Heads на основе мировых практик:
    - Anthropic: Hierarchical Orchestration с изолированными контекстами
    - Meta: Supervisor-Worker models
    - OpenAI: LLM-Driven Orchestration
    """
    
    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url
        self.department_heads = DEPARTMENT_HEADS
        self.department_keywords = DEPARTMENT_KEYWORDS
    
    def determine_department(self, goal: str) -> Optional[str]:
        """
        Определить отдел для задачи на основе ключевых слов
        
        Returns:
            Название отдела или None
        """
        goal_lower = goal.lower()
        
        # Все задачи идут через план и разбивку (в т.ч. создание файлов) — без исключений
        # Проверяем ключевые слова для каждого отдела
        for department, keywords in self.department_keywords.items():
            if any(keyword in goal_lower for keyword in keywords):
                logger.info(f"🎯 Определен отдел '{department}' для задачи: {goal[:50]}...")
                return department
        
        # Без ключевых слов: если явно просят что-то сделать — идём в Strategy/Data (общие задачи)
        request_phrases = [
            "прошу", "сделай", "помоги", "нужно", "можешь", "хочу",
            "подскажи", "давай", "расскажи что", "объясни", "сделай так",
            "help", "please", "can you", "could you", "хотел бы",
        ]
        if any(phrase in goal_lower for phrase in request_phrases):
            logger.info(f"🎯 Нет ключевых слов отдела, но похоже на просьбу → отдел Strategy/Data")
            return "Strategy/Data"
        return None
    
    def determine_complexity(self, goal: str, department: Optional[str] = None) -> TaskComplexity:
        """
        Определить сложность задачи
        
        Returns:
            TaskComplexity
        """
        goal_lower = goal.lower()
        
        # Критические задачи
        critical_keywords = ["критично", "critical", "важно", "important", "срочно", "urgent"]
        if any(keyword in goal_lower for keyword in critical_keywords):
            return TaskComplexity.CRITICAL
        
        # Сложные задачи
        complex_keywords = ["сложн", "complex", "комплекс", "много", "several", "интеграция"]
        if any(keyword in goal_lower for keyword in complex_keywords):
            return TaskComplexity.COMPLEX
        
        # Простые задачи
        return TaskComplexity.SIMPLE
    
    async def get_department_head(self, department: str) -> Optional[Dict]:
        """
        Получить информацию о Department Head
        
        Returns:
            Dict с информацией о Head или None
        """
        head_name = self.department_heads.get(department)
        if not head_name:
            return None
        
        # Получаем информацию из БД
        if ASYNCPG_AVAILABLE and self.db_url:
            try:
                logger.info(f"🔌 Подключаюсь к БД для получения Department Head '{head_name}' отдела '{department}'...")
                conn = await asyncpg.connect(self.db_url, timeout=5.0)
                head = await conn.fetchrow("""
                    SELECT id, name, role, department, system_prompt
                    FROM experts
                    WHERE name = $1 AND department = $2
                    LIMIT 1
                """, head_name, department)
                await conn.close()
                
                if head:
                    logger.info(f"✅ Department Head '{head_name}' найден в БД: {head['role']}")
                    return {
                        "id": head['id'],
                        "name": head['name'],
                        "role": head['role'],
                        "department": head['department'],
                        "system_prompt": head['system_prompt']
                    }
                else:
                    logger.warning(f"⚠️ Department Head '{head_name}' не найден в БД для отдела '{department}'")
            except Exception as e:
                logger.error(f"❌ Ошибка получения Department Head '{head_name}': {e}", exc_info=True)
        else:
            if not ASYNCPG_AVAILABLE:
                if not hasattr(self, '_asyncpg_warning_logged'):
                    logger.debug(f"ℹ️ asyncpg не доступен, используем fallback для Department Head")
                    self._asyncpg_warning_logged = True
            if not self.db_url:
                if not hasattr(self, '_db_url_warning_logged'):
                    logger.debug(f"ℹ️ DATABASE_URL не настроен, используем fallback для Department Head")
                    self._db_url_warning_logged = True
        
        # Fallback - возвращаем имя
        return {
            "name": head_name,
            "department": department,
            "role": f"{department} Head"
        }
    
    async def get_department_experts(self, department: str, limit: int = 10) -> List[Dict]:
        """
        Получить список экспертов отдела
        
        Returns:
            Список экспертов отдела
        """
        if not ASYNCPG_AVAILABLE:
            if not hasattr(self, '_asyncpg_experts_warning_logged'):
                logger.debug(f"ℹ️ asyncpg не доступен, эксперты из БД недоступны")
                self._asyncpg_experts_warning_logged = True
            return []
        
        if not self.db_url:
            if not hasattr(self, '_db_url_experts_warning_logged'):
                logger.debug(f"ℹ️ DATABASE_URL не настроен, эксперты из БД недоступны")
                self._db_url_experts_warning_logged = True
            return []
        
        try:
            logger.info(f"🔌 Подключаюсь к БД для получения экспертов отдела '{department}'...")
            logger.debug(f"🔌 DATABASE_URL: {self.db_url[:50]}..." if len(self.db_url) > 50 else f"🔌 DATABASE_URL: {self.db_url}")
            
            conn = await asyncpg.connect(self.db_url, timeout=5.0)
            experts = await conn.fetch("""
                SELECT id, name, role, department, system_prompt
                FROM experts
                WHERE department = $1
                ORDER BY id
                LIMIT $2
            """, department, limit)
            await conn.close()
            
            if experts:
                logger.info(f"✅ Получено {len(experts)} экспертов из отдела '{department}': {[e['name'] for e in experts]}")
            else:
                logger.warning(f"⚠️ В отделе '{department}' не найдено экспертов в БД")
            
            return [
                {
                    "id": expert['id'],
                    "name": expert['name'],
                    "role": expert['role'],
                    "department": expert['department'],
                    "system_prompt": expert['system_prompt']
                }
                for expert in experts
            ]
        except asyncpg.exceptions.InvalidPasswordError as e:
            logger.error(f"❌ Ошибка аутентификации БД: {e}")
            return []
        except asyncpg.exceptions.ConnectionDoesNotExistError as e:
            logger.error(f"❌ Ошибка подключения к БД: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Ошибка получения экспертов отдела '{department}': {e}", exc_info=True)
            return []
    
    async def coordinate_department_task(
        self,
        goal: str,
        department: str,
        complexity: TaskComplexity
    ) -> Dict[str, Any]:
        """
        Координировать выполнение задачи через отдел
        
        Args:
            goal: Цель задачи
            department: Отдел
            complexity: Сложность задачи
        
        Returns:
            Результат координации
        """
        logger.info(f"🏢 Координация задачи через отдел '{department}': {goal[:50]}...")
        
        # Получаем Department Head
        head = await self.get_department_head(department)
        if not head:
            logger.warning(f"⚠️ Department Head не найден для '{department}', используем прямую координацию")
            return await self._coordinate_directly(goal, department)
        
        # В зависимости от сложности выбираем стратегию
        if complexity == TaskComplexity.SIMPLE:
            # Простая задача - один эксперт отдела
            return await self._handle_simple_task(goal, department, head)
        elif complexity == TaskComplexity.COMPLEX:
            # Сложная задача - Department Head координирует экспертов
            return await self._handle_complex_task(goal, department, head)
        else:  # CRITICAL
            # Критическая задача - Swarm экспертов отдела
            return await self._handle_critical_task(goal, department, head)
    
    async def _handle_simple_task(
        self,
        goal: str,
        department: str,
        head: Dict
    ) -> Dict[str, Any]:
        """Обработка простой задачи - один эксперт"""
        logger.info(f"👥 Получаю экспертов отдела '{department}' для простой задачи...")
        experts = await self.get_department_experts(department, limit=5)
        
        if not experts:
            logger.error(f"❌ Нет экспертов в отделе '{department}' в БД")
            # Пробуем использовать Department Head как эксперта
            if head and head.get('name'):
                logger.info(f"🔄 Использую Department Head '{head['name']}' как эксперта")
                return {
                    "success": True,
                    "strategy": "simple",
                    "department": department,
                    "assigned_to": head['name'],
                    "expert_info": head,
                    "fallback_to_head": True
                }
            return {
                "success": False,
                "error": f"Нет экспертов в отделе '{department}' и Department Head недоступен"
            }
        
        # Выбираем лучшего эксперта (можно улучшить логику выбора)
        selected_expert = experts[0]
        
        logger.info(f"✅ Простая задача делегирована эксперту '{selected_expert['name']}' ({selected_expert.get('role', 'N/A')}) из отдела '{department}'")
        logger.debug(f"📋 Информация об эксперте: ID={selected_expert.get('id', 'N/A')}, Role={selected_expert.get('role', 'N/A')}")
        
        return {
            "success": True,
            "strategy": "simple",
            "department": department,
            "assigned_to": selected_expert['name'],
            "expert_info": selected_expert
        }
    
    async def _handle_complex_task(
        self,
        goal: str,
        department: str,
        head: Dict
    ) -> Dict[str, Any]:
        """Обработка сложной задачи - Department Head координирует"""
        experts = await self.get_department_experts(department, limit=10)
        
        if not experts:
            return {
                "success": False,
                "error": f"Нет экспертов в отделе '{department}'"
            }
        
        logger.info(f"✅ Сложная задача координируется через '{head['name']}' (Head отдела '{department}')")
        logger.info(f"📋 Эксперты отдела ({len(experts)}): {[e['name'] for e in experts[:5]]}")
        
        return {
            "success": True,
            "strategy": "department_head",
            "department": department,
            "head": head,
            "experts": experts,
            "coordination_required": True
        }
    
    async def _handle_critical_task(
        self,
        goal: str,
        department: str,
        head: Dict
    ) -> Dict[str, Any]:
        """Обработка критической задачи - Swarm экспертов"""
        experts = await self.get_department_experts(department, limit=10)
        
        if not experts:
            return {
                "success": False,
                "error": f"Нет экспертов в отделе '{department}'"
            }
        
        # Выбираем 3-5 лучших экспертов для Swarm
        swarm_experts = experts[:5] if len(experts) >= 5 else experts
        
        logger.info(f"✅ Критическая задача - Swarm из {len(swarm_experts)} экспертов отдела '{department}'")
        logger.info(f"🐝 Swarm эксперты: {[e['name'] for e in swarm_experts]}")
        
        return {
            "success": True,
            "strategy": "swarm",
            "department": department,
            "head": head,
            "swarm_experts": swarm_experts,
            "swarm_size": len(swarm_experts)
        }
    
    async def _coordinate_directly(
        self,
        goal: str,
        department: str
    ) -> Dict[str, Any]:
        """Прямая координация без Department Head"""
        experts = await self.get_department_experts(department, limit=5)
        
        if not experts:
            return {
                "success": False,
                "error": f"Нет экспертов в отделе '{department}'"
            }
        
        selected_expert = experts[0]
        
        return {
            "success": True,
            "strategy": "direct",
            "department": department,
            "assigned_to": selected_expert['name'],
            "expert_info": selected_expert
        }


# Глобальный экземпляр
_department_heads_system: Optional[DepartmentHeadsSystem] = None


def get_department_heads_system(db_url: Optional[str] = None) -> DepartmentHeadsSystem:
    """Получить глобальный экземпляр Department Heads System"""
    global _department_heads_system
    if _department_heads_system is None:
        _department_heads_system = DepartmentHeadsSystem(db_url)
    return _department_heads_system
