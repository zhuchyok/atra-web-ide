"""
Deploy Singularity 9.0: Применение миграций и установка cron jobs

Функционал:
- Применение SQL миграций для Singularity 9.0
- Установка cron jobs
- Проверка готовности системы
"""

import asyncio
import os
import sys
import subprocess
from pathlib import Path

# Добавляем путь к app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../app'))

from evaluator import get_pool

PROJECT_ROOT = Path(__file__).parent.parent
MIGRATIONS_DIR = PROJECT_ROOT / 'db' / 'migrations'
CRON_DIR = PROJECT_ROOT / 'infrastructure' / 'cron'


async def apply_migrations():
    """Применяет SQL миграции для Singularity 9.0"""
    print("📊 [SINGULARITY 9 DEPLOY] Применение SQL миграций...")
    
    migrations = [
        ('add_tacit_knowledge_tables.sql', 'user_style_profiles'),
        ('add_emotion_tables.sql', 'emotion_logs'),
        ('add_code_smell_tables.sql', 'code_smell_predictions')
    ]
    
    pool = await get_pool()
    async with pool.acquire() as conn:
        for migration_file, table_name in migrations:
            try:
                # Проверяем, существует ли таблица
                exists = await conn.fetchval(f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{table_name}')")
                if exists:
                    print(f"✅ Таблица {table_name} уже существует")
                    continue
                
                # Читаем SQL файл
                migration_path = MIGRATIONS_DIR / migration_file
                if not migration_path.exists():
                    print(f"⚠️ Файл миграции не найден: {migration_path}")
                    continue
                
                with open(migration_path, 'r') as f:
                    sql = f.read()
                
                # Применяем миграцию
                await conn.execute(sql)
                print(f"✅ Миграция {migration_file} применена (таблица {table_name})")
            except Exception as e:
                print(f"❌ Ошибка применения {migration_file}: {e}")
                import traceback
                traceback.print_exc()


def install_cron_jobs():
    """Устанавливает cron jobs для Singularity 9.0"""
    print("⏰ [SINGULARITY 9 DEPLOY] Установка cron jobs...")
    
    cron_files = [
        'tacit_knowledge_updater.cron',
        'predictive_compression.cron',
        'validate_singularity_9_metrics.cron'
    ]
    
    cron_entries = []
    
    for cron_file in cron_files:
        cron_path = CRON_DIR / cron_file
        if cron_path.exists():
            with open(cron_path, 'r') as f:
                content = f.read().strip()
                if content and not content.startswith('#'):
                    cron_entries.append(content)
                    print(f"✅ Cron job из {cron_file} добавлен")
        else:
            print(f"⚠️ Cron файл не найден: {cron_path}")
    
    if cron_entries:
        # Получаем текущий crontab
        try:
            result = subprocess.run(['crontab', '-l'], capture_output=True, text=True, check=False)
            current_cron = result.stdout if result.returncode == 0 else ""
        except:
            current_cron = ""
        
        # Добавляем новые cron jobs (если их еще нет)
        new_entries = []
        for entry in cron_entries:
            # Проверяем по части cron команды (без комментариев)
            entry_cmd = entry.split('\n')[-1] if '\n' in entry else entry
            # Убираем комментарии для проверки
            entry_cmd_clean = entry_cmd.split('#')[0].strip()
            
            # Проверяем, есть ли похожая команда в текущем crontab
            found = False
            for line in current_cron.split('\n'):
                line_clean = line.split('#')[0].strip()
                # Проверяем по ключевым словам из команды
                if entry_cmd_clean and len(entry_cmd_clean) > 20:
                    key_words = [w for w in entry_cmd_clean.split() if len(w) > 5]
                    if key_words and any(kw in line_clean for kw in key_words):
                        found = True
                        break
            
            if not found:
                new_entries.append(entry)
            else:
                print(f"⚠️ Cron job уже установлен: {entry_cmd_clean[:60]}...")
        
        if new_entries:
            # Обновляем crontab
            new_cron = current_cron.rstrip() + "\n\n" + "\n".join(new_entries) + "\n"
            process = subprocess.Popen(['crontab', '-'], stdin=subprocess.PIPE, text=True)
            process.communicate(input=new_cron)
            
            if process.returncode == 0:
                print(f"✅ {len(new_entries)} cron jobs установлено")
            else:
                print(f"❌ Ошибка установки cron jobs: returncode {process.returncode}")
        else:
            print("ℹ️ Все cron jobs уже установлены")
    else:
        print("⚠️ Нет cron jobs для установки")


async def verify_deployment():
    """Проверяет готовность системы Singularity 9.0"""
    print("🔍 [SINGULARITY 9 DEPLOY] Проверка готовности системы...")
    
    # Проверяем таблицы
    pool = await get_pool()
    async with pool.acquire() as conn:
        tables = ['user_style_profiles', 'emotion_logs', 'code_smell_predictions', 'code_smell_training_data']
        for table in tables:
            exists = await conn.fetchval(f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{table}')")
            status = "✅" if exists else "❌"
            print(f"{status} Таблица {table}: {'существует' if exists else 'не существует'}")
    
    # Проверяем Python модули
    modules = [
        'tacit_knowledge_miner',
        'emotion_detector',
        'code_smell_predictor',
        'code_smell_model_trainer',
        'singularity_9_ab_tester',
        'context_analyzer'
    ]
    
    app_dir = PROJECT_ROOT / 'app'
    for module in modules:
        module_file = app_dir / f"{module}.py"
        exists = module_file.exists()
        status = "✅" if exists else "❌"
        print(f"{status} Модуль {module}: {'существует' if exists else 'не существует'}")


async def main():
    """Основная функция деплоя"""
    print("🚀 [SINGULARITY 9 DEPLOY] Начало деплоя...")
    print("")
    
    # Применяем миграции
    await apply_migrations()
    print("")
    
    # Устанавливаем cron jobs
    install_cron_jobs()
    print("")
    
    # Проверяем готовность
    await verify_deployment()
    print("")
    
    print("✅ [SINGULARITY 9 DEPLOY] Деплой завершен!")


if __name__ == "__main__":
    asyncio.run(main())

