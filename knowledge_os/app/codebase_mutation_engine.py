import asyncio
import json
import logging
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CodebaseMutationEngine:
    """
    Codebase Mutation Engine - система самоэволюции кода.
    Ищет узкие места, анализирует логи ошибок и предлагает (или вносит) исправления.
    """

    def __init__(self, project_root: str = None):
        self.project_root = project_root or os.getcwd()
        self.mutation_history = []
        self._victoria_enhanced = None

    async def _get_victoria(self):
        if self._victoria_enhanced is None:
            try:
                from app.victoria_enhanced import VictoriaEnhanced

                self._victoria_enhanced = VictoriaEnhanced()
            except ImportError:
                logger.error("❌ [MUTATION] VictoriaEnhanced not found")
        return self._victoria_enhanced

    async def analyze_and_mutate(
        self, error_event: Dict[str, Any], propose_only: bool = False
    ) -> Dict[str, Any]:
        """
        Анализирует событие ошибки и пытается найти мутацию (исправление).
        [SINGULARITY 21.19] Now updates expert DNA on repeated errors.
        """
        error_info = error_event.get("error_info", {})
        error_type = error_info.get("type", "UnknownError")
        error_msg = error_info.get("message", "")
        file_path = error_info.get("file")
        line_number = error_info.get("line")

        if not file_path or not os.path.exists(file_path):
            logger.warning(f"🧬 [MUTATION] Файл не найден: {file_path}")
            return {"success": False, "reason": "file_not_found"}

        logger.info(
            f"🧬 [MUTATION] Попытка анализа {error_type} в {file_path}:{line_number} (propose_only={propose_only})"
        )

        # 1. Читаем контекст ошибки
        try:
            with open(file_path, encoding="utf-8") as f:
                lines = f.readlines()

            start = max(0, (line_number or 0) - 10)
            end = min(len(lines), (line_number or 0) + 10)
            code_context = "".join(lines[start:end])
        except Exception as e:
            return {"success": False, "reason": f"read_error: {e}"}

        # 2. Запрашиваем решение у Victoria
        victoria = await self._get_victoria()
        if not victoria:
            return {"success": False, "reason": "victoria_unavailable"}

        prompt = f"""Ты — Интеллект Сингулярности (Victoria). Тебе нужно решить, как исправить ошибку в системе.
Файл: {file_path}
Ошибка: {error_type}: {error_msg}
Строка: {line_number}

Контекст кода:
```python
{code_context}
```

Твои варианты действий:
1. "apply" - Исправить код (только если ты уверена на 100% и это критическая ошибка).
2. "propose" - Предложить исправление (если есть сомнения или риск задеть другую логику).
3. "ignore" - Проигнорировать (если это ложное срабатывание или штатное поведение).

Верни ТОЛЬКО JSON:
{{
    "decision": "apply" | "propose" | "ignore",
    "confidence": 0.0-1.0,
    "explanation": "Почему выбрано это действие",
    "fix_description": "Что исправлено",
    "old_code": "точный кусок старого кода для замены",
    "new_code": "новый кусок кода"
}}"""

        try:
            res = await victoria.solve(prompt, method="extended_thinking")
            patch_data = self._parse_json(res.get("result", ""))

            if not patch_data or "decision" not in patch_data:
                return {"success": False, "reason": "invalid_victoria_response"}

            decision = patch_data.get("decision", "propose")
            confidence = patch_data.get("confidence", 0.0)

            if decision == "ignore":
                logger.info(f"🧬 [MUTATION] Victoria решила игнорировать ошибку в {file_path}")
                return {
                    "success": True,
                    "decision": "ignored",
                    "explanation": patch_data.get("explanation"),
                }

            # Если принудительно просили только предложить, или Виктория сама так решила
            should_propose = propose_only or decision == "propose" or confidence < 0.9

            if should_propose:
                logger.info(
                    f"🧬 [MUTATION] Создано предложение для {file_path} (confidence: {confidence})"
                )
                return {
                    "success": True,
                    "propose_only": True,
                    "patch_data": patch_data,
                    "file": file_path,
                    "explanation": patch_data.get("explanation"),
                }

            # 3. Автономное применение (decision == 'apply' и высокая уверенность)
            logger.info(
                f"🚀 [MUTATION] Victoria решила АВТОНОМНО исправить {file_path} (confidence: {confidence})"
            )

            # Проверка безопасности (Patch Safety Guard) + Тесты
            is_safe = await self._verify_patch_safety(file_path, patch_data)
            if is_safe:
                # Проверяем, не применен ли уже патч (мог быть применен внутри _verify_patch_safety)
                with open(file_path, encoding="utf-8") as f:
                    current_content = f.read()

                success = True
                if patch_data.get("new_code") not in current_content:
                    success = await self._apply_patch(file_path, patch_data)

                if success:
                    mutation_id = str(uuid.uuid4())[:8]
                    result = {
                        "success": True,
                        "mutation_id": mutation_id,
                        "decision": "applied",
                        "explanation": patch_data.get("explanation"),
                        "file": file_path,
                        "verified_by_tests": self._find_related_test(file_path) is not None,
                    }
                    self.mutation_history.append(result)
                    return result
            else:
                logger.warning(
                    "⚠️ [MUTATION] Автономное исправление отклонено Safety Guard. Переход к предложению."
                )
                return {
                    "success": True,
                    "propose_only": True,
                    "patch_data": patch_data,
                    "file": file_path,
                    "explanation": f"Авто-исправление не прошло тесты. Ошибка: {patch_data.get('explanation')}",
                }

        except Exception as e:
            logger.error(f"❌ [MUTATION] Ошибка генерации мутации: {e}")

        return {"success": False, "status": "failed_to_mutate"}

    async def _update_expert_dna_on_failure(self, expert_name: str, error_msg: str):
        """[SINGULARITY 21.19] Self-Learning DNA: Inject 'antibody' into expert DNA."""
        try:
            import asyncpg

            db_url = os.getenv(
                "DATABASE_URL", "postgresql://admin:secret@knowledge_pgbouncer:6432/knowledge_os"
            )
            conn = await asyncpg.connect(db_url)
            try:
                expert_id = await conn.fetchval(
                    "SELECT id FROM experts WHERE name = $1", expert_name
                )
                department = await conn.fetchval(
                    "SELECT department FROM experts WHERE name = $1", expert_name
                )

                if expert_id:
                    # [SINGULARITY 28.0] Constitutional Guard for Antibody Injection
                    try:
                        from constitutional_court import get_constitutional_court
                        court = get_constitutional_court()
                        is_constitutional = await court.verify_decision(
                            decision_description=f"Inject antibody into {expert_name} DNA due to failure: {error_msg[:100]}",
                            context={"expert": expert_name, "error": error_msg}
                        )
                        if not is_constitutional:
                            logger.warning(f"⚖️ [CONSTITUTIONAL GUARD] Antibody injection for {expert_name} rejected.")
                            return
                    except Exception as court_err:
                        logger.debug(f"Constitutional Antibody verification skipped: {court_err}")

                    antibody = f"\n### 🛡️ ANTI-ERROR RULE (Auto-Learned):\nAvoid this pattern which caused error: {error_msg[:100]}. Ensure proper validation/imports."

                    # [SINGULARITY 21.21] Antifragile Feedback Loop: Update whole department
                    if department:
                        logger.info(
                            f"📈 [ANTIFRAGILE] Scaling antibody to department: {department}"
                        )
                        await conn.execute(
                            """
                            INSERT INTO knowledge_nodes (content, metadata)
                            VALUES ($1, $2)
                        """,
                            f"Antifragile Note: {error_msg[:100]}",
                            {
                                "type": "antifragile_note",
                                "department": department,
                                "original_expert": expert_name,
                                "antibody": antibody,
                            },
                        )

                    # Get current override
                    current = await conn.fetchval(
                        "SELECT custom_instructions FROM expert_dna_overrides WHERE expert_id = $1 AND is_active = TRUE",
                        expert_id,
                    )
                    new_dna = (current or "") + antibody

                    await conn.execute(
                        "UPDATE expert_dna_overrides SET is_active = FALSE WHERE expert_id = $1",
                        expert_id,
                    )
                    await conn.execute(
                        """
                        INSERT INTO expert_dna_overrides (expert_id, custom_instructions, updated_by)
                        VALUES ($1, $2, $3)
                    """,
                        expert_id,
                        new_dna,
                        "Antifragile_Feedback_Loop",
                    )
                    logger.info(f"🧬 [DNA] Injected antibody for {expert_name} after error.")
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Failed to update DNA on failure: {e}")

    async def _reinforce_expert_dna_on_success(self, expert_name: str, query: str, response: str):
        """[SINGULARITY 27.2] Success Reinforcement: Extract 'wisdom' from successful interaction."""
        try:
            import asyncpg

            db_url = os.getenv(
                "DATABASE_URL", "postgresql://admin:secret@knowledge_pgbouncer:6432/knowledge_os"
            )
            conn = await asyncpg.connect(db_url)
            try:
                expert_id = await conn.fetchval(
                    "SELECT id FROM experts WHERE name = $1", expert_name
                )
                if not expert_id:
                    return

                # 1. Extract wisdom using Victoria
                victoria = await self._get_victoria()
                if not victoria:
                    return

                prompt = f"""Ты — Интеллект Сингулярности. Эксперт {expert_name} получил ПОЛОЖИТЕЛЬНЫЙ отзыв за этот ответ.
Запрос: {query[:500]}
Ответ: {response[:1000]}

Выдели ОДНО ключевое правило или принцип, который сделал этот ответ успешным.
Верни только текст правила (1 предложение), которое нужно добавить в DNA эксперта как 'SUCCESS RULE'."""

                wisdom_res = await victoria.solve(prompt, method="quick_answer")
                wisdom_rule = wisdom_res.get("result", "").strip()

                if wisdom_rule and len(wisdom_rule) > 10:
                    # [SINGULARITY 28.0] Constitutional Guard for DNA Mutation
                    try:
                        from constitutional_court import get_constitutional_court
                        court = get_constitutional_court()
                        is_constitutional = await court.verify_decision(
                            decision_description=f"Reinforce DNA for {expert_name} with success rule: {wisdom_rule}",
                            context={"expert": expert_name, "wisdom_rule": wisdom_rule}
                        )
                        if not is_constitutional:
                            logger.warning(f"⚖️ [CONSTITUTIONAL GUARD] DNA reinforcement for {expert_name} rejected.")
                            return
                    except Exception as court_err:
                        logger.debug(f"Constitutional DNA verification skipped: {court_err}")

                    success_rule = f"\n### 🏆 SUCCESS RULE (Auto-Learned):\n{wisdom_rule}"

                    # 2. Update DNA
                    current = await conn.fetchval(
                        "SELECT custom_instructions FROM expert_dna_overrides WHERE expert_id = $1 AND is_active = TRUE",
                        expert_id,
                    )
                    new_dna = (current or "") + success_rule

                    await conn.execute(
                        "UPDATE expert_dna_overrides SET is_active = FALSE WHERE expert_id = $1",
                        expert_id,
                    )
                    await conn.execute(
                        """
                        INSERT INTO expert_dna_overrides (expert_id, custom_instructions, updated_by)
                        VALUES ($1, $2, $3)
                    """,
                        expert_id,
                        new_dna,
                        "Success_Reinforcement_Loop",
                    )
                    logger.info(f"🧬 [DNA] Reinforced success for {expert_name}.")
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Failed to reinforce DNA on success: {e}")

    async def _verify_patch_safety(self, file_path: str, patch_data: Dict) -> bool:
        """
        [SINGULARITY 23.1] Real Docker Sandbox Patch Verification:
        Проверка безопасности патча в изолированном контейнере.
        """
        import os
        import sys
        import uuid
        from sandbox_manager import get_sandbox_manager

        temp_file = f"{file_path}.tmp"
        backup_file = f"{file_path}.bak"
        
        try:
            # 1. Читаем текущий контент
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            old_code = patch_data.get("old_code")
            new_code = patch_data.get("new_code")

            if old_code not in content:
                logger.warning(f"🧬 [MUTATION] Старый код не найден в {file_path}")
                return False

            new_content = content.replace(old_code, new_code)

            # [SINGULARITY 21.20] ArchitecturalGuard: Проверка на SOLID/KISS перед записью
            if not await self._architectural_guard(new_content, file_path):
                logger.warning("🛡️ [ARCH GUARD] Патч отклонен: нарушение архитектурных стандартов.")
                return False

            # [SINGULARITY 28.0] Constitutional Guard: Final verification against COGNITIVE_CODE.md
            try:
                from constitutional_court import get_constitutional_court
                court = get_constitutional_court()
                is_constitutional = await court.verify_decision(
                    decision_description=f"Mutation of {file_path}: {patch_data.get('fix_description')}",
                    context={"file": file_path, "patch": patch_data, "new_content_preview": new_content[:2000]}
                )
                if not is_constitutional:
                    logger.warning(f"⚖️ [CONSTITUTIONAL GUARD] Mutation of {file_path} rejected by Constitutional Court.")
                    return False
            except Exception as court_err:
                logger.debug(f"Constitutional Court verification skipped: {court_err}")

            sandbox = get_sandbox_manager()
            if not sandbox or not sandbox.client:
                logger.warning("⚠️ SandboxManager not available, falling back to local verification")
                return await self._verify_patch_safety_fallback(file_path, new_content)

            # 2. Подготовка песочницы
            sandbox_id = f"mutation_{uuid.uuid4().hex[:8]}"
            shared_dir = "./knowledge_os/sandbox_shared"
            os.makedirs(shared_dir, exist_ok=True)
            
            # Копируем файл в песочницу
            rel_path = os.path.relpath(file_path, os.getcwd())
            sandbox_file_path = os.path.join(shared_dir, f"{sandbox_id}_{os.path.basename(file_path)}")
            
            with open(sandbox_file_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            sandbox_filename = os.path.basename(sandbox_file_path)

            # 3. Проверка синтаксиса в Docker
            if file_path.endswith(".py"):
                compile_res = await sandbox.run_in_sandbox("Mutation", f"python3 -m py_compile {sandbox_filename}")
                if compile_res.get("exit_code", 1) != 0:
                    logger.warning(f"⚠️ [MUTATION] Патч нарушает синтаксис: {compile_res.get('output')}")
                    return False

            # 4. Запуск тестов в Docker (если есть)
            test_file = self._find_related_test(file_path)
            
            # [SINGULARITY 24.0] Dependency-Aware Regression Guard
            from dependency_mapper import get_dependency_mapper
            mapper = get_dependency_mapper()
            affected_files = mapper.get_affected_files(file_path)
            
            related_tests = [test_file] if test_file else []
            for aff_file in affected_files:
                aff_test = self._find_related_test(os.path.join(self.project_root, aff_file))
                if aff_test and aff_test not in related_tests:
                    related_tests.append(aff_test)
                    logger.info(f"🧪 [DEPENDENCY GUARD] Added test for affected file: {aff_file}")
            
            for t_file in related_tests:
                logger.info(f"🧪 [MUTATION] Запуск теста {t_file} в песочнице...")
                # Копируем тест в песочницу
                sandbox_test_path = os.path.join(shared_dir, f"{sandbox_id}_{os.path.basename(t_file)}")
                with open(t_file, "r", encoding="utf-8") as f:
                    test_content = f.read()
                
                # В тесте нужно подменить импорт тестируемого файла на временный sandbox_filename (без .py)
                module_name = os.path.basename(file_path).replace(".py", "")
                sandbox_module_name = sandbox_filename.replace(".py", "")
                test_content = test_content.replace(f"from {module_name}", f"import {sandbox_module_name} as {module_name} # patched\n# from {module_name}")
                test_content = test_content.replace(f"import {module_name}", f"import {sandbox_module_name} as {module_name}")
                
                with open(sandbox_test_path, "w", encoding="utf-8") as f:
                    f.write(test_content)

                test_res = await sandbox.run_in_sandbox("Mutation", f"pytest {os.path.basename(sandbox_test_path)}")
                
                # Чистим тесты из песочницы
                if os.path.exists(sandbox_test_path): os.remove(sandbox_test_path)

                if test_res.get("exit_code", 1) != 0:
                    logger.warning(f"❌ [MUTATION] Тест {t_file} провален в песочнице! {test_res.get('output')}")
                    return False

            if related_tests:
                logger.info(f"✅ [MUTATION] Все тесты ({len(related_tests)}) пройдены в песочнице успешно!")

            # Чистим файл из песочницы
            if os.path.exists(sandbox_file_path): os.remove(sandbox_file_path)
            
            return True

        except Exception as e:
            logger.error(f"❌ [MUTATION] Ошибка проверки в песочнице: {e}")
            return False

    async def _verify_patch_safety_fallback(self, file_path: str, new_content: str) -> bool:
        """Fallback to local verification if Docker is not available."""
        temp_file = f"{file_path}.tmp"
        backup_file = f"{file_path}.bak"
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(new_content)

            if file_path.endswith(".py"):
                process = subprocess.run([sys.executable, "-m", "py_compile", temp_file], capture_output=True)
                if process.returncode != 0: return False

            test_file = self._find_related_test(file_path)
            if test_file:
                os.rename(file_path, backup_file)
                os.rename(temp_file, file_path)
                try:
                    test_process = subprocess.run([sys.executable, "-m", "pytest", test_file], capture_output=True, timeout=30)
                    if test_process.returncode != 0:
                        os.rename(file_path, temp_file)
                        os.rename(backup_file, file_path)
                        return False
                    if os.path.exists(backup_file): os.remove(backup_file)
                    return True
                except Exception:
                    if os.path.exists(backup_file):
                        if os.path.exists(file_path): os.remove(file_path)
                        os.rename(backup_file, file_path)
                    return False
            return True
        finally:
            if os.path.exists(temp_file): os.remove(temp_file)

    async def _architectural_guard(self, code: str, file_path: str) -> bool:
        """[SINGULARITY 21.20] Harness: Проверка кода на соответствие стандартам гигантов."""
        # [SINGULARITY 21.21] Recursive Testing: Require self-testing for new logic
        if "def " in code and not file_path.startswith("tests/"):
            has_test_in_code = "test_" in code or "pytest" in code or "unittest" in code
            related_test = self._find_related_test(file_path)

            if not related_test and not has_test_in_code:
                logger.warning(
                    f"🛡️ [RECURSIVE TEST] Rejected: No test found or proposed for new logic in {file_path}"
                )
                return False

            if has_test_in_code:
                logger.info("🧪 [RECURSIVE TEST] Agent proposed tests within the code block.")

        if len(code.split("\n")) > 1000:
            return False

        if "async def" in code and "try:" not in code and "except" not in code:
            return False

        return True

    def _find_related_test(self, file_path: str) -> Optional[str]:
        """Поиск связанного файла теста."""
        base_name = os.path.basename(file_path)
        dir_name = os.path.dirname(file_path)

        candidates = [
            os.path.join(dir_name, f"test_{base_name}"),
            os.path.join(dir_name, "tests", f"test_{base_name}"),
            os.path.join(os.path.dirname(dir_name), "tests", f"test_{base_name}"),
        ]

        for c in candidates:
            if os.path.exists(c):
                return c
        return None

    async def _apply_patch(self, file_path: str, patch_data: Dict) -> bool:
        """Применить патч к файлу и зафиксировать в Git."""
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            old_code = patch_data.get("old_code")
            new_code = patch_data.get("new_code")

            if old_code in content:
                new_content = content.replace(old_code, new_code)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                
                logger.info(f"✅ [MUTATION] Патч применен к {file_path}")
                
                # [SINGULARITY 28.9] Autonomous Git Cycle
                try:
                    fix_desc = patch_data.get("fix_description", "Autonomous self-repair")
                    subprocess.run(["git", "add", file_path], cwd=self.project_root, check=True)
                    subprocess.run(["git", "commit", "-m", f"🧬 [EVOLUTION] {fix_desc}"], cwd=self.project_root, check=True)
                    logger.info(f"📦 [GIT] Mutation committed: {fix_desc}")
                except Exception as git_err:
                    logger.warning(f"⚠️ [GIT] Failed to commit mutation: {git_err}")
                
                return True
            else:
                logger.warning(f"⚠️ [MUTATION] Старый код не найден в {file_path} для замены")
                return False
        except Exception as e:
            logger.error(f"❌ [MUTATION] Ошибка применения патча: {e}")
            return False

    def _parse_json(self, text: str) -> Optional[Dict]:
        try:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                return json.loads(match.group())
        except:
            pass
        return None

    async def run_nightly_optimization(self):
        """Фоновая оптимизация кодовой базы (запускается по расписанию)."""
        logger.info("🌙 [MUTATION] Запуск ночной оптимизации...")
        try:
            from expert_researcher import get_expert_researcher
            researcher = get_expert_researcher()
            await researcher.run_nightly_inventory()
        except Exception as e:
            logger.error(f"❌ [MUTATION] Nightly R&D failed: {e}")


_mutation_engine = None


def get_mutation_engine() -> CodebaseMutationEngine:
    global _mutation_engine
    if _mutation_engine is None:
        _mutation_engine = CodebaseMutationEngine()
    return _mutation_engine
