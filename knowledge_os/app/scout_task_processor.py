#!/usr/bin/env python3
"""
Обработчик задач разведки для smart_worker_autonomous.py
Определяет, использовать ли базовую или enhanced разведку
"""

import asyncio
import os
import sys
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

async def process_scout_task(task_metadata: Dict[str, Any], task_description: str) -> str:
    """
    Обрабатывает задачу разведки, определяя нужен ли enhanced режим.
    
    Args:
        task_metadata: Метаданные задачи
        task_description: Описание задачи
        
    Returns:
        Результат выполнения разведки
    """
    business = task_metadata.get('business', 'Столичные окна')
    location = task_metadata.get('location', 'Чебоксары')
    use_enhanced = task_metadata.get('enhanced', False)
    extra_competitors = task_metadata.get('extra_competitors')
    
    # Определяем, использовать ли enhanced
    if use_enhanced or 'enhanced' in task_description.lower() or 'максимум' in task_description.lower():
        logger.info("🚀 Используем Enhanced разведку")
        try:
            # Пытаемся импортировать enhanced версию
            current_dir = os.path.dirname(os.path.abspath(__file__))
            sys.path.insert(0, current_dir)
            sys.path.insert(0, '/app')  # Также пробуем /app
            
            from enhanced_scout_researcher import EnhancedScoutResearcher
            
            researcher = EnhancedScoutResearcher()
            
            # Обрабатываем extra_competitors
            competitors_list = None
            if extra_competitors:
                if isinstance(extra_competitors, str):
                    competitors_list = [c.strip() for c in extra_competitors.split(',') if c.strip()]
                elif isinstance(extra_competitors, list):
                    competitors_list = extra_competitors
            
            result = await researcher.perform_enhanced_research(
                business, 
                location, 
                competitors_list
            )
            return f"✅ Enhanced разведка завершена. Найдено {result.get('total_sources', 0)} источников, {len(result.get('competitors', {}))} конкурентов. Детальный отчет с SWOT, Porter's Five Forces, PEST анализом сохранен в БД."
        except ImportError as e:
            logger.warning(f"Enhanced разведка недоступна: {e}, используем базовую")
            use_enhanced = False
        except Exception as e:
            logger.error(f"Ошибка Enhanced разведки: {e}")
            use_enhanced = False
    
    # Базовая разведка
    if not use_enhanced:
        logger.info("📋 Используем базовую разведку")
        try:
            from scout_researcher import perform_scout_research
            await perform_scout_research(business, location)
            return f"✅ Базовая разведка завершена для '{business}' в {location}"
        except Exception as e:
            logger.error(f"Ошибка базовой разведки: {e}")
            return f"❌ Ошибка разведки: {e}"
