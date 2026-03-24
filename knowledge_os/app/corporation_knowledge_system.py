"""
Система автоматического обновления знаний корпорации
Все агенты и корпорация знают ВСЁ: модели, скрипты, внедрения, изменения
Singularity 10.0: prompt_change_log для версионирования и отката
"""

import asyncio
import hashlib
import json
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# Database connection
try:
    import asyncpg

    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False


class CorporationKnowledgeSystem:
    """
    Система автоматического обновления знаний корпорации.
    Отслеживает и обновляет информацию о:
    - Доступных моделях (MLX и Ollama)
    - Всех скриптах
    - Внедрениях и изменениях
    - Конфигурации системы
    """

    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or os.getenv(
            "DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os"
        )
        self.project_root = Path(__file__).parent.parent.parent
        self.scripts_dir = self.project_root / "scripts"
        self.knowledge_os_dir = self.project_root / "knowledge_os"

        # URLs для проверки моделей
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.mlx_url = os.getenv("MLX_API_URL", "http://localhost:11435")

    async def discover_ollama_models(self) -> List[Dict[str, Any]]:
        """Обнаружить все модели Ollama"""
        models = []

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.ollama_url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    for model in data.get("models", []):
                        models.append(
                            {
                                "name": model.get("name", ""),
                                "size": model.get("size", 0),
                                "modified": model.get("modified_at", ""),
                                "source": "ollama",
                            }
                        )
        except Exception as e:
            logger.error(f"Ошибка обнаружения моделей Ollama: {e}")

        return models

    async def discover_mlx_models(self) -> List[Dict[str, Any]]:
        """Обнаружить все модели MLX"""
        models = []

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.mlx_url}/v1/models")
                if response.status_code == 404:
                    response = await client.get(f"{self.mlx_url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    for model in data.get("data", data.get("models", [])):
                        models.append(
                            {"name": model.get("id", model.get("name", "")), "source": "mlx"}
                        )
        except Exception as e:
            logger.debug(f"MLX API недоступен: {e}")

        # Также проверяем локальные директории
        mlx_dirs = [
            Path.home() / "mlx-models",
            Path.home() / ".mlx_models",
            Path.home() / ".cache" / "huggingface" / "hub",
        ]

        for mlx_dir in mlx_dirs:
            if mlx_dir.exists():
                for model_dir in mlx_dir.iterdir():
                    if model_dir.is_dir():
                        # Проверяем наличие файлов модели
                        if any(model_dir.glob("*.safetensors")) or any(model_dir.glob("*.bin")):
                            models.append(
                                {
                                    "name": model_dir.name,
                                    "path": str(model_dir),
                                    "source": "mlx_local",
                                }
                            )

        return models

    def discover_scripts(self) -> List[Dict[str, Any]]:
        """Обнаружить все скрипты в проекте"""
        scripts = []

        # Ищем все .sh и .py файлы в scripts/
        if self.scripts_dir.exists():
            # [SINGULARITY 21.9] Оптимизация памяти: не грузим тысячи файлов в список,
            # если их слишком много. Ограничиваемся основными.
            count = 0
            for script_file in self.scripts_dir.rglob("*.sh"):
                if count > 50:
                    break
                scripts.append(
                    {
                        "name": script_file.name,
                        "path": str(script_file.relative_to(self.project_root)),
                        "type": "shell",
                        "size": script_file.stat().st_size,
                        "modified": datetime.fromtimestamp(script_file.stat().st_mtime).isoformat(),
                    }
                )
                count += 1

            count = 0
            for script_file in self.scripts_dir.rglob("*.py"):
                if count > 50:
                    break
                scripts.append(
                    {
                        "name": script_file.name,
                        "path": str(script_file.relative_to(self.project_root)),
                        "type": "python",
                        "size": script_file.stat().st_size,
                        "modified": datetime.fromtimestamp(script_file.stat().st_mtime).isoformat(),
                    }
                )
                count += 1

        return scripts

    def discover_images(self) -> List[Dict[str, Any]]:
        """[OMNI-RAG] Обнаружить все изображения в проекте"""
        images = []
        image_extensions = ["*.png", "*.jpg", "*.jpeg", "*.svg", "*.gif"]

        # Директории для поиска (адаптировано под структуру контейнера)
        search_dirs = [
            self.project_root / "docs",
            self.project_root / "knowledge_os" / "docs",
            self.project_root / "knowledge_os" / "knowledge_base",
            self.project_root / "knowledge_os" / "ai_insights",
            self.project_root / "ai_insights",
        ]

        for sdir in search_dirs:
            if not sdir.exists():
                continue

            for ext in image_extensions:
                for img_file in sdir.rglob(ext):
                    # Пропускаем node_modules, виртуальные окружения и скрытые папки
                    path_str = str(img_file)
                    if "node_modules" in path_str or ".venv" in path_str or "/." in path_str:
                        continue

                    images.append(
                        {
                            "name": img_file.name,
                            "path": str(img_file.relative_to(self.project_root)),
                            "abs_path": str(img_file),
                            "size": img_file.stat().st_size,
                            "modified": datetime.fromtimestamp(
                                img_file.stat().st_mtime
                            ).isoformat(),
                        }
                    )

        return images

    async def discover_recent_changes(self) -> List[Dict[str, Any]]:
        """Обнаружить недавние изменения в проекте"""
        changes = []

        try:
            # Используем git для обнаружения изменений
            result = subprocess.run(
                [
                    "git",
                    "log",
                    "--since",
                    "7 days ago",
                    "--pretty=format:%H|%an|%ae|%ad|%s",
                    "--date=iso",
                ],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line:
                        parts = line.split("|", 4)
                        if len(parts) == 5:
                            changes.append(
                                {
                                    "commit": parts[0],
                                    "author": parts[1],
                                    "email": parts[2],
                                    "date": parts[3],
                                    "message": parts[4],
                                }
                            )
        except Exception as e:
            logger.debug(f"Git недоступен: {e}")

        return changes

    async def update_corporation_knowledge(self, pool: Optional[Any] = None) -> Dict[str, Any]:
        """Обновить все знания корпорации. Если передан pool (asyncpg), используем его вместо нового соединения."""
        logger.info("🔄 Обновление знаний корпорации...")

        # Обнаруживаем все
        ollama_models = await self.discover_ollama_models()
        mlx_models = await self.discover_mlx_models()
        scripts = self.discover_scripts()
        images = self.discover_images()
        recent_changes = await self.discover_recent_changes()

        knowledge = {
            "timestamp": datetime.now().isoformat(),
            "ollama_models": ollama_models,
            "mlx_models": mlx_models,
            "scripts": scripts,
            "images": images,
            "recent_changes": recent_changes,
            "total_ollama_models": len(ollama_models),
            "total_mlx_models": len(mlx_models),
            "total_scripts": len(scripts),
            "total_images": len(images),
        }

        # Сохраняем в БД с эмбеддингами для поиска
        if ASYNCPG_AVAILABLE:
            try:
                # Импортируем get_embedding: сначала semantic_cache (лёгкий, Ollama), чтобы не тянуть app.main (MCP, redis, pool) — меньше памяти в оркестраторе
                get_embedding = None
                try:
                    from semantic_cache import get_embedding as _get_embedding

                    get_embedding = _get_embedding
                except ImportError:
                    try:
                        from app.main import get_embedding
                    except ImportError:
                        try:
                            from app.enhanced_search import get_embedding
                        except ImportError:
                            logger.warning("⚠️ get_embedding недоступен, сохраняем без эмбеддингов")

                # Используем переданный пул или одно соединение (меньше слотов к БД в nightly)
                if pool is not None:
                    async with pool.acquire() as conn:
                        await self._save_corporation_knowledge_to_db(conn, knowledge, get_embedding)
                else:
                    conn = await asyncpg.connect(self.db_url, command_timeout=30)
                    try:
                        await self._save_corporation_knowledge_to_db(conn, knowledge, get_embedding)
                    finally:
                        await conn.close()
            except Exception as e:
                logger.error(f"Ошибка сохранения знаний в БД: {e}", exc_info=True)

        return knowledge

    async def _save_corporation_knowledge_to_db(
        self, conn, knowledge: Dict[str, Any], get_embedding=None
    ) -> None:
        """Сохранить knowledge в БД (используется с conn из пула или одиночного connect)."""
        ollama_models = knowledge.get("ollama_models", [])
        mlx_models = knowledge.get("mlx_models", [])
        scripts = knowledge.get("scripts", [])
        images = knowledge.get("images", [])
        recent_changes = knowledge.get("recent_changes", [])
        # Получаем или создаем домен System
        domain_id = await conn.fetchval("""
            SELECT id FROM domains WHERE name = 'System' LIMIT 1
        """)
        if not domain_id:
            domain_id = await conn.fetchval("""
                INSERT INTO domains (name) VALUES ('System') RETURNING id
            """)

        # Удаляем старые знания корпорации
        await conn.execute("""
            DELETE FROM knowledge_nodes
            WHERE metadata->>'source' = 'corporation_knowledge_system'
        """)

        saved_count = 0
        # Сохраняем каждую модель Ollama отдельно с эмбеддингом
        for model in ollama_models:
            content = f"Модель Ollama: {model['name']}. Размер: {model.get('size', 0) / 1024 / 1024 / 1024:.2f} GB. Доступна для использования в корпорации."
            embedding = None
            if get_embedding:
                try:
                    embedding = await get_embedding(content)
                except Exception as e:
                    logger.debug(f"Ошибка создания эмбеддинга для модели {model['name']}: {e}")

            await conn.execute(
                """
                INSERT INTO knowledge_nodes (domain_id, content, embedding, confidence_score, metadata, is_verified)
                VALUES ($1, $2, $3, 1.0, $4, true)
            """,
                domain_id,
                content,
                str(embedding) if embedding else None,
                json.dumps(
                    {
                        "source": "corporation_knowledge_system",
                        "type": "ollama_model",
                        "model_name": model["name"],
                        "size": model.get("size", 0),
                        "timestamp": knowledge["timestamp"],
                    }
                ),
            )
            saved_count += 1
        # [SINGULARITY 21.9] Сброс памяти
        import gc

        if saved_count % 3 == 0:
            gc.collect()
            await asyncio.sleep(1)
        print(f"DEBUG: Saved model {model['name']}", flush=True)

        # Сохраняем каждую модель MLX отдельно с эмбеддингом
        for model in mlx_models:
            content = f"Модель MLX: {model['name']}. Путь: {model.get('path', 'N/A')}. Доступна для использования в корпорации."
            embedding = None
            if get_embedding:
                try:
                    embedding = await get_embedding(content)
                except Exception as e:
                    logger.debug(f"Ошибка создания эмбеддинга для MLX модели {model['name']}: {e}")

            await conn.execute(
                """
                INSERT INTO knowledge_nodes (domain_id, content, embedding, confidence_score, metadata, is_verified)
                VALUES ($1, $2, $3, 1.0, $4, true)
            """,
                domain_id,
                content,
                str(embedding) if embedding else None,
                json.dumps(
                    {
                        "source": "corporation_knowledge_system",
                        "type": "mlx_model",
                        "model_name": model["name"],
                        "path": model.get("path"),
                        "timestamp": knowledge["timestamp"],
                    }
                ),
            )
            saved_count += 1
            if saved_count % 3 == 0:
                gc.collect()
                await asyncio.sleep(1)

        # Сохраняем скрипты группами по типам с эмбеддингами
        scripts_by_type = {}
        for script in scripts:
            script_type = script["type"]
            if script_type not in scripts_by_type:
                scripts_by_type[script_type] = []
            scripts_by_type[script_type].append(script)

        for script_type, type_scripts in scripts_by_type.items():
            scripts_list = "\n".join([f"- {s['path']}" for s in type_scripts[:20]])
            content = (
                f"Доступные {script_type} скрипты корпорации ({len(type_scripts)}):\n{scripts_list}"
            )
            embedding = None
            if get_embedding:
                try:
                    embedding = await get_embedding(content)
                except Exception as e:
                    logger.debug(f"Ошибка создания эмбеддинга для скриптов {script_type}: {e}")

            await conn.execute(
                """
                INSERT INTO knowledge_nodes (domain_id, content, embedding, confidence_score, metadata, is_verified)
                VALUES ($1, $2, $3, 1.0, $4, true)
            """,
                domain_id,
                content,
                str(embedding) if embedding else None,
                json.dumps(
                    {
                        "source": "corporation_knowledge_system",
                        "type": f"scripts_{script_type}",
                        "count": len(type_scripts),
                        "timestamp": knowledge["timestamp"],
                    }
                ),
            )
            saved_count += 1
            gc.collect()
            await asyncio.sleep(0.5)

        # [OMNI-RAG] Сохраняем описания изображений
        if images:
            try:
                # [FIX] Исправлен импорт для работы внутри контейнера
                try:
                    from app.vision_processor import get_vision_processor
                except ImportError:
                    from vision_processor import get_vision_processor

                vision = get_vision_processor()

                for img in images:
                    # Пропускаем слишком большие файлы для экономии времени в этом цикле
                    if img["size"] > 5 * 1024 * 1024:
                        continue

                    # [SINGULARITY 21.10] Ограничиваем индексацию только важными исследованиями,
                    # если проектных изображений нет.
                    if "ai_research" in img["path"]:
                        # Индексируем DeepSeek и AutoGen как ключевые технологии
                        if not ("DeepSeek" in img["path"] or "autogen" in img["path"]):
                            continue
                        # Пропускаем аватарки, фавиконы и SVG (которые PIL не читает)
                        if any(
                            x in img["path"].lower() for x in ["avatar", "favicon", "logo", ".svg"]
                        ):
                            continue

                    logger.info(f"🔍 [OMNI-RAG] Indexing image: {img['path']}")
                    description = await vision.process_image(
                        image_path=img["abs_path"],
                        prompt="Опиши подробно, что на этом изображении: текст, объекты, схемы и логику.",
                    )

                    if description:
                        logger.info(
                            f"✅ [OMNI-RAG] Description generated for {img['path']}: {description[:50]}..."
                        )
                        # [FIX] Очистка описания от промпта, если модель его повторила
                        description = description.replace(
                            "Это файл из проекта Singularity 21.5. Опиши подробно, что на нем изображено, текст и логику (если это схема).",
                            "",
                        ).strip()
                        description = description.replace(
                            "Опиши подробно, что на этом изображении: текст, объекты, схемы и логику.",
                            "",
                        ).strip()

                        content = f"Изображение {img['path']}: {description}"
                        embedding = None
                        if get_embedding:
                            try:
                                embedding = await get_embedding(content)
                            except Exception:
                                pass

                        await conn.execute(
                            """
                            INSERT INTO knowledge_nodes (domain_id, content, embedding, confidence_score, metadata, is_verified)
                            VALUES ($1, $2, $3, 0.9, $4, true)
                        """,
                            domain_id,
                            content,
                            str(embedding) if embedding else None,
                            json.dumps(
                                {
                                    "source": "corporation_knowledge_system",
                                    "type": "image_description",
                                    "file_path": img["path"],
                                    "timestamp": knowledge["timestamp"],
                                }
                            ),
                        )
                        saved_count += 1
                        import gc

                        gc.collect()
                        await asyncio.sleep(0.5)
            except Exception as ve:
                logger.warning(f"⚠️ [OMNI-RAG] Ошибка обработки изображений: {ve}")

        # Сохраняем недавние изменения с эмбеддингом
        if recent_changes:
            changes_text = "\n".join(
                [
                    f"- {c.get('date', '')[:19]}: {c.get('message', '')[:100]}"
                    for c in recent_changes[:10]
                ]
            )
            content = f"Недавние изменения в корпорации ({len(recent_changes)}):\n{changes_text}"
            embedding = None
            if get_embedding:
                try:
                    embedding = await get_embedding(content)
                except Exception as e:
                    logger.debug(f"Ошибка создания эмбеддинга для изменений: {e}")

            await conn.execute(
                """
                INSERT INTO knowledge_nodes (domain_id, content, embedding, confidence_score, metadata, is_verified)
                VALUES ($1, $2, $3, 1.0, $4, true)
            """,
                domain_id,
                content,
                str(embedding) if embedding else None,
                json.dumps(
                    {
                        "source": "corporation_knowledge_system",
                        "type": "recent_changes",
                        "count": len(recent_changes),
                        "timestamp": knowledge["timestamp"],
                    }
                ),
            )
            saved_count += 1

        # Также сохраняем общий сводный узел для быстрого доступа
        summary_content = f"""Актуальное состояние корпорации (обновлено {knowledge["timestamp"]}):
- Доступно моделей Ollama: {len(ollama_models)}
- Доступно моделей MLX: {len(mlx_models)}
- Доступно скриптов: {len(scripts)}
- Доступно изображений (Omni-RAG): {len(images)}
- Недавних изменений: {len(recent_changes)}
Все знания доступны через search_knowledge."""

        embedding = None
        if get_embedding:
            try:
                embedding = await get_embedding(summary_content)
            except Exception as e:
                logger.debug(f"Ошибка создания эмбеддинга для сводки: {e}")

        await conn.execute(
            """
            INSERT INTO knowledge_nodes (domain_id, content, embedding, confidence_score, metadata, is_verified)
            VALUES ($1, $2, $3, 1.0, $4, true)
        """,
            domain_id,
            summary_content,
            str(embedding) if embedding else None,
            json.dumps(
                {
                    "source": "corporation_knowledge_system",
                    "type": "system_summary",
                    "version": "1.0",
                    "timestamp": knowledge["timestamp"],
                }
            ),
        )
        saved_count += 1

        logger.info(
            f"✅ Знания корпорации сохранены в базу знаний: {saved_count} узлов ({len(ollama_models)} Ollama, {len(mlx_models)} MLX, {len(scripts)} скриптов)"
        )

    def generate_system_prompt_update(
        self,
        knowledge: Dict[str, Any],
        top_insights: Optional[List[Dict[str, Any]]] = None,
        lessons_learned: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Генерировать обновление system prompt с актуальными знаниями (Singularity 10.0: + топ-инсайты)"""

        prompt = """
📚 АКТУАЛЬНЫЕ ЗНАНИЯ КОРПОРАЦИИ (обновлено автоматически {}):

🤖 ДОСТУПНЫЕ МОДЕЛИ:

Ollama модели ({}):
""".format(knowledge.get("timestamp", ""), knowledge["total_ollama_models"])

        for model in knowledge["ollama_models"]:
            size_info = (
                f" ({model.get('size', 0) / 1024 / 1024 / 1024:.1f} GB)"
                if model.get("size")
                else ""
            )
            prompt += f"- {model['name']}{size_info}\n"

        prompt += f"\nMLX модели ({knowledge['total_mlx_models']}):\n"
        for model in knowledge["mlx_models"]:
            path_info = f" ({model.get('path', '')})" if model.get("path") else ""
            prompt += f"- {model['name']}{path_info}\n"

        prompt += f"\n📜 ДОСТУПНЫЕ СКРИПТЫ ({knowledge['total_scripts']}):\n"
        # Группируем по типам
        scripts_by_type = {}
        for script in knowledge["scripts"]:
            script_type = script["type"]
            if script_type not in scripts_by_type:
                scripts_by_type[script_type] = []
            scripts_by_type[script_type].append(script)

        for script_type, scripts in scripts_by_type.items():
            prompt += f"\n{script_type.upper()} скрипты ({len(scripts)}):\n"
            for script in scripts[:20]:  # Первые 20 каждого типа
                prompt += f"  - {script['path']}\n"

        if knowledge["recent_changes"]:
            prompt += f"\n🔄 НЕДАВНИЕ ИЗМЕНЕНИЯ ({len(knowledge['recent_changes'])}):\n"
            for change in knowledge["recent_changes"][:10]:  # Последние 10
                prompt += f"- {change.get('date', '')[:19]}: {change.get('message', '')[:100]}\n"

        # Singularity 10.0: топ lessons learned из adaptive_learning_logs
        if lessons_learned:
            prompt += "\n📖 LESSONS LEARNED (adaptive_learning_logs):\n"
            for ll in lessons_learned[:5]:
                prompt += f"- {ll.get('learned_insight', '')[:300]}\n"
        # Singularity 10.0: топ-инсайты из knowledge_nodes (макс 2000 символов на блок)
        if top_insights:
            insights_block = "\n💡 ТОП-ИНСАЙТЫ КОРПОРАЦИИ (из knowledge_nodes):\n"
            for ins in top_insights:
                if len(insights_block) >= 2000:
                    break
                content = (ins.get("content") or "")[:350]
                if content:
                    domain_name = ins.get("domain_name") or ""
                    prefix = f"[{domain_name}] " if domain_name else ""
                    line = f"- {prefix}{content}\n"
                    if len(insights_block) + len(line) > 2000:
                        line = line[: 2000 - len(insights_block) - 3] + "...\n"
                    insights_block += line
            prompt += insights_block

        prompt += "\n⚠️ ВАЖНО: Ты всегда должен знать актуальное состояние корпорации!"
        prompt += "\n💡 Используй эти знания при выборе моделей и инструментов!"

        return prompt


async def update_all_agents_knowledge(pool=None):
    """Обновить знания всех агентов. Если передан pool (asyncpg), используем его для всех операций с БД."""
    print("DEBUG: Starting update_all_agents_knowledge", flush=True)
    system = CorporationKnowledgeSystem()
    knowledge = await system.update_corporation_knowledge(pool=pool)

    # Также извлекаем полные знания корпорации (системы, логика, умения)
    try:
        # Пробуем импортировать через разные пути
        try:
            from app.corporation_complete_knowledge import CorporationCompleteKnowledge
        except ImportError:
            # Пробуем через knowledge_os путь
            import sys

            knowledge_os_path = os.path.dirname(os.path.dirname(__file__))
            if knowledge_os_path not in sys.path:
                sys.path.insert(0, knowledge_os_path)
            from app.corporation_complete_knowledge import CorporationCompleteKnowledge

        complete_extractor = CorporationCompleteKnowledge()
        complete_result = await complete_extractor.extract_all(pool=pool)
        logger.info(
            f"✅ Извлечено полных знаний корпорации: {complete_result['total_extracted']} (сохранено: {complete_result['saved_to_db']})"
        )
    except Exception as e:
        logger.debug(f"Не удалось извлечь полные знания корпорации: {e}")

    # Singularity 10.0: топ-инсайты и lessons learned
    top_insights = []
    lessons_learned = []
    if ASYNCPG_AVAILABLE:
        try:
            if pool is not None:
                conn_ins = await pool.acquire()
            else:
                conn_ins = await asyncpg.connect(system.db_url, command_timeout=10)
            try:
                rows = await conn_ins.fetch("""
                    SELECT k.content, k.confidence_score, d.name as domain_name
                    FROM knowledge_nodes k
                    LEFT JOIN domains d ON k.domain_id = d.id
                    WHERE (k.is_verified = true OR k.confidence_score > 0.7)
                      AND k.created_at > NOW() - INTERVAL '7 days'
                      AND k.metadata->>'source' != 'corporation_knowledge_system'
                    ORDER BY k.confidence_score DESC, k.created_at DESC
                    LIMIT 10
                """)
                top_insights = [dict(r) for r in rows]
                # adaptive_learning_logs (high impact_score)
                ll_rows = await conn_ins.fetch("""
                    SELECT learned_insight, impact_score, learning_type
                    FROM adaptive_learning_logs
                    WHERE impact_score > 0.6
                    ORDER BY impact_score DESC
                    LIMIT 5
                """)
                lessons_learned = [dict(r) for r in ll_rows]
            finally:
                if pool is not None:
                    await pool.release(conn_ins)
                else:
                    await conn_ins.close()
        except Exception as e:
            logger.debug("Не удалось загрузить топ-инсайты/lessons: %s", e)

    prompt_update = system.generate_system_prompt_update(
        knowledge, top_insights=top_insights or None, lessons_learned=lessons_learned or None
    )

    # Сохраняем динамический контекст в expert_context (не в system_prompt!)
    # system_prompt остаётся статичным (~5KB), динамика живёт в expert_context
    if ASYNCPG_AVAILABLE:
        try:
            if pool is not None:
                conn = await pool.acquire()
            else:
                conn = await asyncpg.connect(system.db_url, command_timeout=30)
            try:
                experts = await conn.fetch("SELECT id, name FROM experts")

                for expert in experts:
                    # Upsert динамического контекста — заменяем полностью
                    await conn.execute(
                        """
                        INSERT INTO expert_context (expert_id, context_type, content, updated_at)
                        VALUES ($1, 'corporation_knowledge', $2, NOW())
                        ON CONFLICT (expert_id, context_type)
                        DO UPDATE SET content = EXCLUDED.content, updated_at = NOW()
                        """,
                        expert["id"],
                        prompt_update,
                    )

                logger.info(
                    f"✅ Динамический контекст обновлён для {len(experts)} агентов "
                    f"(expert_context, размер блока: {len(prompt_update)} chars)"
                )
            finally:
                if pool is not None:
                    await pool.release(conn)
                else:
                    await conn.close()
        except Exception as e:
            logger.error(f"Ошибка обновления expert_context: {e}")

    return knowledge


if __name__ == "__main__":
    asyncio.run(update_all_agents_knowledge())
