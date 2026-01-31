"""
Model Notifier - Уведомляет Викторию, Веронику и корпорацию о новых моделях
"""

import asyncio
import os
import json
import httpx
import asyncpg
from datetime import datetime, timezone
from typing import List, Dict, Set
import logging

logger = logging.getLogger(__name__)

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')
VICTORIA_URL = os.getenv('VICTORIA_URL', 'http://localhost:8010')
VERONICA_URL = os.getenv('VERONICA_URL', 'http://localhost:8011')

class ModelNotifier:
    """Уведомляет агентов о новых моделях"""
    
    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url
        self.victoria_url = VICTORIA_URL
        self.veronica_url = VERONICA_URL
    
    async def notify_about_new_models(self, new_models: List[str], model_details: Dict[str, Dict]):
        """Уведомить агентов о новых моделях"""
        if not new_models:
            return
        
        notification = self._create_notification(new_models, model_details)
        
        # Уведомляем Викторию (Team Lead)
        await self._notify_victoria(notification)
        
        # Уведомляем Веронику (Local Developer)
        await self._notify_veronica(notification)
        
        # Сохраняем уведомление в базу знаний
        await self._save_notification_to_db(notification)
    
    def _create_notification(self, new_models: List[str], model_details: Dict[str, Dict]) -> Dict:
        """Создать уведомление о новых моделях"""
        models_info = []
        for model_name in new_models:
            details = model_details.get(model_name, {})
            size = details.get('size', 0)
            param_size = details.get('details', {}).get('parameter_size', 'неизвестно')
            
            models_info.append({
                "name": model_name,
                "size": self._format_size(size),
                "parameters": param_size,
                "category": self._determine_category(model_name, details.get('details', {}))
            })
        
        return {
            "type": "new_models_notification",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "models": models_info,
            "count": len(new_models)
        }
    
    async def _notify_victoria(self, notification: Dict):
        """Уведомить Викторию о новых моделях"""
        try:
            message = f"""🎉 Обнаружены новые модели ({notification['count']}):

"""
            for model in notification['models']:
                message += f"""🤖 {model['name']}
   📊 Размер: {model['size']}
   🔢 Параметры: {model['parameters']}
   🎯 Категория: {model['category']}

"""
            
            message += f"""
📅 Время обнаружения: {notification['timestamp']}

💡 Рекомендация: Проверьте новые модели и обновите конфигурацию выбора моделей при необходимости.
"""
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                try:
                    # Пробуем отправить через API Виктории
                    response = await client.post(
                        f"{self.victoria_url}/notify",
                        json={"message": message, "type": "model_update"},
                        timeout=5.0
                    )
                    if response.status_code == 200:
                        logger.info("✅ Виктория уведомлена о новых моделях")
                except Exception as e:
                    logger.warning(f"Не удалось уведомить Викторию: {e}")
        except Exception as e:
            logger.error(f"Ошибка уведомления Виктории: {e}")
    
    async def _notify_veronica(self, notification: Dict):
        """Уведомить Веронику о новых моделях"""
        try:
            message = f"""🆕 Доступны новые модели ({notification['count']}):

"""
            for model in notification['models']:
                message += f"- {model['name']} ({model['size']}, {model['category']})\n"
            
            message += "\n💡 Можете использовать новые модели для разработки."
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                try:
                    response = await client.post(
                        f"{self.veronica_url}/notify",
                        json={"message": message, "type": "model_update"},
                        timeout=5.0
                    )
                    if response.status_code == 200:
                        logger.info("✅ Вероника уведомлена о новых моделях")
                except Exception as e:
                    logger.warning(f"Не удалось уведомить Веронику: {e}")
        except Exception as e:
            logger.error(f"Ошибка уведомления Вероники: {e}")
    
    async def _save_notification_to_db(self, notification: Dict):
        """Сохранить уведомление в базу знаний"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                content = f"""🔔 Уведомление о новых моделях

Обнаружено новых моделей: {notification['count']}

"""
                for model in notification['models']:
                    content += f"""🤖 {model['name']}
   Размер: {model['size']}
   Параметры: {model['parameters']}
   Категория: {model['category']}

"""
                
                content += f"\n📅 Время: {notification['timestamp']}"
                
                domain_id = await conn.fetchval("SELECT id FROM domains WHERE name = $1", "AI Models")
                if not domain_id:
                    domain_id = await conn.fetchval("INSERT INTO domains (name) VALUES ($1) RETURNING id", "AI Models")
                
                await conn.execute("""
                    INSERT INTO knowledge_nodes (domain_id, content, metadata, confidence_score, is_verified)
                    VALUES ($1, $2, $3, $4, $5)
                """, domain_id, content, json.dumps(notification), 1.0, True)
                
                logger.info("✅ Уведомление сохранено в базу знаний")
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Ошибка сохранения уведомления: {e}")
    
    def _determine_category(self, model_name: str, details: Dict) -> str:
        """Определить категорию модели"""
        name_lower = model_name.lower()
        
        if 'coder' in name_lower:
            return "Coding"
        elif 'r1' in name_lower or 'reasoning' in name_lower:
            return "Reasoning"
        elif 'vision' in name_lower:
            return "Vision"
        elif 'tiny' in name_lower or 'mini' in name_lower:
            return "Fast"
        elif '70b' in name_lower or '104b' in name_lower:
            return "Complex"
        else:
            return "General"
    
    def _format_size(self, size_bytes: int) -> str:
        """Форматировать размер"""
        if size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
