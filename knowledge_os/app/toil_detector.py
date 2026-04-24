"""
[SINGULARITY 28.X] Toil Detection - автоматическое обнаружение рутины.
Обнаруживает повторяющиеся задачи и предлагает автоматизацию.
"""

import logging
import os
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from collections import Counter

try:
    from app.db_pool import get_pool
except ImportError:
    from db_pool import get_pool

logger = logging.getLogger("ToilDetector")

# Patterns that indicate toil (рутина)
TOIL_PATTERNS = [
    "повторить",
    "снова",
    "еще раз",
    "same thing",
    "again",
    "ответить на вопрос",
    "простой запрос",
    "рутинн",
    "однотипн"
]

TOIL_TASK_TYPES = [
    "simple_question",
    "status_check",
    "repeat_request",
    "translation",
    "formatting"
]


class ToilDetector:
    """
    [SINGULARITY 28.X] Toil Detector - обнаружение и автоматизация рутины.
    """
    
    def __init__(self):
        self.toil_patterns = TOIL_PATTERNS
        self.toil_task_types = TOIL_TASK_TYPES

    async def detect_toil_tasks(self, time_window_hours: int = 24) -> List[Dict[str, Any]]:
        """Detect tasks that look like toil (рутина)."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Get recent tasks and analyze patterns
            tasks = await conn.fetch("""
                SELECT 
                    id, title, description, status, 
                    created_at, metadata
                FROM tasks
                WHERE created_at > NOW() - INTERVAL '1 hour' * $1
                AND status IN ('completed', 'pending')
                ORDER BY created_at DESC
            """, time_window_hours)

            toil_tasks = []
            for task in tasks:
                title = (task.get("title") or "").lower()
                desc = (task.get("description") or "").lower()
                
                # Check for toil patterns
                is_toil = any(pattern in title or pattern in desc 
                           for pattern in self.toil_patterns)
                
                if is_toil:
                    toil_tasks.append({
                        "task_id": task["id"],
                        "title": task["title"],
                        "created_at": task["created_at"].isoformat() if task.get("created_at") else None,
                        "reason": "matched toil pattern"
                    })

            logger.info(f"🔄 [TOIL] Found {len(toil_tasks)} toil tasks in {time_window_hours}h")
            return toil_tasks

    async def suggest_automation(self, task: Dict[str, Any]) -> str:
        """Suggest automation for a toil task."""
        title = task.get("title", "").lower()
        
        if "перевод" in title or "translate" in title:
            return "Авто-перевод через MLX API при получении задачи с типом 'translation'"
        elif "формат" in title or "format" in title:
            return "Авто-форматирование через template"
        elif "вопрос" in title or "question" in title:
            return "Кэшированный ответ через semantic cache"
        else:
            return "Создать macro/quick reply для этого типа задач"

    async def auto_resolve(self, task_id: str) -> bool:
        """Attempt to automatically resolve a toil task."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Mark as auto-resolved
            result = await conn.execute("""
                UPDATE tasks 
                SET status = 'completed', 
                    metadata = metadata || jsonb_build_object('auto_resolved', true, 'resolved_at', NOW())
                WHERE id = $1
            """, task_id)
            
            return result.startswith("UPDATE")

    async def analyze_toil_trends(self, days: int = 7) -> Dict[str, Any]:
        """Analyze toil trends over time."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Get task pattern counts
            task_types = await conn.fetch("""
                SELECT 
                    metadata->>'task_type' as task_type,
                    COUNT(*) as count
                FROM tasks
                WHERE created_at > NOW() - INTERVAL '1 day' * $1
                AND metadata->>'task_type' IS NOT NULL
                GROUP BY (metadata->>'task_type')
                ORDER BY count DESC
                LIMIT 10
            """, days)

            # Get repeated titles
            repeated = await conn.fetch("""
                SELECT title, COUNT(*) as count
                FROM tasks
                WHERE created_at > NOW() - INTERVAL '1 day' * $1
                GROUP BY title
                HAVING COUNT(*) > 2
                ORDER BY count DESC
                LIMIT 5
            """, days)

            return {
                "task_types": [dict(r) for r in task_types] if task_types else [],
                "repeated_tasks": [dict(r) for r in repeated] if repeated else [],
                "days": days
            }

    async def report_toil_metrics(self) -> Dict[str, Any]:
        """Get overall toil metrics."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Total tasks
            total = await conn.fetchval("""
                SELECT COUNT(*) FROM tasks 
                WHERE created_at > NOW() - INTERVAL '24 hours'
            """)
            
            # Auto-resolved
            auto_resolved = await conn.fetchval("""
                SELECT COUNT(*) FROM tasks 
                WHERE metadata->>'auto_resolved' = 'true'
                AND created_at > NOW() - INTERVAL '24 hours'
            """)
            
            # Toil percentage
            toil_tasks = await self.detect_toil_tasks(24)
            
            return {
                "total_tasks_24h": total or 0,
                "auto_resolved_24h": auto_resolved or 0,
                "detected_toil_24h": len(toil_tasks),
                "toil_percentage": round((len(toil_tasks) / max(total, 1)) * 100, 1)
            }


_toil_detector = None

def get_toil_detector() -> ToilDetector:
    """Get singleton instance."""
    global _toil_detector
    if _toil_detector is None:
        _toil_detector = ToilDetector()
    return _toil_detector