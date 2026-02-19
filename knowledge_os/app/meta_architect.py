"""
[KNOWLEDGE OS] Meta-Architect Engine.
Autonomous Meta-Architect Agent (Singularity v3.0).
Responsible for self-authoring, patching, and code-level optimization across the workspace.
"""

import asyncio
import getpass
import json
import logging
import os
import subprocess
import time

# Third-party imports with fallback
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False

# Local project imports with fallback
try:
    from ai_core import run_smart_agent_async
except ImportError:
    async def run_smart_agent_async(prompt, **kwargs):  # pylint: disable=unused-argument
        """Fallback for run_smart_agent_async."""
        return None

try:
    from architecture_profiler import get_profiler
except ImportError:
    get_profiler = None

try:
    from graphrag.graphrag_service import get_graphrag_service
except ImportError:
    def get_graphrag_service():
        return None

try:
    from graphrag.code_analyzer import CodeAnalyzer
except ImportError:
    CodeAnalyzer = None

try:
    from sandbox_manager import get_sandbox_manager
except ImportError:
    get_sandbox_manager = None

try:
    from graph_optimizer import run_optimization_cycle
except ImportError:
    async def run_optimization_cycle():
        return None

logger = logging.getLogger(__name__)

USER_NAME = getpass.getuser()
# Priority: 1. env var, 2. local user (Mac), 3. fallback to admin (Server)
if USER_NAME == 'zhuchyok':
    DEFAULT_DB_URL = f'postgresql://{USER_NAME}@localhost:5432/knowledge_os'
else:
    DEFAULT_DB_URL = 'postgresql://admin:secret@localhost:5432/knowledge_os'

DB_URL = os.getenv('DATABASE_URL', DEFAULT_DB_URL)
# GLOBAL VISION: Meta-Architect now scans the entire workspace
base_dir_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WORKSPACE_ROOT = os.getenv('WORKSPACE_ROOT', base_dir_path)


