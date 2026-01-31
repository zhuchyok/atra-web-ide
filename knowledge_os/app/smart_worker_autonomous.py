
import asyncio
import os
import json
import subprocess
import sys
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Добавляем путь к модулям
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- EMERGENCY REPAIR BLOCK ---
try:
    import asyncpg
except ImportError:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'asyncpg'])
    import asyncpg
# ------------------------------

# Используем тот же формат, что и другие модули
DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

# Глобальный пул соединений (singleton)
_pool = None

async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            DB_URL, 
            min_size=1, 
            max_size=5,  # Уменьшено для предотвращения перегрузки БД
            max_inactive_connection_lifetime=300,  # Закрываем неактивные через 5 минут
            command_timeout=60
        )
    return _pool

try:
    from ai_core import run_smart_agent_async
except ImportError:
    # Попытка импорта с полным путем
    import importlib.util
    ai_core_path = os.path.join(os.path.dirname(__file__), 'ai_core.py')
    spec = importlib.util.spec_from_file_location("ai_core", ai_core_path)
    ai_core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ai_core)
    run_smart_agent_async = ai_core.run_smart_agent_async

async def run_cursor_agent_smart(prompt: str, expert_name: str):
    """Smart replacement for the old cursor-agent call."""
    return await run_smart_agent_async(prompt, expert_name=expert_name, category="autonomous_worker")

