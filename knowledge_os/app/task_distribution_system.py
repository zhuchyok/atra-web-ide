"""
Task Distribution System - Полная система распределения задач
Импортирует полную реализацию из task_distribution_system_complete.py
"""
import logging
import json
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Database connection
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False

# Импортируем полную реализацию
try:
    from task_distribution_system_complete import (
        TaskDistributionSystem,
        TaskAssignment,
        TaskStatus,
        TaskCollection,
        get_task_distribution_system
    )
except ImportError:
    # Если полная реализация недоступна, создаем базовую
    from enum import Enum
    from dataclasses import dataclass
    
    class TaskStatus(Enum):
        PENDING = "pending"
        IN_PROGRESS = "in_progress"
        COMPLETED = "completed"
        REVIEWED = "reviewed"
        REJECTED = "rejected"
        FAILED = "failed"
    
    @dataclass
    class TaskAssignment:
        task_id: str
        subtask: str
        employee_name: str
        department: str
        status: TaskStatus = TaskStatus.PENDING
        result: Optional[str] = None
        manager_name: Optional[str] = None
        quality_score: float = 0.0
        correlation_id: Optional[str] = None
        review_rejections: int = 0
        recommended_model: Optional[str] = None
    
    @dataclass
    class TaskCollection:
        department: str
        aggregated_result: str
        assignments: List[TaskAssignment]
        quality_score: float = 0.0
    
    class TaskDistributionSystem:
        def __init__(self, db_url: str):
            self.db_url = db_url
        
        async def distribute_tasks_from_plan(self, *args, **kwargs):
            return []

        async def distribute_tasks_from_veronica_prompt(self, *args, **kwargs):
            return []
        
        async def execute_task_assignment(self, *args, **kwargs):
            return None
        
        async def manager_review_task(self, *args, **kwargs):
            return None
        
        async def department_head_collect_tasks(self, *args, **kwargs):
            return None
    
    def get_task_distribution_system(db_url: str) -> TaskDistributionSystem:
        return TaskDistributionSystem(db_url)

# Экспортируем все для обратной совместимости
__all__ = [
    'TaskDistributionSystem',
    'TaskAssignment',
    'TaskStatus',
    'TaskCollection',
    'get_task_distribution_system'
]

# Добавляем методы для полной обратной цепочки после существующих методов

async def _collect_and_review_by_managers(
    self, assignments: List[TaskAssignment]
) -> List[Dict]:
    """
    Собрать результаты от сотрудников и проверить управляющими
    
    Основано на лучших практиках:
    - Anthropic: Hierarchical review process
    - OpenAI: Quality gates at each level
    
    Returns:
        Список проверенных результатов
    """
    reviewed_results = []
    
    # Группируем по отделам для эффективной обработки
    by_department = {}
    for assignment in assignments:
        if assignment.status == TaskStatus.COMPLETED:
            dept = assignment.department
            if dept not in by_department:
                by_department[dept] = []
            by_department[dept].append(assignment)
    
    # Обрабатываем каждый отдел
    for department, dept_assignments in by_department.items():
        for assignment in dept_assignments:
            # Проверка управляющим
            reviewed_assignment = await self.manager_review_task(
                assignment,
                original_requirements=assignment.subtask
            )
            
            if reviewed_assignment.status == TaskStatus.REVIEWED:
                reviewed_results.append({
                    "assignment_id": reviewed_assignment.task_id,
                    "employee": reviewed_assignment.employee_name,
                    "department": reviewed_assignment.department,
                    "subtask": reviewed_assignment.subtask,
                    "result": reviewed_assignment.result,
                    "quality_score": getattr(reviewed_assignment, 'quality_score', 0.8),
                    "reviewed_by": reviewed_assignment.manager_name,
                    "correlation_id": reviewed_assignment.correlation_id
                })
            else:
                logger.warning(f"⚠️ Задача {reviewed_assignment.task_id} не прошла проверку управляющим")
    
    return reviewed_results

