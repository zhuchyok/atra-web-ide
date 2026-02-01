"""
Worker для автоматической синхронизации .cursor/rules/ при изменениях в БД.

Запускается как background task и:
1. Отслеживает изменения в таблице experts_changelog
2. Запускает sync_cursor_rules.py при обнаружении изменений
3. Обновляет статус синхронизации
"""

import asyncio
import asyncpg
import subprocess
from pathlib import Path
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/knowledge")
SYNC_SCRIPT = Path(__file__).parent.parent / "scripts" / "sync_cursor_rules.py"
CHECK_INTERVAL = 30  # секунд


class CursorRulesAutoSync:
    """Автоматическая синхронизация .cursor/rules/ при изменениях экспертов."""
    
    def __init__(self):
        self.db_pool = None
        self.running = False
    
    async def start(self):
        """Запустить worker."""
        print("🚀 Запуск CursorRulesAutoSync worker...")
        
        self.db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=2)
        self.running = True
        
        print(f"✅ Worker запущен (проверка каждые {CHECK_INTERVAL}с)")
        
        try:
            while self.running:
                await self.check_and_sync()
                await asyncio.sleep(CHECK_INTERVAL)
        finally:
            await self.db_pool.close()
    
    async def check_and_sync(self):
        """Проверить изменения и синхронизировать если нужно."""
        try:
            # Получаем pending изменения
            async with self.db_pool.acquire() as conn:
                changes = await conn.fetch("""
                    SELECT * FROM get_pending_expert_changes()
                """)
            
            if not changes:
                return
            
            print(f"\n⚠️  Обнаружено {len(changes)} изменений экспертов:")
            for change in changes:
                event_icon = {
                    'INSERT': '➕',
                    'UPDATE': '🔄',
                    'DELETE': '➖'
                }.get(change['event_type'], '❓')
                
                print(f"   {event_icon} {change['event_type']}: {change['expert_name']} ({change['expert_role']})")
            
            # Запускаем синхронизацию
            print(f"\n🔄 Запуск синхронизации...")
            result = subprocess.run(
                ["python", str(SYNC_SCRIPT)],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print("✅ Синхронизация успешна!")
                
                # Отмечаем все изменения как синхронизированные
                async with self.db_pool.acquire() as conn:
                    for change in changes:
                        await conn.execute(
                            "SELECT mark_expert_change_synced($1)",
                            change['id']
                        )
                
                print(f"✅ Отмечено {len(changes)} изменений как синхронизированные")
                
                # Опционально: коммит в git
                if os.getenv("AUTO_COMMIT_CURSOR_RULES", "false").lower() == "true":
                    await self.git_commit_changes(changes)
            else:
                print(f"❌ Ошибка синхронизации: {result.stderr}")
        
        except Exception as e:
            print(f"❌ Ошибка в check_and_sync: {e}")
    
    async def git_commit_changes(self, changes):
        """Автоматический коммит изменений в git."""
        try:
            project_root = Path(__file__).parent.parent
            
            # Формируем commit message
            change_types = {}
            for change in changes:
                event = change['event_type']
                change_types[event] = change_types.get(event, 0) + 1
            
            msg_parts = []
            if change_types.get('INSERT'):
                msg_parts.append(f"Найм: {change_types['INSERT']}")
            if change_types.get('UPDATE'):
                msg_parts.append(f"Изменение: {change_types['UPDATE']}")
            if change_types.get('DELETE'):
                msg_parts.append(f"Увольнение: {change_types['DELETE']}")
            
            commit_msg = f"Auto-sync .cursor/rules/ ({', '.join(msg_parts)})"
            
            # Git операции
            subprocess.run(["git", "add", ".cursor/rules/"], cwd=project_root, check=True)
            subprocess.run(["git", "commit", "-m", commit_msg], cwd=project_root, check=True)
            
            print(f"✅ Git commit: {commit_msg}")
            
        except subprocess.CalledProcessError as e:
            print(f"⚠️  Git commit не удался (может быть нечего коммитить): {e}")
    
    async def stop(self):
        """Остановить worker."""
        print("🛑 Остановка CursorRulesAutoSync worker...")
        self.running = False


async def main():
    """Основная функция."""
    worker = CursorRulesAutoSync()
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        print("\n⚠️  Получен сигнал остановки...")
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