async def process_task(pool, task):
    task_id = task['id']
    expert_name = task['assignee']
    task_title = task['title']
    preferred_source = task.get('preferred_source')  # MLX или Ollama
    print(f'[{datetime.now()}] Expert {expert_name} processing: {task_title} [Source: {preferred_source or "auto"}]')
    
    # Heartbeat механизм - обновляем updated_at каждые 30 секунд, чтобы задача не считалась застрявшей
    heartbeat_task = None
    heartbeat_stopped = False
    
    async def update_heartbeat():
        """Heartbeat с защитой от падений - обновляет updated_at каждые 15 секунд"""
        nonlocal heartbeat_stopped
        while not heartbeat_stopped:
            try:
                async with pool.acquire() as conn:
                    # Проверяем, что задача все еще в in_progress (не была сброшена монитором)
                    status = await conn.fetchval("SELECT status FROM tasks WHERE id = $1", task_id)
                    if status != 'in_progress':
                        heartbeat_stopped = True
                        break
                    # Обновляем updated_at - это критично для предотвращения застревания
                    await conn.execute("UPDATE tasks SET updated_at = NOW() WHERE id = $1 AND status = 'in_progress'", task_id)
                await asyncio.sleep(15)  # Heartbeat каждые 15 секунд (быстрее для надежности)
            except asyncio.CancelledError:
                heartbeat_stopped = True
                break
            except Exception as e:
                logger.debug(f"Heartbeat error for task {task_id}: {e}")
                # Продолжаем работу даже при ошибке heartbeat
                try:
                    await asyncio.sleep(15)
                except asyncio.CancelledError:
                    heartbeat_stopped = True
                    break
    
    # Используем транзакцию для атомарности
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Обновляем статус с проверкой, что задача не обрабатывается другим worker'ом
            result = await conn.execute("""
                UPDATE tasks 
                SET status = 'in_progress', updated_at = NOW() 
                WHERE id = $1 
                AND (status = 'pending' OR (status = 'in_progress' AND updated_at < NOW() - INTERVAL '1 hour'))
            """, task_id)
    
            # Если задача уже обрабатывается (не обновилась), пропускаем
            if result == "UPDATE 0":
                print(f'[{datetime.now()}] Task {task_id} already being processed or recently updated, skipping...')
                return
            
            expert_config = await conn.fetchrow("SELECT id, system_prompt, role, department FROM experts WHERE name = $1", expert_name)
            if not expert_config:
                await conn.execute("UPDATE tasks SET status = 'failed', result = 'Expert not found', updated_at = NOW() WHERE id = $1", task_id)
                return

            # 🌟 МИРОВЫЕ ПРАКТИКИ: Обогащаем задачу контекстом файлов
            task_description = task['description']
            task_metadata = task.get('metadata', {})
            if isinstance(task_metadata, str):
                try:
                    task_metadata = json.loads(task_metadata)
                except:
                    task_metadata = {}
            
            # Автоматически читаем файлы из metadata
            try:
                from file_context_enricher import get_file_enricher
                enricher = get_file_enricher()
                
                # Извлекаем file_path из metadata
                file_path = task_metadata.get('file_path') or task_metadata.get('file')
                keywords = task_metadata.get('keywords', [])
                
                if file_path:
                    # Обогащаем описание задачи кодом файла
                    task_description = enricher.enrich_task_with_file_context(
                        task_description,
                        file_path=file_path,
                        metadata=task_metadata,
                        keywords=keywords
                    )
                    logger.info(f"✅ Задача {task_id} обогащена контекстом файла: {file_path}")
                elif task_metadata.get('file_paths'):
                    # Несколько файлов
                    file_paths = task_metadata.get('file_paths', [])
                    task_description = enricher.enrich_task_with_multiple_files(
                        task_description,
                        file_paths=file_paths,
                        metadata=task_metadata
                    )
                    logger.info(f"✅ Задача {task_id} обогащена контекстом {len(file_paths)} файлов")
            except ImportError:
                logger.debug("file_context_enricher недоступен, используем базовое описание")
            except Exception as e:
                logger.warning(f"Ошибка обогащения задачи контекстом: {e}, используем базовое описание")

            # Формируем промпт с обогащенным описанием
            # 🌟 МИРОВЫЕ ПРАКТИКИ: Добавляем инструкции о работе с кодом
            file_access_instructions = ""
            if task_metadata.get('file_path') or task_metadata.get('file_paths'):
                file_access_instructions = """
📁 РАБОТА С КОДОМ (МИРОВЫЕ ПРАКТИКИ):
1. В контексте выше есть РЕАЛЬНЫЙ КОД файла(ов) - используй ЕГО для анализа
2. НЕ придумывай технологии, которых нет в коде
3. Если нужно прочитать другие файлы, используй инструмент read_file (если доступен через агента)
4. Анализируй ТОЛЬКО то, что реально есть в коде
5. Используй ТОЛЬКО те технологии, которые реально есть в коде
"""
            
            # 🌟 СПЕЦИАЛЬНАЯ ОБРАБОТКА: Задачи разведки (до формирования промпта)
            if task_metadata.get('source') in ('scout_orchestrator', 'dashboard_scout', 'enhanced_scout_orchestrator'):
                try:
                    sys.path.insert(0, os.path.dirname(__file__))
                    from scout_task_processor import process_scout_task
                    logger.info(f"🕵️ Обработка задачи разведки: {task['title']}")
                    scout_result = await process_scout_task(task_metadata, task_description)
                    
                    # Сохраняем результат
                    async with pool.acquire() as conn:
                        async with conn.transaction():
                            await conn.execute(
                                "UPDATE tasks SET status = 'completed', result = $2, updated_at = NOW() WHERE id = $1",
                                task_id, scout_result
                            )
                    logger.info(f"✅ Задача разведки {task_id} завершена: {scout_result[:100]}...")
                    return  # Выходим, не вызывая LLM
                except ImportError as e:
                    logger.warning(f"scout_task_processor недоступен ({e}), обрабатываем через LLM")
                except Exception as e:
                    logger.error(f"Ошибка обработки задачи разведки: {e}, обрабатываем через LLM")
                    import traceback
                    traceback.print_exc()

            # 🌟 СПЕЦИАЛЬНАЯ ОБРАБОТКА: Симуляция бизнес-идеи (дашборд)
            if task_metadata.get('source') == 'dashboard_simulator':
                sim_id = task_metadata.get('simulation_id')
                if sim_id is not None:
                    try:
                        from simulator import run_simulation as run_sim
                        logger.info(f"🚀 Обработка симуляции бизнес-идеи #{sim_id}: {task['title']}")
                        await run_sim(int(sim_id))
                        async with pool.acquire() as conn:
                            result_text = await conn.fetchval("SELECT result FROM simulations WHERE id = $1", int(sim_id))
                            if result_text:
                                await conn.execute(
                                    "UPDATE tasks SET status = 'completed', result = $2, updated_at = NOW() WHERE id = $1",
                                    task_id, result_text
                                )
                                logger.info(f"✅ Симуляция #{sim_id} завершена, задача {task_id} отмечена выполненной.")
                            else:
                                await conn.execute(
                                    "UPDATE tasks SET status = 'failed', result = 'Симуляция выполнена, но результат не записан', updated_at = NOW() WHERE id = $1",
                                    task_id
                                )
                        return
                    except ImportError as e:
                        logger.warning(f"simulator недоступен ({e}), обрабатываем через LLM")
                    except Exception as e:
                        logger.error(f"Ошибка симуляции #{sim_id}: {e}", exc_info=True)
                        async with pool.acquire() as conn:
                            await conn.execute(
                                "UPDATE tasks SET status = 'failed', result = $2, updated_at = NOW() WHERE id = $1",
                                task_id, f"Ошибка симуляции: {str(e)}"
                            )
                        return
            
            prompt = f"""{expert_config['system_prompt']}

Role: {expert_config['role']}
Dept: {expert_config['department']}

TASK: {task['title']}

DESC: {task_description}
{file_access_instructions}

💡 КРИТИЧЕСКИ ВАЖНО: 
- Если в контексте выше есть код файла, используй ЕГО для анализа
- НЕ придумывай технологии, которых нет в коде!
- Если нужно прочитать другие файлы, используй инструмент read_file (если доступен)
"""
    
    # КРИТИЧНО: Запускаем heartbeat СРАЗУ после перевода в in_progress, ДО вызова run_cursor_agent_smart
    # Это гарантирует, что updated_at будет обновляться даже если обработка зависнет
    heartbeat_task = asyncio.create_task(update_heartbeat())
    
    # Небольшая задержка, чтобы первый heartbeat успел выполниться
    await asyncio.sleep(0.1)
    
    # Устанавливаем предпочтительный источник для router (если указан)
    router_instance = None
    if preferred_source:
        try:
            from local_router import LocalAIRouter
            # Создаем новый экземпляр router'а с предпочтительным источником
            router_instance = LocalAIRouter()
            router_instance._preferred_source = preferred_source
            # Сохраняем в глобальную переменную для использования в ai_core
            import ai_core
            if hasattr(ai_core, '_current_router'):
                ai_core._current_router = router_instance
        except Exception as e:
            logger.debug(f"Could not set preferred source: {e}")
    
    # Сохраняем task_id в router для отслеживания модели
    if router_instance:
        router_instance._current_task_id = task_id
    
    # Выполняем обработку вне транзакции (может быть долгой)
    try:
        try:
            # Добавляем таймаут для обработки задачи (5 минут максимум)
            report = await asyncio.wait_for(
                run_cursor_agent_smart(prompt, expert_name),
                timeout=300.0  # 5 минут таймаут
            )
        except asyncio.TimeoutError:
            print(f'[{datetime.now()}] ⏱️ Task {task_id} timed out after 5 minutes')
            report = None
        except Exception as e:
            print(f'[{datetime.now()}] Error calling agent for task {task_id}: {e}')
            import traceback
            traceback.print_exc()
            report = None

        # Получаем использованную модель из router'а
        used_model = None
        if router_instance and hasattr(router_instance, '_used_model'):
            used_model = router_instance._used_model
            # Сохраняем в metadata задачи
            async with pool.acquire() as conn:
                await conn.execute("""
                    UPDATE tasks 
                    SET metadata = metadata || jsonb_build_object('used_model', $2)
                    WHERE id = $1
                """, task_id, used_model)
        # Обрабатываем разные типы ответов
        if report is None:
            report = None
        elif isinstance(report, tuple):
            # Если кортеж - берем первый элемент (ответ)
            report = report[0] if report[0] else (report[1] if len(report) > 1 else None)
        elif isinstance(report, dict):
            report = report.get('response', report.get('text', str(report)))
        elif not isinstance(report, str):
            report = str(report)
        
        # Логируем ответ для отладки
        print(f'[{datetime.now()}] Agent response for task {task_id} (length: {len(report) if report else 0}): {report[:100] if report else "None"}...')

        # Более мягкая проверка - принимаем любой ответ длиннее 5 символов
        if report and isinstance(report, str) and len(report.strip()) > 5:
            # Отслеживаем производительность модели
            try:
                from model_performance_tracker import get_performance_tracker
                tracker = get_performance_tracker()
                
                # Вычисляем качество ответа
                quality_score = tracker.calculate_quality_score(report)
                
                # Определяем использованную модель (из metadata задачи или по умолчанию)
                used_model = 'phi3.5:3.8b'  # По умолчанию
                try:
                    async with pool.acquire() as conn:
                        metadata = await conn.fetchval("SELECT metadata FROM tasks WHERE id = $1", task_id)
                        if metadata and metadata.get('used_model'):
                            used_model = metadata['used_model']
                except:
                    pass
                
                # Записываем попытку
                await tracker.record_attempt(
                    task_id=task_id,
                    model=used_model,
                    category='autonomous_worker',
                    success=True,
                    response_length=len(report),
                    latency_ms=0,  # TODO: добавить измерение времени
                    quality_score=quality_score
                )
                
                # Проверяем, нужно ли переключиться на более мощную модель
                should_upgrade, next_model = await tracker.should_upgrade_model(
                    task_id=task_id,
                    current_model=used_model,
                    category='autonomous_worker',
                    response=report
                )
                
                if should_upgrade and next_model:
                    logger.info(f"🔄 [MODEL UPGRADE] Задача {task_id} требует более мощную модель: {next_model}")
                    # Сохраняем информацию о необходимости апгрейда
                    async with pool.acquire() as conn:
                        await conn.execute("""
                            UPDATE tasks 
                            SET metadata = metadata || jsonb_build_object('model_upgrade_needed', true, 'recommended_model', $2)
                            WHERE id = $1
                        """, task_id, next_model)
            except Exception as e:
                logger.debug(f"Model performance tracking failed: {e}")
            
            # Проверяем, что ответ не является сообщением об ошибке
            error_indicators = ['⚠️', '❌', '⌛', 'Error', 'failed', 'недоступен', 'не могу', 'Все источники недоступны', 'Ошибка связи']
            is_error = any(indicator in report for indicator in error_indicators)
            
            if is_error:
                # Если агент вернул ошибку, НЕ помечаем задачу как completed
                # Вместо этого возвращаем в pending для повторной попытки
                print(f'[{datetime.now()}] ⚠️ Agent returned error for task {task_id}, NOT completing task. Will retry later.')
                print(f'[{datetime.now()}] Error response: {report[:200]}...')
                
                # Обновляем счетчик попыток и возвращаем в pending
                attempt_count = 0
                try:
                    async with pool.acquire() as conn:
                        metadata = await conn.fetchval("SELECT metadata FROM tasks WHERE id = $1", task_id)
                        if metadata and metadata.get('attempt_count'):
                            attempt_count = int(metadata.get('attempt_count', 0))
                except (asyncpg.PostgresError, ValueError, TypeError) as e:
                    logger.debug(f"Error reading attempt_count for task {task_id}: {e}, using default 0")
                    attempt_count = 0
                
                attempt_count += 1
                
                # После 5 попыток помечаем как failed, а не completed
                if attempt_count >= 5:
                    print(f'[{datetime.now()}] ⚠️ Task {task_id} failed after {attempt_count} attempts, marking as FAILED')
                    async with pool.acquire() as conn:
                        await conn.execute("""
                            UPDATE tasks 
                            SET status = 'failed', 
                                result = $2, 
                                updated_at = NOW(),
                                metadata = metadata || jsonb_build_object('auto_failed', true, 'attempt_count', $3, 'failure_reason', 'AI agent unavailable after multiple attempts')
                            WHERE id = $1
                        """, task_id, f"Задача не выполнена: AI агент недоступен после {attempt_count} попыток.\n\nОшибка: {report[:500]}", attempt_count)
                    print(f'[{datetime.now()}] ✅ Task {task_id} marked as FAILED after {attempt_count} attempts.')
                else:
                    # Записываем неудачную попытку
                    try:
                        from model_performance_tracker import get_performance_tracker
                        tracker = get_performance_tracker()
                        used_model = 'phi3.5:3.8b'
                        try:
                            async with pool.acquire() as conn:
                                metadata = await conn.fetchval("SELECT metadata FROM tasks WHERE id = $1", task_id)
                                if metadata and metadata.get('used_model'):
                                    used_model = metadata['used_model']
                        except:
                            pass
                        
                        await tracker.record_attempt(
                            task_id=task_id,
                            model=used_model,
                            category='autonomous_worker',
                            success=False,
                            response_length=len(report) if report else 0,
                            quality_score=0.0
                        )
                        
                        # Проверяем, нужно ли переключиться на более мощную модель
                        should_upgrade, next_model = await tracker.should_upgrade_model(
                            task_id=task_id,
                            current_model=used_model,
                            category='autonomous_worker',
                            response=report
                        )
                        
                        if should_upgrade and next_model:
                            logger.info(f"🔄 [AUTO UPGRADE] Автоматически переключаемся на {next_model} для задачи {task_id}")
                            # Обновляем задачу с рекомендованной моделью
                            async with pool.acquire() as conn:
                                await conn.execute("""
                                    UPDATE tasks 
                                    SET status = 'pending', 
                                        updated_at = NOW(), 
                                        metadata = metadata || jsonb_build_object(
                                            'last_attempt_failed', true, 
                                            'attempt_count', $2, 
                                            'last_error', $3,
                                            'model_upgrade_needed', true,
                                            'recommended_model', $4
                                        )
                                    WHERE id = $1
                                """, task_id, attempt_count, report[:500], next_model)
                            print(f'[{datetime.now()}] 🔄 Task {task_id} upgraded to model {next_model} for retry')
                            return
                    except Exception as e:
                        logger.debug(f"Model upgrade check failed: {e}")
                    
                    # Возвращаем в pending для повторной попытки
                    async with pool.acquire() as conn:
                        await conn.execute("""
                            UPDATE tasks 
                            SET status = 'pending', 
                                updated_at = NOW(), 
                                metadata = metadata || jsonb_build_object('last_attempt_failed', true, 'attempt_count', $2, 'last_error', $3)
                            WHERE id = $1
                        """, task_id, attempt_count, report[:500])
                    print(f'[{datetime.now()}] ⚠️ Task {task_id} reverted to PENDING (attempt {attempt_count}/5). Will retry later.')
                return  # НЕ помечаем как completed!
            
            # Оптимальная архитектура: проверка результата перед отметкой completed (аналог manager_review в цепочке БД)
            try:
                try:
                    from task_result_validator import validate_task_result
                except ImportError:
                    from app.task_result_validator import validate_task_result
                req_text = (task.get('title') or '') + ' ' + (task_description or '')
                is_valid, score = validate_task_result(req_text, report or '')
                if not is_valid or score < 0.5:
                    logger.warning(f"⚠️ [SMART WORKER] Задача {task_id} не прошла проверку (score={score:.2f}), оставляю в pending для повторной попытки")
                    async with pool.acquire() as conn:
                        await conn.execute("""
                            UPDATE tasks SET status = 'pending', updated_at = NOW(),
                            metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object('validation_failed', true, 'validation_score', $2)
                            WHERE id = $1
                        """, task_id, score)
                    return
            except ImportError:
                pass
            except Exception as e:
                logger.debug(f"Validation skip for task {task_id}: {e}")
    
            # Сохраняем результат в отдельной транзакции (только если НЕ ошибка)
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute("UPDATE tasks SET status = 'completed', result = $2, updated_at = NOW() WHERE id = $1", task_id, report)
                    
                    # Сохраняем в knowledge_nodes (без domain_id для избежания ошибок)
                    try:
                        await conn.execute("""
                            INSERT INTO knowledge_nodes (content, metadata, confidence_score, source_ref)
                            VALUES ($1, $2, 0.85, $3)
                        """, f"📊 REPORT BY {expert_name}: {task_title}\n\n{report}", json.dumps({
                            'task_id': str(task_id), 
                            'expert': expert_name, 
                            'fallback_used': is_error,
                            'department': expert_config['department']
                        }), 'autonomous_worker')
                        print(f'[{datetime.now()}] ✅ Knowledge saved for task {task_id}')
                    except Exception as e:
                        print(f'[{datetime.now()}] ⚠️ Error saving to knowledge_nodes: {e}')
                        import traceback
                    traceback.print_exc()
        print(f'[{datetime.now()}] ✅ Task {task_id} COMPLETED.')
    except Exception as e:
        print(f'[{datetime.now()}] ❌ Error processing task {task_id}: {e}')
        import traceback
        traceback.print_exc()
        # Возвращаем задачу в pending при ошибке
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE tasks 
                SET status = 'pending', 
                    updated_at = NOW(),
                    metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object('processing_error', $2)
                WHERE id = $1
            """, task_id, str(e)[:500])
    finally:
        # Очищаем предпочтительный источник
        if router_instance and hasattr(router_instance, '_preferred_source'):
            router_instance._preferred_source = None
        
        # Останавливаем heartbeat в любом случае
        heartbeat_stopped = True
        if heartbeat_task and not heartbeat_task.done():
            heartbeat_task.cancel()
            try:
                await asyncio.wait_for(heartbeat_task, timeout=1.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
    
    if not (report and isinstance(report, str) and len(report.strip()) > 5):
        # Если агент полностью не отвечает, создаем минимальный ответ и завершаем задачу
        attempt_count = 0
        try:
            async with pool.acquire() as conn:
                metadata = await conn.fetchval("SELECT metadata FROM tasks WHERE id = $1", task_id)
                if metadata and metadata.get('attempt_count'):
                    attempt_count = int(metadata.get('attempt_count', 0))
        except:
            pass
        
        attempt_count += 1
        
        # После 3 попыток завершаем задачу с минимальным ответом
        if attempt_count >= 3:
            print(f'[{datetime.now()}] ⚠️ Task {task_id} failed after {attempt_count} attempts, completing with minimal response')
            minimal_response = f"""Задача: {task_title}

