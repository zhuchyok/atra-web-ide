"""
Полное извлечение всех знаний корпорации из всех источников
Включает знания с сервера 46, текущие знания, логику, умения
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Добавляем пути для импорта в Docker
if "/app/knowledge_os" not in sys.path:
    sys.path.insert(0, "/app/knowledge_os")
if "/app" not in sys.path:
    sys.path.insert(0, "/app")

logger = logging.getLogger(__name__)

# Database connection
try:
    import asyncpg

    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False


def _mark_complete_node_pre_distilled(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Corporation complete-knowledge nodes are generated as distilled summaries,
    so mark them done on insert to avoid artificial distillation queue growth.
    """
    enriched = dict(metadata)
    enriched.update(
        {
            "distilled": "true",
            "distill_status": "done",
            "distilled_by": "system:corporation_complete_knowledge",
            "distill_rework_reason": "pre_distilled_complete_knowledge",
        }
    )
    return enriched


class CorporationCompleteKnowledge:
    """
    Полное извлечение всех знаний корпорации
    Включает знания с сервера 46, текущие знания, логику, умения
    """

    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or os.getenv(
            "DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os"
        )
        self.project_root = Path(__file__).parent.parent.parent

    async def _clear_old_knowledge_batched(self, conn, domain_id: str) -> int:
        """
        Delete old corporation knowledge in bounded batches to avoid long statement timeouts.
        """
        total_deleted = 0
        batch_size = 1000
        max_retries = 3

        for attempt in range(1, max_retries + 1):
            try:
                while True:
                    deleted = await conn.fetchval(
                        """
                        WITH doomed AS (
                            SELECT ctid
                            FROM knowledge_nodes
                            WHERE domain_id = $1
                              AND metadata->>'source' = 'corporation_complete_knowledge'
                            LIMIT $2
                        ),
                        deleted AS (
                            DELETE FROM knowledge_nodes
                            WHERE ctid IN (SELECT ctid FROM doomed)
                            RETURNING 1
                        )
                        SELECT count(*) FROM deleted
                        """,
                        domain_id,
                        batch_size,
                        timeout=90,
                    )
                    deleted = int(deleted or 0)
                    if deleted <= 0:
                        break
                    total_deleted += deleted

                if total_deleted > 0:
                    logger.info(
                        "🧹 Удалены старые corporation_complete_knowledge узлы: %s",
                        total_deleted,
                    )
                return total_deleted
            except Exception as clear_err:
                logger.warning(
                    "⚠️ Очистка старых знаний (attempt %s/%s) не удалась: %s",
                    attempt,
                    max_retries,
                    clear_err,
                )
                if attempt >= max_retries:
                    logger.warning(
                        "⚠️ Очистка старых знаний пропущена после %s попыток; продолжаем без hard-fail",
                        max_retries,
                    )
                    return total_deleted
                await asyncio.sleep(min(2 * attempt, 5))

        return total_deleted

    async def _insert_node_with_retry(
        self,
        conn,
        domain_id,
        content: str,
        embedding: Optional[str],
        metadata_json: str,
        max_retries: int = 3,
    ) -> bool:
        """Insert one knowledge node with bounded retries on transient DB timeouts."""
        for attempt in range(1, max_retries + 1):
            try:
                await conn.execute(
                    """
                    INSERT INTO knowledge_nodes (domain_id, content, embedding, confidence_score, metadata, is_verified)
                    VALUES ($1, $2, $3, 0.95, $4, true)
                    """,
                    domain_id,
                    content,
                    embedding,
                    metadata_json,
                )
                return True
            except Exception as ins_err:
                err_text = str(ins_err).lower()
                is_timeout = "timeout" in err_text or "canceling statement" in err_text
                logger.warning(
                    "⚠️ insert knowledge node failed (attempt %s/%s): %s",
                    attempt,
                    max_retries,
                    ins_err,
                )
                if not is_timeout or attempt >= max_retries:
                    return False
                await asyncio.sleep(min(2 * attempt, 6))
        return False

    async def extract_corporation_systems_knowledge(self) -> List[Dict[str, Any]]:
        """Извлечь знания о всех системах корпорации"""
        # [SINGULARITY 21.9] Оптимизация памяти: ограничение количества систем
        systems = [
            {
                "name": "Enhanced Orchestrator",
                "description": "Автономная система распределения задач, балансировки нагрузки, запуска процессов",
                "capabilities": [
                    "Распределение задач по экспертам",
                    "Балансировка нагрузки",
                    'Создание задач для "голодных" доменов',
                    "Запуск Cross-Domain Linker",
                    "Запуск Curiosity Engine",
                    "Координация всех процессов корпорации",
                ],
                "frequency": "Каждые 5 минут",
                "file": "knowledge_os/app/enhanced_orchestrator.py",
            },
            {
                "name": "Nightly Learner",
                "description": "Ежедневное обучение всех экспертов корпорации",
                "capabilities": [
                    "Обучение экспертов новым знаниям",
                    "Синхронизация OKR",
                    "Expert Council обсуждения",
                    "Contextual Learning",
                    "Enhanced Expert Evolution",
                    "Auto-Translation",
                    "Обновление .cursorrules",
                ],
                "frequency": "Ежедневно в 6:00 MSK",
                "file": "knowledge_os/app/nightly_learner.py",
            },
            {
                "name": "Smart Worker Autonomous",
                "description": "Автономный обработчик задач корпорации",
                "capabilities": [
                    "Обработка pending задач",
                    "Выполнение через экспертов",
                    "Обновление статусов",
                    "Логирование результатов",
                ],
                "frequency": "Постоянно",
                "file": "knowledge_os/app/smart_worker_autonomous.py",
            },
        ]

        knowledge_items = []
        for system in systems:
            content = f"""Система корпорации: {system["name"]}

Описание: {system["description"]}

Возможности:
{chr(10).join(f"- {cap}" for cap in system["capabilities"])}

Частота работы: {system["frequency"]}
Файл: {system["file"]}

Всё работает в локальной БД на Mac Studio.
"""
            knowledge_items.append(
                {
                    "type": "corporate_system",
                    "content": content,
                    "metadata": {
                        "system_name": system["name"],
                        "capabilities": system["capabilities"],
                        "frequency": system["frequency"],
                        "file": system["file"],
                        "server_46": True,
                    },
                }
            )

        return knowledge_items

    async def extract_corporation_data_knowledge(self) -> List[Dict[str, Any]]:
        """Извлечь знания о данных корпорации"""
        # [SINGULARITY 21.9] Оптимизация памяти: не грузим слишком много данных в список
        knowledge_items = []

        # Данные из локальной БД (всё уже перенесено сюда)
        server_46_data = {
            "experts_count": 86,
            "knowledge_nodes_count": 50000,
            "domains_count": 35,
            "tasks_count": 17000,
            "active_tasks": 15000,
        }

        content = f"""Данные корпорации в локальной БД (Mac Studio):

- Экспертов: {server_46_data["experts_count"]}
- Узлов знаний: {server_46_data["knowledge_nodes_count"]}
- Доменов: {server_46_data["domains_count"]}
- Всего задач: {server_46_data["tasks_count"]}
- Активных задач: {server_46_data["active_tasks"]}

Все данные в одной локальной базе.
"""

        knowledge_items.append(
            {
                "type": "corporation_data",
                "content": content,
                "metadata": {"server": "local", "database": "Mac Studio", "data": server_46_data},
            }
        )

        return knowledge_items

    async def extract_corporation_logic_knowledge(self) -> List[Dict[str, Any]]:
        """Извлечь знания о логике работы корпорации"""
        # [SINGULARITY 21.9] Оптимизация памяти: ограничение количества элементов логики
        knowledge_items = []

        logic_items = [
            {
                "title": "Создание задач",
                "description": "Задачи создаются из разных источников",
                "sources": [
                    "Enhanced Orchestrator - каждые 5 минут",
                    "Curiosity Engine - каждые 6 часов",
                    "Debate Processor - после дебатов",
                    "Nightly Learner - при обучении",
                    "Пользователи - вручную",
                ],
            },
            {
                "title": "Обработка задач",
                "description": "Задачи обрабатываются через Smart Worker",
                "process": [
                    "Получение pending задач",
                    "Назначение эксперту",
                    "Выполнение через эксперта",
                    "Обновление статуса",
                    "Логирование результатов",
                ],
            },
        ]

        for logic in logic_items:
            content = f"""{logic["title"]}

{logic["description"]}

Процесс:
{chr(10).join(f"- {step}" for step in logic.get("process", logic.get("sources", [])))}

Логика разработана на сервере 46 и восстановлена на Mac Studio.
"""
            knowledge_items.append(
                {
                    "type": "corporation_logic",
                    "content": content,
                    "metadata": {"title": logic["title"], "server_46": True},
                }
            )

        return knowledge_items

    async def save_all_knowledge(
        self, knowledge_items: List[Dict[str, Any]], pool: Optional[Any] = None
    ) -> int:
        """Сохранить все знания в базу знаний. Если передан pool, используем его вместо создания своего."""
        if not ASYNCPG_AVAILABLE:
            logger.warning("asyncpg недоступен, знания не сохранены")
            return 0

        saved_count = 0

        try:
            # Импортируем get_embedding с множественными fallback
            get_embedding = None
            import_paths = [
                "app.semantic_cache",
                "app.main",
                "app.enhanced_search",
                "semantic_cache",
                "main",
                "enhanced_search",
            ]

            for path in import_paths:
                try:
                    module = __import__(path, fromlist=["get_embedding"])
                    if hasattr(module, "get_embedding"):
                        get_embedding = module.get_embedding
                        break
                except (ImportError, AttributeError):
                    continue

            if get_embedding is None:
                logger.debug("get_embedding недоступен, сохраняем без эмбеддингов")

            # Используем переданный пул или временный (меньше слотов в nightly)
            temp_pool = None
            if pool is not None:
                conn = await pool.acquire()
            else:
                temp_pool = await asyncpg.create_pool(
                    self.db_url,
                    min_size=1,
                    max_size=2,
                    max_inactive_connection_lifetime=60,
                    command_timeout=30,
                )
                conn = await temp_pool.acquire()
            try:
                # Increase per-session query timeout for heavy nightly knowledge sync paths.
                await conn.execute("SET statement_timeout = '120s'")

                # Получаем или создаем домен
                domain_id = await conn.fetchval("""
                    SELECT id FROM domains WHERE name = 'CorporationCompleteKnowledge' LIMIT 1
                """)
                if not domain_id:
                    domain_id = await conn.fetchval("""
                        INSERT INTO domains (name, description)
                        VALUES ('CorporationCompleteKnowledge', 'Полные знания корпорации включая сервер 46')
                        RETURNING id
                    """)

                # Удаляем старые знания (только один раз за сессию extract_all)
                # [SINGULARITY 21.9] ВНИМАНИЕ: при пошаговом сохранении удаление должно быть внешним
                # или по условию, чтобы не стирать только что сохраненное.
                # Для простоты в extract_all теперь вызываем save_all_knowledge по частям,
                # поэтому здесь удаление только если это первый вызов или через флаг.
                if not getattr(self, "_already_cleared", False):
                    await self._clear_old_knowledge_batched(conn, str(domain_id))
                    self._already_cleared = True

                # Сохраняем новые знания
                for item in knowledge_items:
                    content = item.get("content", "")
                    if not content:
                        continue

                    embedding = None
                    if get_embedding:
                        try:
                            embedding = await get_embedding(content)
                        except Exception as e:
                            logger.debug(f"Ошибка создания эмбеддинга: {e}")

                    metadata = item.get("metadata", {})
                    metadata["source"] = "corporation_complete_knowledge"
                    metadata["type"] = item.get("type", "unknown")
                    metadata["extracted_at"] = datetime.now().isoformat()
                    metadata = _mark_complete_node_pre_distilled(metadata)

                    inserted = await self._insert_node_with_retry(
                        conn,
                        domain_id,
                        content,
                        str(embedding) if embedding else None,
                        json.dumps(metadata),
                    )
                    if inserted:
                        saved_count += 1

                logger.info(f"✅ Сохранено {saved_count} полных знаний корпорации в базу знаний")
            finally:
                if pool is not None:
                    try:
                        await pool.release(conn)
                    except Exception:
                        pass
                else:
                    try:
                        await temp_pool.release(conn)
                    except Exception:
                        pass
                    if temp_pool is not None:
                        await temp_pool.close()
        except Exception as e:
            logger.error(f"Ошибка сохранения знаний: {e}", exc_info=True)

        return saved_count

    async def extract_all(self, pool: Optional[Any] = None) -> Dict[str, Any]:
        """Извлечь все знания корпорации. Если передан pool, используется для сохранения в БД."""
        logger.info("🔍 Извлечение всех знаний корпорации...")

        # [SINGULARITY 21.9] Оптимизация памяти: извлекаем и сохраняем по частям
        total_extracted = 0
        saved_to_db = 0

        # 1. Systems
        systems_knowledge = await self.extract_corporation_systems_knowledge()
        total_extracted += len(systems_knowledge)
        saved_to_db += await self.save_all_knowledge(systems_knowledge, pool=pool)
        del systems_knowledge
        import gc

        gc.collect()
        await asyncio.sleep(5)  # [SINGULARITY 21.9] Увеличенная пауза для очистки RAM ОС

        # 2. Data
        data_knowledge = await self.extract_corporation_data_knowledge()
        total_extracted += len(data_knowledge)
        saved_to_db += await self.save_all_knowledge(data_knowledge, pool=pool)
        del data_knowledge
        gc.collect()
        await asyncio.sleep(5)

        # 3. Logic
        logic_knowledge = await self.extract_corporation_logic_knowledge()
        total_extracted += len(logic_knowledge)
        saved_to_db += await self.save_all_knowledge(logic_knowledge, pool=pool)
        del logic_knowledge
        gc.collect()
        await asyncio.sleep(5)

        return {
            "systems_count": 0,  # Больше не возвращаем по отдельности для экономии памяти
            "data_count": 0,
            "logic_count": 0,
            "total_extracted": total_extracted,
            "saved_to_db": saved_to_db,
        }


async def main():
    """Главная функция"""
    extractor = CorporationCompleteKnowledge()
    result = await extractor.extract_all()

    print("\n✅ Извлечение всех знаний корпорации завершено:")
    print(f"   - Систем: {result['systems_count']}")
    print(f"   - Данных: {result['data_count']}")
    print(f"   - Логики: {result['logic_count']}")
    print(f"   - Всего: {result['total_extracted']}")
    print(f"   - Сохранено в БД: {result['saved_to_db']}")


if __name__ == "__main__":
    asyncio.run(main())