class MetaArchitect:
    """
    Autonomous Meta-Architect Agent (Singularity v3.0).
    Responsible for self-authoring, patching, and code-level optimization across the workspace.
    """

    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url

    async def self_repair_cycle(self):
        """Analyze repair tasks and attempt to fix the code."""
        # ... existing code ...

    async def verify_mutation_safety(self, module_name: str, function_name: str, mutated_code: str) -> Dict[str, Any]:
        """
        [SINGULARITY 10.0+] Safety Verification via GraphRAG (Impact Analysis).
        Verifies if the mutation is safe to deploy in shadow mode.
        """
        logger.info(f"🛡️ [SAFETY] Verifying mutation safety for {module_name}.{function_name}...")
        
        # 1. Analyze mutated code for signature changes
        if not CodeAnalyzer:
            logger.error("CodeAnalyzer not available for safety verification.")
            return {"score": 0.5, "risks": ["CodeAnalyzer missing"]}

        try:
            # We need to find the function in the mutated code
            import ast
            tree = ast.parse(mutated_code)
            mutated_function = None
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Handle both top-level functions and methods (if function_name is Class.method)
                    current_name = node.name
                    # Simple check for now, could be improved to match full name
                    if current_name == function_name or ('.' in function_name and function_name.split('.')[-1] == current_name):
                        mutated_function = node
                        break
            
            if not mutated_function:
                return {"score": 0.0, "risks": [f"Function {function_name} not found in mutated code"]}

            # Check signature (arguments)
            # This is a simplified check. A robust one would compare arg names, defaults, etc.
            mutated_args = [arg.arg for arg in mutated_function.args.args]
            
            # 2. Use GraphRAG to find callers
            graphrag_service = get_graphrag_service()
            callers = []
            if graphrag_service:
                # Find nodes that call this function
                conn = await asyncpg.connect(self.db_url)
                # Find the node for this function
                func_node_id = await conn.fetchval("""
                    SELECT id FROM knowledge_nodes 
                    WHERE (metadata->>'file_path' LIKE $1 OR metadata->>'file_path' LIKE $2)
                    AND content LIKE $3
                    LIMIT 1
                """, f"%{module_name}.py", f"%{module_name}%", f"%def {function_name}%")
                
                if func_node_id:
                    caller_nodes = await conn.fetch("""
                        SELECT kn.content, kn.metadata->>'file_path' as file_path
                        FROM knowledge_links kl
                        JOIN knowledge_nodes kn ON kl.source_node_id = kn.id
                        WHERE kl.target_node_id = $1 AND kl.link_type = 'calls'
                    """, func_node_id)
                    callers = [dict(c) for c in caller_nodes]
                await conn.close()

            # 3. Safety Audit via Local Model
            audit_prompt = f"""
ВЫ - ЭКСПЕРТ ПО БЕЗОПАСНОСТИ И КАЧЕСТВУ КОДА (QA/SRE).
ЗАДАЧА: Провести аудит безопасности архитектурной мутации.

МОДУЛЬ: {module_name}
ФУНКЦИЯ: {function_name}
АРГУМЕНТЫ В МУТАЦИИ: {mutated_args}

СПИСОК ЗАВИСИМЫХ ВЫЗОВОВ (CALLERS) ИЗ GRAPHRAG:
{json.dumps(callers, indent=2) if callers else "No callers found in graph."}

КОД МУТАЦИИ:
```python
{mutated_code}
```

ПРАВИЛА АУДИТА:
1. Если сигнатура функции изменилась (новые обязательные аргументы, удаление аргументов), а вызывающие функции не обновлены - это КРИТИЧЕСКИЙ РИСК (Score < 0.3).
2. Если в коде есть потенциальные race conditions, утечки памяти или бесконечные циклы - это ВЫСОКИЙ РИСК (Score < 0.5).
3. Если мутация меняет логику возвращаемого значения так, что это сломает вызывающих - это СРЕДНИЙ РИСК (Score < 0.7).
4. Если мутация только оптимизирует производительность без изменения интерфейса - это БЕЗОПАСНО (Score > 0.8).

ВЕРНИТЕ ОТВЕТ В JSON:
{{
    "safety_score": 0.0 to 1.0,
    "risks": ["риск 1", "риск 2"],
    "recommendation": "abort" или "proceed"
}}
"""
            audit_json = await run_smart_agent_async(
                audit_prompt,
                expert_name="Виктория",
                category="safety_audit",
                model="qwen2.5-coder:32b"
            )

            try:
                if "```json" in audit_json:
                    audit_json = audit_json.split("```json")[1].split("```")[0].strip()
                audit_result = json.loads(audit_json)
                return {
                    "score": audit_result.get("safety_score", 0.0),
                    "risks": audit_result.get("risks", ["Unknown risk"]),
                    "recommendation": audit_result.get("recommendation", "abort")
                }
            except Exception as e:
                logger.error(f"Failed to parse safety audit JSON: {e}")
                return {"score": 0.0, "risks": [f"Audit parsing error: {e}"]}

        except Exception as e:
            logger.error(f"Safety verification failed: {e}")
            return {"score": 0.0, "risks": [str(e)]}

    async def self_evolution_cycle(self):
        """[SINGULARITY 10.0] Analyze performance hot spots and generate architectural mutations."""
        # Run graph optimization as part of evolution
        logger.info("🔧 [EVOLUTION] Starting Graph Optimization (Pruning & Caching)...")
        await run_optimization_cycle()

        if not get_profiler:
            logger.error("ArchitectureProfiler not available.")
            return

        profiler = get_profiler()
        hot_spots = await profiler.get_hot_spots(limit=3)
        
        if not hot_spots:
            logger.info("No architectural hot spots identified yet.")
            return

        for spot in hot_spots:
            logger.info(f"🚀 [EVOLUTION] Analyzing hot spot: {spot['module_name']}.{spot['function_name']} (Avg: {spot['avg_time']:.2f}ms)")
            
            # 0. Retrieve GraphRAG Context
            graph_context = ""
            graphrag_service = get_graphrag_service()
            if graphrag_service:
                query = f"module {spot['module_name']} function {spot['function_name']}"
                graph_context = await graphrag_service.retrieve_graph_context(query)
                if graph_context:
                    logger.info(f"🌐 [EVOLUTION] GraphRAG context retrieved for {spot['function_name']}")

            # 1. Generate Mutation Hypothesis
            hypothesis_prompt = f"""
ВЫ - ГЛАВНЫЙ АРХИТЕКТОР (CTO) SINGULARITY 10.0.
ЦЕЛЬ: Оптимизировать производительность ядра.

ГОРЯЧАЯ ТОЧКА: Модуль {spot['module_name']}, функция {spot['function_name']}
СРЕДНЕЕ ВРЕМЯ: {spot['avg_time']:.2f}ms
КОЛИЧЕСТВО ВЫЗОВОВ: {spot['call_count']}
ОШИБОК: {spot['failure_count']}

{graph_context}

ЗАДАЧА: 
1. Проанализируйте, почему эта функция может быть медленной.
2. Используя данные GraphRAG выше (если есть), оцените зависимости: какие другие функции вызывают эту? От чего зависит эта функция? Как изменение этой функции повлияет на логические связи в системе?
3. Предложите архитектурную мутацию (например, внедрение кэширования, асинхронности, изменение алгоритма или перенос логики).
4. Опишите ожидаемый результат.

ВЕРНИТЕ ОТВЕТ В JSON:
{{
    "analysis": "...",
    "mutation_hypothesis": "...",
    "expected_improvement_percent": 20,
    "dependency_impact": "..."
}}
"""
            hypothesis_json = await run_smart_agent_async(
                hypothesis_prompt,
                expert_name="Виктория",
                category="architectural_evolution"
            )
            
            try:
                # Clean JSON if needed
                if "```json" in hypothesis_json:
                    hypothesis_json = hypothesis_json.split("```json")[1].split("```")[0].strip()
                hypothesis = json.loads(hypothesis_json)
            except Exception as e:
                logger.error(f"Failed to parse hypothesis JSON: {e}")
                continue

            # 2. Generate Mutated Code
            # Find the file path for the module
            module_path = os.path.join(WORKSPACE_ROOT, "knowledge_os", "app", f"{spot['module_name']}.py")
            if not os.path.exists(module_path):
                continue

            with open(module_path, 'r', encoding='utf-8') as f:
                original_code = f.read()

            mutation_prompt = f"""
ВЫ - ГЛАВНЫЙ АРХИТЕКТОР (CTO) SINGULARITY 10.0.
ЗАДАЧА: Реализовать мутацию кода для оптимизации.

ФАЙЛ: {module_path}
ГИПОТЕЗА МУТАЦИИ: {hypothesis['mutation_hypothesis']}

{graph_context}

ТЕКУЩИЙ КОД:
```python
{original_code}
```

ВЕРНИТЕ ПОЛНЫЙ ИСПРАВЛЕННЫЙ КОД ФАЙЛА. 
Используйте только валидный Python. Не обрезайте код.
Учитывайте зависимости и логические связи, указанные в контексте GraphRAG (если есть).
"""
            mutated_code = await run_smart_agent_async(
                mutation_prompt,
                expert_name="Виктория",
                category="code_mutation"
            )

            if "```python" in mutated_code:
                mutated_code = mutated_code.split("```python")[1].split("```")[0].strip()
            
            # 2.5 Safety Verification via GraphRAG
            safety_report = await self.verify_mutation_safety(spot['module_name'], spot['function_name'], mutated_code)
            if safety_report['score'] < 0.7:
                logger.warning(f"🛑 [SAFETY VIOLATION] Mutation for {spot['function_name']} rejected. Score: {safety_report['score']}. Risks: {safety_report['risks']}")
                
                # Log Safety Violation to knowledge nodes
                conn = await asyncpg.connect(self.db_url)
                node_content = f"🛑 SAFETY VIOLATION: Mutation of {spot['module_name']}.{spot['function_name']} rejected."
                node_meta = json.dumps({
                    "type": "safety_violation",
                    "module": spot['module_name'],
                    "function": spot['function_name'],
                    "safety_report": safety_report,
                    "hypothesis": hypothesis
                })
                await conn.execute("""
                    INSERT INTO knowledge_nodes (domain_id, content, is_verified, confidence_score, metadata)
                    VALUES ((SELECT id FROM domains WHERE name = 'Architecture' LIMIT 1), $1, true, 1.0, $2)
                """, node_content, node_meta)
                await conn.close()
                continue

            # 3. Save as Mutation for Shadow Execution
            mutation_id = f"mut_{spot['module_name']}_{int(time.time())}"
            mutation_path = os.path.join(WORKSPACE_ROOT, "knowledge_os", "app", f"{spot['module_name']}_v2.py")
            
            with open(mutation_path, 'w', encoding='utf-8') as f:
                f.write(mutated_code)
            
            logger.info(f"🧬 [MUTATION] Created mutated version: {mutation_path}")
            
            # [SINGULARITY 10.0+] Автоматический деплой в Shadow для A/B тестирования
            try:
                from traffic_mirror import get_traffic_mirror
                tm = get_traffic_mirror()
                await tm.register_shadow(spot['module_name'], mutation_path)
                logger.info(f"🛡️ [SHADOW] Mutation {mutation_id} deployed for A/B testing.")
            except Exception as e:
                logger.error(f"Failed to deploy shadow mutation: {e}")

            # Log to knowledge nodes
            conn = await asyncpg.connect(self.db_url)
            node_content = f"🧬 ARCHITECTURAL MUTATION: {spot['module_name']}.{spot['function_name']} -> {hypothesis['mutation_hypothesis']}"
            node_meta = json.dumps({
                "type": "architecture_mutation",
                "module": spot['module_name'],
                "function": spot['function_name'],
                "hypothesis": hypothesis,
                "mutation_path": mutation_path
            })
            await conn.execute("""
                INSERT INTO knowledge_nodes (domain_id, content, is_verified, confidence_score, metadata)
                VALUES ((SELECT id FROM domains WHERE name = 'Architecture' LIMIT 1), $1, true, 0.8, $2)
            """, node_content, node_meta)
            await conn.close()
            logger.info(f"🧬 [MUTATION] Created mutated version: {mutation_path}")

    async def recursive_learning_loop(self):
        """[SINGULARITY 10.0] Compare shadow vs production metrics and promote winners."""
        if not get_profiler:
            return

        profiler = get_profiler()
        hot_spots = await profiler.get_hot_spots(limit=10)
        
        for spot in hot_spots:
            if not spot['module_name'].startswith("shadow-"):
                continue
            
            original_module = spot['module_name'].replace("shadow-", "")
            # Find production metrics for comparison
            prod_spot = next((s for s in hot_spots if s['module_name'] == original_module and s['function_name'] == spot['function_name']), None)
            
            if prod_spot:
                improvement = (prod_spot['avg_time'] - spot['avg_time']) / prod_spot['avg_time']
                logger.info(f"📊 [RECURSIVE LEARNING] {original_module}.{spot['function_name']}: Shadow is {improvement:.1%} faster than Production.")
                
                if improvement > 0.05 and spot['call_count'] > 50: # 5% threshold, 50 calls min
                    logger.info(f"🏆 [WINNER] Shadow version of {original_module} is a winner! Triggering Hot-Swap.")
                    
                    # Log lesson to knowledge nodes
                    conn = await asyncpg.connect(self.db_url)
                    node_content = f"🧠 ARCHITECTURAL LESSON: Mutation of {original_module}.{spot['function_name']} improved performance by {improvement:.1%}. Promoting to Production."
                    node_meta = json.dumps({
                        "type": "architectural_lesson",
                        "module": original_module,
                        "improvement": improvement,
                        "status": "promoted"
                    })
                    await conn.execute("""
                        INSERT INTO knowledge_nodes (domain_id, content, is_verified, confidence_score, metadata)
                        VALUES ((SELECT id FROM domains WHERE name = 'Architecture' LIMIT 1), $1, true, 1.0, $2)
                    """, node_content, node_meta)
                    await conn.close()
                    
                    # Trigger Hot-Swap (in a real system, we'd call ServiceMonitor)
                    try:
                        from service_monitor import promote_mutation
                        success = await promote_mutation(original_module, spot['function_name'])
                        if success:
                            logger.info(f"🔄 [HOT-SWAP] Successfully promoted mutation to {original_module}.py")
                        else:
                            logger.warning(f"⚠️ [HOT-SWAP] Promotion failed for {original_module}")
                    except Exception as e:
                        logger.error(f"Failed to trigger hot-swap: {e}")
                        logger.info(f"🔄 [HOT-SWAP] Promoting mutation to {original_module}.py")
        if not ASYNCPG_AVAILABLE:
            logger.error("❌ asyncpg is not installed. Repair cycle aborted.")
            return "Error: asyncpg missing"

        try:
            conn = await asyncpg.connect(self.db_url)
            # Find urgent repair tasks created by Phase 8
            tasks = await conn.fetch("""
                SELECT id, title, description, metadata
                FROM tasks
                WHERE status = 'pending' AND title LIKE '🚨 АВТО-РЕМОНТ%'
                ORDER BY created_at ASC
                LIMIT 1
            """)

            if not tasks:
                await conn.close()
                return "No repair tasks found."

            for task in tasks:
                logger.info("🏗️ Meta-Architect (Global) addressing task: %s", task['title'])

                # 1. Identify relevant files
                analysis_prompt = (
                    "ВЫ - ГЛОБАЛЬНЫЙ МЕТА-АРХИТЕКТОР. "
                    "ЗАДАЧА: Проанализируйте описание ошибки и определите ПОЛНЫЙ путь к файлу "
                    f"в директории {WORKSPACE_ROOT}.\n\n"
                    f"ОШИБКА: {task['description']}\n"
                    f"МЕТАДАННЫЕ: {task['metadata']}\n\n"
                    "ВЕРНИТЕ ТОЛЬКО АБСОЛЮТНЫЙ ПУТЬ К ФАЙЛУ."
                )
                file_path_rel = await run_smart_agent_async(
                    analysis_prompt,
                    expert_name="Виктория",
                    category="meta_architect_analysis"
                )
                full_path = file_path_rel.strip().strip('`').strip()

                if not os.path.exists(full_path):
                    logger.error("File not found: %s", full_path)
                    continue

                # 2. Read file content
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # 3. Generate patch
                patch_prompt = (
                    "ВЫ - ГЛОБАЛЬНЫЙ МЕТА-АРХИТЕКТОР. "
                    "ЦЕЛЬ: Исправьте ошибку в коде.\n\n"
                    f"ФАЙЛ: {full_path}\n"
                    "ТЕКУЩИЙ КОД:\n"
                    "```python\n"
                    f"{content}\n"
                    "```\n\n"
                    f"ОПИСАНИЕ ОШИБКИ: {task['description']}\n\n"
                    "ЗАДАЧА: Верните ПОЛНЫЙ исправленный код файла. "
                    "Не используйте комментарии '... more code ...'. Только валидный Python код."
                )
                new_code = await run_smart_agent_async(
                    patch_prompt,
                    expert_name="Виктория",
                    category="meta_architect_patching"
                )

                if "```python" in new_code:
                    new_code = new_code.split("```python")[1].split("```")[0].strip()
                elif "```" in new_code:
                    new_code = new_code.split("```")[1].split("```")[0].strip()

                if len(new_code) < 100:
                    logger.error("Generated code is too short, aborting.")
                    continue

                # 4. Verify (Simple syntax check)
                temp_file = full_path + ".tmp"
                with open(temp_file, 'w', encoding='utf-8') as f:
                    f.write(new_code)

                try:
                    subprocess.check_call(['python3', '-m', 'py_compile', temp_file])
                    # 5. Apply
                    os.replace(temp_file, full_path)
                    await conn.execute("""
                        UPDATE tasks SET status = 'completed', result = $2, updated_at = NOW()
                        WHERE id = $1
                    """, task['id'], f"Code patched in {full_path}")

                    # 6. Log knowledge
                    node_content = f"🔧 GLOBAL SELF-PATCH: Meta-Architect исправил баг в {full_path}"
                    node_meta = json.dumps({
                        "type": "self_patch",
                        "file": full_path,
                        "task_id": str(task['id'])
                    })
                    await conn.execute("""
                        INSERT INTO knowledge_nodes (domain_id, content, is_verified, confidence_score, metadata)
                        VALUES ((SELECT id FROM domains WHERE name = 'Strategy' LIMIT 1), $1, true, 1.0, $2)
                    """, node_content, node_meta)

                    logger.info("✅ Successfully patched %s", full_path)
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    logger.error("Syntax check failed for %s: %s", file_path_rel, exc)
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                    await conn.execute("""
                        UPDATE tasks SET status = 'failed', result = $2, updated_at = NOW()
                        WHERE id = $1
                    """, task['id'], f"Syntax error in generated patch: {exc}")

            await conn.close()
            return "Repair cycle finished."
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Meta-Architect error: %s", exc)
            return f"Error: {exc}"


if __name__ == "__main__":
    architect_instance = MetaArchitect()
    asyncio.run(architect_instance.self_repair_cycle())