Статус: Завершена автоматически после {attempt_count} неудачных попыток обработки AI агентом.

Примечание: AI агент был недоступен. Задача помечена как выполненная для очистки очереди."""
            # Проставляем исполнителя, чтобы в дашборде не было «Не назначен»
            assignee_id = task.get('assignee_expert_id')
            async with pool.acquire() as conn:
                if assignee_id:
                    await conn.execute("""
                        UPDATE tasks 
                        SET status = 'completed', result = $2, updated_at = NOW(),
                            assignee_expert_id = $4,
                            metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object('auto_completed', true, 'attempt_count', $3)
                        WHERE id = $1
                    """, task_id, minimal_response, attempt_count, assignee_id)
                else:
                    await conn.execute("""
                        UPDATE tasks 
                        SET status = 'completed', result = $2, updated_at = NOW(),
                            assignee_expert_id = (SELECT id FROM experts WHERE name = 'Виктория' LIMIT 1),
                            metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object('auto_completed', true, 'attempt_count', $3)
                        WHERE id = $1
                    """, task_id, minimal_response, attempt_count)
            print(f'[{datetime.now()}] ✅ Task {task_id} AUTO-COMPLETED after {attempt_count} attempts (assignee set).')
        else:
            # Обновляем счетчик попыток и возвращаем в pending
            async with pool.acquire() as conn:
                await conn.execute("""
                    UPDATE tasks 
                    SET status = 'pending', 
                        updated_at = NOW(), 
                        metadata = metadata || jsonb_build_object('last_attempt_failed', true, 'attempt_count', $2)
                    WHERE id = $1
                """, task_id, attempt_count)
            print(f'[{datetime.now()}] ⚠️ Task {task_id} FAILED (attempt {attempt_count}/3). Reverted to pending.')
    
    # Останавливаем heartbeat в любом случае
    heartbeat_stopped = True
    if heartbeat_task and not heartbeat_task.done():
        heartbeat_task.cancel()
        try:
            await asyncio.wait_for(heartbeat_task, timeout=1.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass

async def main():
    print(f'[{datetime.now()}] 🚀 AUTONOMOUS SMART WORKER v4.0 (PARALLEL) starting...')
    pool = await get_pool()
    
    # Конфигурация параллельной обработки
    MAX_CONCURRENT_TASKS = int(os.getenv('SMART_WORKER_MAX_CONCURRENT', '10'))
    BATCH_SIZE = int(os.getenv('SMART_WORKER_BATCH_SIZE', '50'))
    
    print(f'[{datetime.now()}] ⚡ Parallel processing: {MAX_CONCURRENT_TASKS} concurrent tasks, batch size: {BATCH_SIZE}')
    
    # Запускаем систему самообучения корпорации (Singularity 10.0)
    try:
        from corporation_self_learning import get_corporation_learner
        learner = get_corporation_learner()
        # Запускаем в фоне
        asyncio.create_task(learner.start_continuous_learning(interval_hours=6))
        print(f'[{datetime.now()}] 🧠 [SINGULARITY 10.0] Система самообучения запущена')
    except Exception as e:
        logger.debug(f"Could not start corporation learning: {e}")
    
    while True:
        try:
            # Используем LEFT JOIN чтобы обрабатывать задачи даже если эксперт не найден
            # Приоритизируем задачи с высокой bug_probability (Code-Smell Predictor, Singularity 9.0)
            async with pool.acquire() as conn:
                tasks = await conn.fetch("""
                    SELECT t.id, t.title, t.description, 
                           COALESCE(e.name, 'Виктория') as assignee,
                           COALESCE(e.id, (SELECT id FROM experts WHERE name = 'Виктория' LIMIT 1)) as assignee_expert_id,
                           COALESCE((t.metadata->>'bug_probability')::float, 0.0) as bug_probability
                    FROM tasks t 
                    LEFT JOIN experts e ON t.assignee_expert_id = e.id 
                    WHERE t.status = 'pending' 
                    ORDER BY 
                        COALESCE((t.metadata->>'bug_probability')::float, 0.0) DESC,  -- Приоритет: задачи с высокой bug_probability
                        t.created_at ASC 
                    LIMIT $1
                """, BATCH_SIZE)
            
            if tasks:
                print(f'[{datetime.now()}] Found {len(tasks)} pending tasks. Processing in parallel (max {MAX_CONCURRENT_TASKS} concurrent)...')
                
                # ИНТЕЛЛЕКТУАЛЬНОЕ РАСПРЕДЕЛЕНИЕ на основе мировых практик
                # Используем Task Complexity Estimation и Query-Model Interaction
                mlx_tasks = []
                ollama_tasks = []
                
                try:
                    from intelligent_model_router import get_intelligent_router
                    intelligent_router = get_intelligent_router()
                    
                    for task in tasks:
                        # Оцениваем сложность задачи
                        prompt = f"{task.get('title', '')} {task.get('description', '')}"
                        task_complexity = intelligent_router.estimate_task_complexity(prompt, category=None)
                        
                        # Определяем оптимальный источник на основе сложности и типа задачи
                        # MLX лучше для сложных reasoning и coding задач
                        # Ollama лучше для быстрых и простых задач
                        if (task_complexity.complexity_score > 0.6 and 
                            (task_complexity.requires_reasoning or task_complexity.requires_coding)):
                            # Сложные reasoning/coding → MLX (мощные модели)
                            task['preferred_source'] = 'mlx'
                            mlx_tasks.append(task)
                        elif task_complexity.complexity_score < 0.4 or task_complexity.task_type == 'fast':
                            # Простые/быстрые → Ollama
                            task['preferred_source'] = 'ollama'
                            ollama_tasks.append(task)
                        else:
                            # Средние задачи - распределяем равномерно для балансировки
                            if len(mlx_tasks) <= len(ollama_tasks):
                                task['preferred_source'] = 'mlx'
                                mlx_tasks.append(task)
                            else:
                                task['preferred_source'] = 'ollama'
                                ollama_tasks.append(task)
                except Exception as e:
                    logger.debug(f"Intelligent routing failed: {e}, using simple distribution")
                    # Fallback на простое распределение
                    for task in tasks:
                        bug_prob = task.get('bug_probability', 0.0)
                        if bug_prob > 0.5:
                            task['preferred_source'] = 'mlx'
                            mlx_tasks.append(task)
                        else:
                            task['preferred_source'] = 'ollama'
                            ollama_tasks.append(task)
                
                print(f'[{datetime.now()}] 📊 Интеллектуальное распределение: MLX={len(mlx_tasks)}, Ollama={len(ollama_tasks)}')
                
                # Обрабатываем задачи параллельно через ОБА источника одновременно
                all_tasks_to_process = []
                
                # Создаем задачи с указанием предпочтительного источника
                for task in mlx_tasks:
                    all_tasks_to_process.append(task)
                
                for task in ollama_tasks:
                    all_tasks_to_process.append(task)
                
                # Обрабатываем все задачи параллельно батчами
                for i in range(0, len(all_tasks_to_process), MAX_CONCURRENT_TASKS):
                    batch = all_tasks_to_process[i:i + MAX_CONCURRENT_TASKS]
                    print(f'[{datetime.now()}] Processing batch {i//MAX_CONCURRENT_TASKS + 1}: {len(batch)} tasks (MLX и Ollama параллельно)')
                    
                    # Параллельная обработка батча - задачи будут обрабатываться через оба источника одновременно
                    await asyncio.gather(*[
                        process_task(pool, task) 
                        for task in batch
                    ], return_exceptions=True)
                    
                    # Небольшая задержка между батчами
                    if i + MAX_CONCURRENT_TASKS < len(all_tasks_to_process):
                        await asyncio.sleep(1)
                
                print(f'[{datetime.now()}] ✅ Batch completed: {len(tasks)} tasks processed')
            else:
                print(f'[{datetime.now()}] No pending tasks found. Waiting...')
            
            await asyncio.sleep(5)  # Уменьшили задержку, так как обрабатываем быстрее
        except Exception as e:
            print(f'[{datetime.now()}] Main loop error: {e}')
            import traceback
            traceback.print_exc()
            await asyncio.sleep(30)

if __name__ == '__main__':
    asyncio.run(main())

