"""
Model Tracker - Автоматическое отслеживание моделей и сохранение в базу знаний
Периодически проверяет доступные модели, отслеживает изменения и обновляет базу знаний
"""

import asyncio
import os
import json
import httpx
import asyncpg
from datetime import datetime, timezone
from typing import List, Dict, Optional, Set
import logging
try:
    from .model_notifier import ModelNotifier
except ImportError:
    try:
        from model_notifier import ModelNotifier
    except ImportError:
        # Если ModelNotifier недоступен, создаем заглушку
        class ModelNotifier:
            def __init__(self, *args, **kwargs):
                pass
            async def notify_new_model(self, *args, **kwargs):
                pass

logger = logging.getLogger(__name__)

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')
OLLAMA_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
CHECK_INTERVAL = int(os.getenv('MODEL_TRACKER_INTERVAL', '3600'))  # 1 час по умолчанию

class ModelTracker:
    """Отслеживает модели и сохраняет информацию в базу знаний"""
    
    def __init__(self, db_url: str = DB_URL, ollama_url: str = OLLAMA_URL):
        self.db_url = db_url
        self.ollama_url = ollama_url
        self.last_known_models: Set[str] = set()
        self._running = False
        self.notifier = ModelNotifier(db_url)
    
    async def get_available_models(self) -> List[Dict]:
        """Получить список доступных моделей через API"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.ollama_url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    return data.get('models', [])
        except Exception as e:
            logger.error(f"Ошибка получения моделей: {e}")
        return []
    
    async def get_model_details(self, model_name: str) -> Optional[Dict]:
        """Получить детальную информацию о модели"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Пробуем получить информацию через API
                response = await client.get(f"{self.ollama_url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    for model in data.get('models', []):
                        if model.get('name') == model_name:
                            return model
        except Exception as e:
            logger.warning(f"Ошибка получения деталей модели {model_name}: {e}")
        return None
    
    async def save_model_to_knowledge_base(self, model: Dict, conn: asyncpg.Connection):
        """Сохранить информацию о модели в базу знаний"""
        model_name = model.get('name', 'unknown')
        size = model.get('size', 0)
        details = model.get('details', {})
        
        # Определяем категорию модели
        category = self._determine_model_category(model_name, details)
        
        # Формируем контент для базы знаний
        content = f"""🤖 Модель: {model_name}

📊 Характеристики:
- Размер: {self._format_size(size)}
- Параметры: {details.get('parameter_size', 'неизвестно')}
- Формат: {details.get('format', 'неизвестно')}
- Квантование: {details.get('quantization_level', 'неизвестно')}
- Семейство: {', '.join(details.get('families', []))}

🎯 Назначение: {category}

📅 Обновлено: {datetime.now(timezone.utc).isoformat()}
"""
        
        # Метаданные
        metadata = {
            "type": "model",
            "model_name": model_name,
            "size_bytes": size,
            "size_formatted": self._format_size(size),
            "parameter_size": details.get('parameter_size'),
            "format": details.get('format'),
            "quantization_level": details.get('quantization_level'),
            "families": details.get('families', []),
            "category": category,
            "modified_at": model.get('modified_at'),
            "digest": model.get('digest'),
            "last_tracked": datetime.now(timezone.utc).isoformat()
        }
        
        # Получаем или создаем домен "AI Models"
        domain_id = await conn.fetchval("SELECT id FROM domains WHERE name = $1", "AI Models")
        if not domain_id:
            domain_id = await conn.fetchval("INSERT INTO domains (name) VALUES ($1) RETURNING id", "AI Models")
        
        # Проверяем, существует ли уже запись об этой модели
        existing = await conn.fetchrow("""
            SELECT id, metadata FROM knowledge_nodes 
            WHERE domain_id = $1 
            AND content LIKE $2
            ORDER BY created_at DESC
            LIMIT 1
        """, domain_id, f"%Модель: {model_name}%")
        
        if existing:
            # Обновляем существующую запись
            existing_metadata = existing['metadata'] or {}
            # Парсим существующий metadata если это строка
            if isinstance(existing_metadata, str):
                try:
                    existing_metadata = json.loads(existing_metadata)
                except (json.JSONDecodeError, TypeError):
                    existing_metadata = {}
            elif not isinstance(existing_metadata, dict):
                existing_metadata = {}
            
            # Обновляем metadata
            existing_metadata.update(metadata)
            
            await conn.execute("""
                UPDATE knowledge_nodes 
                SET content = $1, 
                    metadata = $2,
                    confidence_score = 1.0,
                    is_verified = TRUE,
                    updated_at = NOW()
                WHERE id = $3
            """, content, json.dumps(existing_metadata), existing['id'])
            
            logger.info(f"✅ Обновлена информация о модели: {model_name}")
        else:
            # Создаем новую запись
            await conn.execute("""
                INSERT INTO knowledge_nodes (domain_id, content, metadata, confidence_score, is_verified)
                VALUES ($1, $2, $3, $4, $5)
            """, domain_id, content, json.dumps(metadata), 1.0, True)
            
            logger.info(f"✨ Добавлена новая модель в базу знаний: {model_name}")
    
    def _determine_model_category(self, model_name: str, details: Dict) -> str:
        """Определить категорию модели на основе имени и деталей"""
        name_lower = model_name.lower()
        
        if 'coder' in name_lower or 'code' in name_lower:
            return "Coding - разработка кода"
        elif 'r1' in name_lower or 'reasoning' in name_lower or 'distill' in name_lower:
            return "Reasoning - рассуждения и планирование"
        elif 'vision' in name_lower or 'dream' in name_lower:
            return "Vision - работа с изображениями"
        elif 'embed' in name_lower:
            return "Embeddings - векторные представления"
        elif 'tiny' in name_lower or 'mini' in name_lower:
            return "Fast - быстрые ответы"
        elif '70b' in name_lower or '104b' in name_lower or 'large' in name_lower:
            return "Complex - сложные задачи, максимальное качество"
        elif 'phi' in name_lower or 'qwen' in name_lower:
            return "General - общие задачи"
        else:
            return "General - общие задачи"
    
    def _format_size(self, size_bytes: int) -> str:
        """Форматировать размер в читаемый вид"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
    
    async def track_models(self):
        """Отследить модели и сохранить в базу знаний"""
        try:
            models = await self.get_available_models()
            if not models:
                logger.warning("Не удалось получить список моделей")
                return
            
            current_models = {model.get('name') for model in models if model.get('name')}
            new_models = current_models - self.last_known_models
            removed_models = self.last_known_models - current_models
            
            if new_models:
                logger.info(f"🆕 Обнаружены новые модели: {', '.join(new_models)}")
            
            if removed_models:
                logger.info(f"⚠️ Модели удалены: {', '.join(removed_models)}")
            
            # Сохраняем все модели в базу знаний
            conn = await asyncpg.connect(self.db_url)
            try:
                for model in models:
                    await self.save_model_to_knowledge_base(model, conn)
                
                # Сохраняем сводку изменений
                if new_models or removed_models:
                    await self._save_changes_summary(conn, new_models, removed_models, current_models)
                
                # Уведомляем о новых моделях
                if new_models:
                    model_details_dict = {m.get('name'): m for m in models if m.get('name') in new_models}
                    await self.notifier.notify_about_new_models(list(new_models), model_details_dict)
                
            finally:
                await conn.close()
            
            self.last_known_models = current_models
            logger.info(f"✅ Отслеживание моделей завершено. Всего моделей: {len(current_models)}")
            
        except Exception as e:
            logger.error(f"Ошибка отслеживания моделей: {e}", exc_info=True)
    
    async def _save_changes_summary(self, conn: asyncpg.Connection, new_models: Set[str], 
                                   removed_models: Set[str], current_models: Set[str]):
        """Сохранить сводку изменений в базу знаний"""
        summary_content = f"""📊 Сводка изменений моделей

🆕 Новые модели ({len(new_models)}):
{chr(10).join(f'- {m}' for m in new_models) if new_models else '- Нет новых моделей'}

⚠️ Удаленные модели ({len(removed_models)}):
{chr(10).join(f'- {m}' for m in removed_models) if removed_models else '- Нет удаленных моделей'}

📦 Всего доступно моделей: {len(current_models)}

📅 Обновлено: {datetime.now(timezone.utc).isoformat()}
"""
        
        metadata = {
            "type": "model_changes_summary",
            "new_models": list(new_models),
            "removed_models": list(removed_models),
            "total_models": len(current_models),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        domain_id = await conn.fetchval("SELECT id FROM domains WHERE name = $1", "AI Models")
        if not domain_id:
            domain_id = await conn.fetchval("INSERT INTO domains (name) VALUES ($1) RETURNING id", "AI Models")
        
        await conn.execute("""
            INSERT INTO knowledge_nodes (domain_id, content, metadata, confidence_score, is_verified)
            VALUES ($1, $2, $3, $4, $5)
        """, domain_id, summary_content, json.dumps(metadata), 1.0, True)
    
    async def run_continuous(self):
        """Запустить непрерывное отслеживание"""
        self._running = True
        logger.info(f"🚀 Запущено отслеживание моделей (интервал: {CHECK_INTERVAL} сек)")
        
        # Первая проверка сразу
        await self.track_models()
        
        while self._running:
            await asyncio.sleep(CHECK_INTERVAL)
            if self._running:
                await self.track_models()
    
    def stop(self):
        """Остановить отслеживание"""
        self._running = False
        logger.info("⏹️ Отслеживание моделей остановлено")


async def main():
    """Главная функция для запуска отслеживания"""
    tracker = ModelTracker()
    try:
        await tracker.run_continuous()
    except KeyboardInterrupt:
        tracker.stop()
        logger.info("Остановлено пользователем")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    asyncio.run(main())
