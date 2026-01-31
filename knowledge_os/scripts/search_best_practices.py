#!/usr/bin/env python3
"""
Скрипт для поиска лучших практик из интернета для всех сотрудников.

Использует веб-поиск для поиска актуальных практик и обновляет базы знаний.
"""

import logging
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from observability.best_practices_searcher import get_best_practices_searcher
from observability.team_member_manager import get_team_member_manager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def search_best_practices_for_all_members(use_web_search: bool = True):
    """
    Ищет лучшие практики для всех сотрудников.
    
    Args:
        use_web_search: Использовать ли веб-поиск (требует доступ к web_search)
    """
    logger.info("🔍 Запуск поиска лучших практик для всех сотрудников...")
    
    team_manager = get_team_member_manager()
    searcher = get_best_practices_searcher()
    
    results = []
    
    for member in team_manager.get_active_members():
        logger.info("🔍 Поиск практик для %s (%s)...", member.name, member.role)
        
        try:
            practices = searcher.search_best_practices_for_role(
                member.role,
                use_web_search=use_web_search,
            )
            
            results.append({
                "member": member.name,
                "role": member.role,
                "practices_found": len(practices),
                "practices": practices,
            })
            
            logger.info("✅ Найдено практик для %s: %d", member.name, len(practices))
            
        except Exception as e:
            logger.error("❌ Ошибка поиска для %s: %s", member.name, e)
            results.append({
                "member": member.name,
                "role": member.role,
                "practices_found": 0,
                "error": str(e),
            })
    
    # Выводим результаты
    print("\n" + "="*70)
    print("📊 РЕЗУЛЬТАТЫ ПОИСКА ЛУЧШИХ ПРАКТИК")
    print("="*70)
    
    total_practices = sum(r.get("practices_found", 0) for r in results)
    print(f"✅ Всего найдено практик: {total_practices}")
    print(f"✅ Обработано сотрудников: {len(results)}")
    
    print("\n👥 РЕЗУЛЬТАТЫ ПО СОТРУДНИКАМ:")
    for result in results:
        status = "✅" if result.get("practices_found", 0) > 0 else "⚠️"
        print(f"   {status} {result['member']} ({result['role']}): {result.get('practices_found', 0)} практик")
        if "error" in result:
            print(f"      Ошибка: {result['error']}")
    
    print("\n" + "="*70)
    logger.info("✅ Поиск завершен!")
    
    return results


def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Поиск лучших практик для всех сотрудников")
    parser.add_argument(
        "--no-web-search",
        action="store_true",
        help="Не использовать веб-поиск (только кэш)",
    )
    
    args = parser.parse_args()
    
    results = search_best_practices_for_all_members(use_web_search=not args.no_web_search)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

