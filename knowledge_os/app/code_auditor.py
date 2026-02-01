import asyncio
import os
import json
import asyncpg
import subprocess
from datetime import datetime, timezone
from resource_manager import acquire_resource_lock

# Import Code-Smell Predictor (Singularity 9.0)
try:
    from code_smell_predictor import CodeSmellPredictor
    CODE_SMELL_PREDICTOR_AVAILABLE = True
except ImportError:
    CODE_SMELL_PREDICTOR_AVAILABLE = False

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

PROJECT_ROOT = "/root/knowledge_os"

def run_cursor_agent(prompt: str):
    """Run cursor-agent CLI to process a prompt and return output."""
    try:
        env = os.environ.copy()
        result = subprocess.run(
            ["/root/.local/bin/cursor-agent", "--print", prompt],
            capture_output=True,
            text=True,
            check=True,
            timeout=600,
            env=env
        )
        return result.stdout
    except Exception as e:
        print(f"Error running cursor-agent for audit: {e}")
        return None

async def run_code_audit():
    async with acquire_resource_lock("code_auditor"):
        print("🎭 Starting Cognitive Mirror (Code Auditor)...")
        conn = await asyncpg.connect(DB_URL)
        
        # 1. Собираем список файлов и логи последних ошибок
        files = []
        for root, dirs, filenames in os.walk(os.path.join(PROJECT_ROOT, "app")):
            for f in filenames:
                if f.endswith(".py"):
                    files.append(f) # Только имена файлов для экономии места
        
        log_dir = os.path.join(PROJECT_ROOT, "logs")
        logs_content = ""
        if os.path.exists(log_dir):
            for f in os.listdir(log_dir):
                if f.endswith(".log"):
                    try:
                        with open(os.path.join(log_dir, f), 'r', encoding='utf-8') as log_file:
                            content = log_file.read()
                            logs_content += f"\n--- {f} ---\n" + content[-1000:] # Последние 1КБ логов на файл
                    except (IOError, OSError, UnicodeDecodeError) as e:
                        print(f"⚠️ Error reading log file {f}: {e}")
                    except Exception as e:
                        print(f"⚠️ Unexpected error reading log {f}: {e}")
        
        # Ограничиваем общий размер промпта
        if len(logs_content) > 3000:
            logs_content = logs_content[-3000:]

        # 2. Промпт для аудита кода
        audit_prompt = f"""
        ТЫ - ГЛАВНЫЙ АРХИТЕКТОР И SRE КОРПОРАЦИИ.
        ТВОЯ ЗАДАЧА: Проведи аудит собственного кода и логов на предмет ошибок, уязвимостей и неэффективности.
        
        СПИСОК ФАЙЛОВ: {files}
        ПОСЛЕДНИЕ ЛОГИ:
        {logs_content}
        
        ЗАДАЧА:
        1. Проанализируй логи на предмет повторяющихся ошибок.
        2. Найди потенциальные "бутылочные горлышки" в архитектуре.
        3. Сгенерируй список конкретных задач по исправлению.
        
        ВЕРНИ JSON СПИСОК ЗАДАЧ:
        [
            {{
                "title": "Заголовок задачи",
                "description": "Подробное описание и что исправить",
                "department": "Backend/DevOps/ML",
                "severity": "high/medium/low"
            }}
        ]
        ВЕРНИ ТОЛЬКО JSON.
        """
        
        output = run_cursor_agent(audit_prompt)
        
        if output:
            try:
                clean_json = output.strip()
                if "```json" in clean_json:
                    parts = clean_json.split("```json", 1)[1].split("```", 1)
                    clean_json = parts[0].strip()
                elif "```" in clean_json:
                    parts = clean_json.split("```", 2)
                    clean_json = (parts[1] if len(parts) > 1 else parts[0]).strip()
                clean_json = clean_json.strip()
                if not clean_json:
                    print("⚠️ Пустой JSON после извлечения из markdown")
                    await conn.close()
                    return
                try:
                    tasks = json.loads(clean_json)
                except json.JSONDecodeError as je:
                    print(f"❌ Ошибка парсинга JSON: {je}")
                    await conn.close()
                    return
                if isinstance(tasks, dict):
                    tasks = [tasks] if tasks else []
                if not isinstance(tasks, list):
                    tasks = []
                
                victoria_id = await conn.fetchval("SELECT id FROM experts WHERE name = 'Виктория'")
                
                # Инициализируем Code-Smell Predictor (Singularity 9.0)
                predictor = None
                if CODE_SMELL_PREDICTOR_AVAILABLE:
                    try:
                        predictor = CodeSmellPredictor()
                    except Exception as e:
                        print(f"⚠️ Error initializing Code-Smell Predictor: {e}")
                
                for t in tasks:
                    # Находим подходящего эксперта
                    assignee = await conn.fetchrow("""
                        SELECT id FROM experts 
                        WHERE department = $1 OR role ILIKE $2 
                        ORDER BY RANDOM() LIMIT 1
                    """, t['department'], f"%{t['department']}%")
                    
                    assignee_id = assignee['id'] if assignee else victoria_id
                    
                    # Code-Smell Predictor: предсказываем вероятность бага (Singularity 9.0)
                    bug_probability = 0.0
                    predicted_issues = {}
                    
                    if predictor and t.get('description'):
                        try:
                            # Извлекаем код из описания задачи (если есть)
                            code_snippet = t['description'][:500]  # Первые 500 символов
                            
                            # Предсказываем баги
                            prediction = predictor.predict_bugs(
                                file_path=f"audit_task_{t['title']}",
                                code=code_snippet
                            )
                            
                            bug_probability = prediction.bug_probability
                            predicted_issues = prediction.predicted_issues
                            
                            # Сохраняем предсказание в БД
                            await predictor.save_prediction(prediction)
                            
                            # Фильтруем задачи по bug_probability > 0.5
                            if bug_probability < 0.5:  # MIN_BUG_PROBABILITY = 0.5
                                print(f"⏭️ Skipping task {t['title']} (bug_probability: {bug_probability:.2f} < {MIN_BUG_PROBABILITY})")
                                continue
                            
                            print(f"🐛 [CODE SMELL] Task {t['title']}: bug_probability={bug_probability:.2f}, issues={prediction.likely_issues}")
                        except Exception as e:
                            print(f"⚠️ Error predicting bugs: {e}")
                    
                    # 🌟 МИРОВЫЕ ПРАКТИКИ: Извлекаем file_path из описания задачи
                    file_path = None
                    if t.get('description'):
                        # Ищем паттерны типа "app.py", "knowledge_os/dashboard/app.py", "Местоположение: app.py"
                        import re
                        path_patterns = [
                            r'Местоположение:\s*([^\s]+\.(py|js|ts|tsx|yml|yaml|json|md))',
                            r'файл[:\s]+([^\s]+\.(py|js|ts|tsx|yml|yaml|json|md))',
                            r'file[:\s]+([^\s]+\.(py|js|ts|tsx|yml|yaml|json|md))',
                            r'([a-zA-Z0-9_/\\-]+\.(py|js|ts|tsx|yml|yaml|json|md))',
                        ]
                        for pattern in path_patterns:
                            match = re.search(pattern, t['description'], re.IGNORECASE)
                            if match:
                                file_path = match.group(1)
                                # Нормализуем путь
                                if not file_path.startswith('/') and 'knowledge_os' not in file_path:
                                    # Пробуем найти полный путь
                                    if 'dashboard' in t['description'].lower() or 'app.py' in file_path:
                                        file_path = 'knowledge_os/dashboard/app.py'
                                    elif 'code_auditor' in file_path or 'auditor' in file_path:
                                        file_path = 'knowledge_os/app/code_auditor.py'
                                break
                    
                    # Создаем задачу с меткой bug_probability и file_path в metadata
                    task_metadata = {
                        "source": "code_auditor",
                        "severity": t['severity'],
                        "bug_probability": bug_probability,
                        "predicted_issues": predicted_issues
                    }
                    
                    # 🌟 Добавляем file_path если найден
                    if file_path:
                        task_metadata["file_path"] = file_path
                        # Извлекаем ключевые слова из описания для selective context
                        keywords = []
                        if 'ошибка' in t['description'].lower() or 'error' in t['description'].lower():
                            keywords.append('error')
                            keywords.append('except')
                        if 'try' in t['description'].lower():
                            keywords.append('try')
                        if 'подключение' in t['description'].lower() or 'connection' in t['description'].lower():
                            keywords.append('connection')
                            keywords.append('connect')
                        if keywords:
                            task_metadata["keywords"] = keywords
                    
                    await conn.execute("""
                        INSERT INTO tasks (title, description, status, assignee_expert_id, creator_expert_id, metadata)
                        VALUES ($1, $2, 'pending', $3, $4, $5)
                    """, f"🤖 AUTO-AUDIT: {t['title']}", t['description'], assignee_id, victoria_id, 
                    json.dumps(task_metadata))
                    
                    print(f"📌 Created auto-audit task: {t['title']} ({t['severity']})")

                    # Если критично - пишем в нотификации
                    if t['severity'] == 'high':
                        await conn.execute("""
                            INSERT INTO notifications (message, type)
                            VALUES ($1, 'system_alert')
                        """, f"🧨 CRITICAL AUDIT: {t['title']}")

            except Exception as e:
                print(f"❌ Error parsing audit output: {e}")

        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_code_audit())

