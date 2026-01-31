#!/usr/bin/env python3
"""
Скрипт для массовой обработки необработанных узлов знаний.
Использует evaluator для обработки узлов батчами.
"""
import asyncio
import os
import sys
import subprocess
from pathlib import Path

# Добавляем путь к app
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

async def get_unverified_count():
    """Получить количество необработанных узлов"""
    import asyncpg
    
    db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
    conn = await asyncpg.connect(db_url)
    try:
        count = await conn.fetchval("SELECT COUNT(*) FROM knowledge_nodes WHERE is_verified = FALSE")
        return count
    finally:
        await conn.close()

def run_evaluator_batch(batch_size=50):
    """Запустить evaluator для обработки батча узлов"""
    evaluator_path = Path(__file__).parent.parent / "app" / "evaluator.py"
    result = subprocess.run(
        [sys.executable, str(evaluator_path), str(batch_size)],
        capture_output=True,
        text=True,
        timeout=3600  # 1 час максимум
    )
    return result.returncode == 0, result.stdout, result.stderr

async def main():
    """Основная функция"""
    print("🚀 Запуск массовой обработки необработанных узлов...")
    
    # Проверяем количество необработанных узлов
    initial_count = await get_unverified_count()
    print(f"📊 Найдено необработанных узлов: {initial_count}")
    
    if initial_count == 0:
        print("✅ Все узлы уже обработаны!")
        return
    
    # Обрабатываем батчами по 50 узлов
    batch_size = 50
    total_processed = 0
    max_batches = 20  # Максимум 20 батчей (1000 узлов)
    
    for batch_num in range(1, max_batches + 1):
        current_count = await get_unverified_count()
        
        if current_count == 0:
            print(f"✅ Все узлы обработаны! Обработано батчей: {batch_num - 1}")
            break
        
        print(f"\n📦 Батч {batch_num}: Обработка {min(batch_size, current_count)} узлов...")
        print(f"   Осталось необработанных: {current_count}")
        
        success, stdout, stderr = run_evaluator_batch(batch_size)
        
        if success:
            processed = min(batch_size, current_count)
            total_processed += processed
            print(f"   ✅ Батч {batch_num} обработан успешно")
            
            # Показываем последние строки вывода
            if stdout:
                lines = stdout.strip().split('\n')
                for line in lines[-5:]:
                    if line.strip():
                        print(f"   {line}")
        else:
            print(f"   ⚠️ Батч {batch_num} завершился с ошибками")
            if stderr:
                print(f"   Ошибка: {stderr[:200]}")
            break
        
        # Небольшая пауза между батчами
        await asyncio.sleep(2)
    
    # Финальная статистика
    final_count = await get_unverified_count()
    print(f"\n📊 ИТОГОВАЯ СТАТИСТИКА:")
    print(f"   Было необработанных: {initial_count}")
    print(f"   Осталось необработанных: {final_count}")
    print(f"   Обработано: {initial_count - final_count}")

if __name__ == "__main__":
    asyncio.run(main())