async def _collect_by_department_heads_enhanced(
    self, reviewed_results: List[Dict]
) -> Dict[str, Dict]:
    """
    Department Heads собирают и синтезируют результаты своих отделов (улучшенная версия)
    
    Основано на лучших практиках:
    - Anthropic: Department-level synthesis
    - OpenAI: Cross-expert result aggregation
    
    Returns:
        Словарь {department: synthesized_result}
    """
    # Группируем по отделам
    by_department = {}
    for result in reviewed_results:
        dept = result["department"]
        if dept not in by_department:
            by_department[dept] = []
        by_department[dept].append(result)
    
    department_syntheses = {}
    
    for department, dept_results in by_department.items():
        # Получаем Department Head
        dept_head = await self._get_department_head(department)
        if not dept_head:
            logger.warning(f"⚠️ Department Head не найден для '{department}'")
            # Реальная обработка без Department Head - используем Victoria для синтеза
            try:
                from app.victoria_enhanced import VictoriaEnhanced
                victoria = VictoriaEnhanced()
                
                synthesis_prompt = f"""
                Синтезируй результаты от {len(dept_results)} сотрудников отдела {department}:
                {json.dumps(dept_results, ensure_ascii=False, indent=2)}
                
                Создай единый результат отдела.
                """
                
                synthesis_result = await victoria.solve(synthesis_prompt, method="extended_thinking")
                aggregated = synthesis_result.get('result', '') or synthesis_result.get('output', '')
                
                department_syntheses[department] = {
                    "department": department,
                    "summary": f"Результаты от {len(dept_results)} сотрудников (синтезировано Victoria)",
                    "unified_result": aggregated,
                    "results": dept_results,
                    "synthesized": True
                }
            except Exception as e:
                logger.error(f"❌ Ошибка синтеза через Victoria: {e}")
                # Только в крайнем случае - простое агрегирование
                department_syntheses[department] = {
                    "department": department,
                    "summary": f"Результаты от {len(dept_results)} сотрудников",
                    "results": dept_results,
                    "synthesized": False
                }
            continue
        
        # Создаем промпт для синтеза
        synthesis_prompt = f"""
        ТЫ: {dept_head['name']}, Department Head отдела {department}
        
        СИНТЕЗИРУЙ РЕЗУЛЬТАТЫ ОТ СОТРУДНИКОВ ТВОЕГО ОТДЕЛА:
        
        РЕЗУЛЬТАТЫ:
        {json.dumps(dept_results, indent=2, ensure_ascii=False)}
        
        СОЗДАЙ ЕДИНЫЙ РЕЗУЛЬТАТ ОТДЕЛА:
        1. Объедини все результаты в единое решение
        2. Устрани противоречия
        3. Выдели ключевые достижения
        4. Укажи созданные файлы/изменения
        5. Оцени качество (0.0-1.0)
        
        ВЕРНИ В ФОРМАТЕ JSON:
        {{
            "department": "{department}",
            "summary": "Краткое резюме работы отдела",
            "unified_result": "Объединенный результат от всех сотрудников",
            "key_achievements": ["достижение1", "достижение2"],
            "files_created": ["все файлы от отдела"],
            "files_modified": ["измененные файлы"],
            "quality_score": 0.0-1.0,
            "ready_for_veronica": true,
            "notes": "Важные замечания для Veronica"
        }}
        """
        
        # Выполняем синтез через ReActAgent
        try:
            from app.react_agent import ReActAgent
            dept_head_agent = ReActAgent(
                agent_name=dept_head['name'],
                system_prompt=f"Вы {dept_head['name']}, Department Head отдела {department}",
                model_name="deepseek-r1-distill-llama:70b"
            )
            
            synthesis_result = await dept_head_agent.run(goal=synthesis_prompt, context=None)
            
            # Парсим результат
            dept_synthesis = self._parse_synthesis_result(synthesis_result)
            dept_synthesis["department"] = department
            dept_synthesis["head"] = dept_head['name']
            
            department_syntheses[department] = dept_synthesis
            
            logger.info(f"✅ [DEPARTMENT HEAD] {dept_head['name']} синтезировал результаты отдела '{department}'")
            
        except Exception as e:
            logger.error(f"❌ Ошибка синтеза отдела '{department}': {e}")
            # Fallback
            department_syntheses[department] = {
                "department": department,
                "summary": f"Результаты от {len(dept_results)} сотрудников (синтез не выполнен)",
                "results": dept_results,
                "synthesized": False,
                "error": str(e)
            }
    
    return department_syntheses

async def _get_department_head(self, department: str) -> Optional[Dict]:
    """Получить Department Head для отдела"""
    try:
        if ASYNCPG_AVAILABLE and self.db_url:
            conn = await asyncpg.connect(self.db_url, timeout=3.0)
            try:
                head = await conn.fetchrow("""
                    SELECT id, name, role, department, system_prompt
                    FROM experts
                    WHERE department = $1 AND role ILIKE '%head%' OR role ILIKE '%руководитель%'
                    LIMIT 1
                """, department)
                if head:
                    return dict(head)
            finally:
                await conn.close()
    except Exception as e:
        logger.debug(f"⚠️ Не удалось получить Department Head из БД: {e}")
    
    # Реальный поиск через department_heads_system
    try:
        from app.department_heads_system import DEPARTMENT_HEADS
        head_name = DEPARTMENT_HEADS.get(department)
        if head_name:
            # Проверяем, существует ли эксперт в БД
            if ASYNCPG_AVAILABLE:
                try:
                    conn = await asyncpg.connect(self.db_url, timeout=3.0)
                    try:
                        expert = await conn.fetchrow("""
                            SELECT id, name, role, department, system_prompt
                            FROM experts
                            WHERE name = $1
                            LIMIT 1
                        """, head_name)
                        if expert:
                            return dict(expert)
                    finally:
                        await conn.close()
                except Exception:
                    pass
            
            # Если не найден в БД, возвращаем базовую информацию
            return {
                "name": head_name,
                "department": department,
                "role": "Department Head"
            }
    except Exception as e:
        logger.debug(f"⚠️ Ошибка получения Department Head из системы: {e}")
    
    return None

def _parse_synthesis_result(self, synthesis_result: Any) -> Dict:
    """Парсить результат синтеза с fallback"""
    import json
    import re
    
    if isinstance(synthesis_result, dict):
        if "final_reflection" in synthesis_result:
            synthesis_text = synthesis_result["final_reflection"]
        elif "result" in synthesis_result:
            synthesis_text = synthesis_result["result"]
        else:
            synthesis_text = str(synthesis_result)
    else:
        synthesis_text = str(synthesis_result)
    
    # Ищем JSON
    json_match = re.search(r'\{.*\}', synthesis_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    
    # Реальный парсинг - пробуем извлечь структурированные данные
    # Ищем ключевые поля в тексте
    summary_match = re.search(r'"summary":\s*"([^"]+)"', synthesis_text, re.IGNORECASE)
    unified_match = re.search(r'"unified_result":\s*"([^"]+)"', synthesis_text, re.IGNORECASE)
    
    result = {
        "summary": summary_match.group(1) if summary_match else synthesis_text[:500],
        "unified_result": unified_match.group(1) if unified_match else synthesis_text,
        "synthesized": True
    }
    
    # Пробуем извлечь другие поля
    achievements_match = re.search(r'"key_achievements":\s*\[(.*?)\]', synthesis_text, re.DOTALL)
    if achievements_match:
        try:
            result["key_achievements"] = json.loads(f"[{achievements_match.group(1)}]")
        except:
            pass
    
    files_match = re.search(r'"files_created":\s*\[(.*?)\]', synthesis_text, re.DOTALL)
    if files_match:
        try:
            result["files_created"] = json.loads(f"[{files_match.group(1)}]")
        except:
            pass
    
    return result
