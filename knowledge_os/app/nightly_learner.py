import asyncio
import gc
import json
import logging
import os
import random
import subprocess
import sys
import time
from datetime import datetime, timedelta
from typing import Optional

import asyncpg
from memory_guard import should_pause_heavy_task
from resource_manager import acquire_resource_lock

logger = logging.getLogger(__name__)


def _log_step(msg: str) -> None:
    """Печать и сброс буфера — при OOM/Killed в логах будет видно последний шаг."""
    print(msg)
    sys.stdout.flush()
    sys.stderr.flush()


# Пути для Mac Studio и Linux (без /root/)
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
_KNOWLEDGE_OS_ROOT = os.path.dirname(_APP_DIR)
from contextual_learner import (
    AdaptiveLearner,
    ContextualMemory,
    NeedPredictor,
    PersonalizationEngine,
)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")


def _node_type(url: str) -> str:
    """Определяет тип узла по URL: ollama (11434) или mlx (11435)."""
    u = (url or "").rstrip("/")
    if ":11435" in u or "11435/" in u:
        return "mlx"
    if ":11434" in u or "11434/" in u:
        return "ollama"
    return "ollama"  # default


async def run_local_model(prompt: str, model: Optional[str] = None) -> Optional[str]:
    """Запуск локальной модели (без токенов). Список моделей берётся из available_models_scanner — Ollama и MLX раздельно."""
    import httpx

    ollama_url = os.getenv("OLLAMA_BASE_URL") or os.getenv("OLLAMA_URL") or "http://localhost:11434"
    mlx_url = os.getenv("MAC_LLM_URL") or os.getenv("MLX_API_URL") or "http://localhost:11435"
    raw_nodes = [
        os.getenv("MAC_LLM_URL") or mlx_url,
        os.getenv("OLLAMA_BASE_URL") or os.getenv("OLLAMA_URL") or ollama_url,
        os.getenv("SERVER_LLM_URL") or ollama_url,
    ]
    # Дедупликация по URL и определение типа по порту (11434=ollama, 11435=mlx)
    seen = set()
    unique_nodes = []
    for url in raw_nodes:
        u = (url or "").rstrip("/")
        if u in seen:
            continue
        seen.add(u)
        kind = _node_type(u)
        unique_nodes.append((u, kind))

    logger.info("[NIGHTLY_LEARNER] run_local_model nodes=%s", [n[0] for n in unique_nodes])

    try:
        from available_models_scanner import get_available_models, pick_best_mlx, pick_best_ollama
    except ImportError:
        try:
            from app.available_models_scanner import (
                get_available_models,
                pick_best_mlx,
                pick_best_ollama,
            )
        except ImportError:
            logger.warning(
                "[NIGHTLY_LEARNER] available_models_scanner not found, cannot get model lists"
            )
            return None

    mlx_list, ollama_list = await get_available_models(mlx_url, ollama_url, force_refresh=False)
    logger.info("[NIGHTLY_LEARNER] scanner: mlx=%s ollama=%s", len(mlx_list), len(ollama_list))

    for node_url, node_kind in unique_nodes:
        selected_model = None
        if node_kind == "ollama":
            selected_model = pick_best_ollama(ollama_list) if ollama_list else None
        else:
            selected_model = pick_best_mlx(mlx_list) if mlx_list else None

        if not selected_model:
            logger.debug("[NIGHTLY_LEARNER] skip node=%s kind=%s no model", node_url, node_kind)
            continue

        logger.info(
            "[NIGHTLY_LEARNER] trying node_url=%s selected_model=%s kind=%s",
            node_url,
            selected_model,
            node_kind,
        )

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                health = await client.get(f"{node_url}/api/tags", timeout=3.0)
                if health.status_code != 200:
                    logger.info(
                        "[NIGHTLY_LEARNER] node %s /api/tags status_code=%s",
                        node_url,
                        health.status_code,
                    )
                    continue
                tags_response = health.json()
                available_tags = [m.get("name", "") for m in tags_response.get("models", [])]
                logger.info(
                    "[NIGHTLY_LEARNER] node=%s /api/tags 200 models_count=%s names=%s",
                    node_url,
                    len(available_tags),
                    available_tags[:15],
                )

                if selected_model not in available_tags:
                    selected_model = available_tags[0] if available_tags else None
                if not selected_model:
                    continue

                logger.info(
                    "[NIGHTLY_LEARNER] POST %s/api/generate model=%s", node_url, selected_model
                )
                response = await client.post(
                    f"{node_url}/api/generate",
                    json={"model": selected_model, "prompt": prompt, "stream": False},
                    timeout=120.0,
                )

                if response.status_code == 200:
                    result = response.json()
                    out = result.get("response", "").strip()
                    logger.info(
                        "[NIGHTLY_LEARNER] success node=%s model=%s response_len=%s",
                        node_url,
                        selected_model,
                        len(out),
                    )
                    return out
                if response.status_code == 404:
                    body = (response.text or "")[:200]
                    logger.warning(
                        "[NIGHTLY_LEARNER] Ollama 404: node=%s model=%s; available_models=%s body=%s",
                        node_url,
                        selected_model,
                        available_tags,
                        body,
                    )
                    continue
                logger.warning(
                    "[NIGHTLY_LEARNER] node=%s /api/generate status_code=%s body=%s",
                    node_url,
                    response.status_code,
                    (response.text or "")[:200],
                )
        except httpx.TimeoutException:
            logger.debug("[NIGHTLY_LEARNER] timeout node=%s", node_url)
            continue
        except Exception as e:
            logger.warning("[NIGHTLY_LEARNER] error node=%s: %s", node_url, e)
            continue

    return None


async def run_cursor_agent(prompt: str) -> Optional[str]:
    """Использование облачной модели через Cursor Agent (если доступен)"""
    # Проверяем доступность cursor-agent
    cursor_agent_paths = [
        os.path.expanduser("~/.local/bin/cursor-agent"),
        "/usr/local/bin/cursor-agent",
        "/root/.local/bin/cursor-agent",
    ]

    cursor_agent_path = None
    for path in cursor_agent_paths:
        if os.path.exists(path) and os.access(path, os.X_OK):
            cursor_agent_path = path
            break

    if not cursor_agent_path:
        result = await run_local_model(prompt)
        return result

    try:
        env = os.environ.copy()
        result = subprocess.run(
            [cursor_agent_path, "--print", prompt],
            capture_output=True,
            text=True,
            check=True,
            timeout=300,
            env=env,
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        print(f"⚠️ Cursor agent timeout для промпта: {prompt[:50]}...")
        return None
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Cursor agent error (code {e.returncode}): {e.stderr[:200]}")
        return None
    except Exception as e:
        print(f"⚠️ Cursor agent exception: {e}")
        return None


async def get_nightly_context(conn):
    """Синхронизация OKR и получение контекста ошибок за день (Phase 0)."""
    # 1. OKR
    okrs = await conn.fetch(
        "SELECT objective FROM okrs WHERE created_at > NOW() - INTERVAL '30 days'"
    )
    okr_text = "\n".join([f"- {o['objective']}" for o in okrs])

    # 2. ОШИБКИ И ПЛОХОЙ FEEDBACK (Phase 0: Error Analysis)
    bad_interactions = await conn.fetch("""
        SELECT user_query, assistant_response, metadata->>'error' as error
        FROM interaction_logs
        WHERE (feedback_score < 3 OR metadata->>'error' IS NOT NULL)
          AND created_at > NOW() - INTERVAL '24 hours'
        LIMIT 10
    """)
    error_context = ""
    if bad_interactions:
        error_context = "\n".join(
            [
                f"Q: {i['user_query'][:100]} | Error: {i['error'] or 'Low feedback'}"
                for i in bad_interactions
            ]
        )
        print(f"⚠️ Phase 0: Найдено {len(bad_interactions)} проблемных взаимодействий для анализа.")

    return okr_text, error_context


async def sync_okrs(conn):
    """Синхронизация метрик в таблице OKR с реальными данными БД."""
    print("Syncing OKR metrics...")
    try:
        await conn.execute("""
            UPDATE key_results
            SET current_value = (SELECT count(*) FROM knowledge_nodes)
            WHERE description ILIKE '%Объем базы знаний%' OR description ILIKE '%узлов%'
        """)
        await conn.execute("""
            UPDATE key_results
            SET current_value = (SELECT COALESCE(sum(usage_count), 0) FROM knowledge_nodes)
            WHERE description ILIKE '%Использование%' OR description ILIKE '%ROI%'
        """)
        print("OKR Sync completed.")
    except Exception as e:
        print(f"OKR Sync error: {e}")


async def create_debate_for_hypothesis(conn, knowledge_node_id, content, domain_id=None):
    """Создаёт дебат по гипотезе: находит эксперта по домену и вызывает run_expert_council."""
    expert = None
    if domain_id:
        try:
            expert = await conn.fetchrow(
                "SELECT id FROM experts WHERE domain_id = $1 ORDER BY RANDOM() LIMIT 1", domain_id
            )
        except Exception:
            pass
    if not expert and domain_id:
        try:
            domain = await conn.fetchrow("SELECT name FROM domains WHERE id = $1", domain_id)
            if domain:
                expert = await conn.fetchrow(
                    "SELECT id FROM experts WHERE department = $1 ORDER BY RANDOM() LIMIT 1",
                    domain["name"],
                )
        except Exception:
            pass
    if not expert:
        try:
            expert = await conn.fetchrow("SELECT id FROM experts ORDER BY RANDOM() LIMIT 1")
        except Exception:
            pass
    if expert:
        await run_expert_council(conn, knowledge_node_id, content, expert["id"])
    else:
        logger.warning("No experts found for hypothesis debate, skipping")


async def run_expert_council(conn, knowledge_id, content, original_expert_id):
    """
    Инициирует многораундовые дебаты (Red Team Pattern) между экспертами.
    Раунд 1: Критика инсайта.
    Раунд 2: Ответ автора на критику.
    Раунд 3: Финальный синтез и вердикт.
    """
    _log_step(
        f"[NIGHTLY] Enhanced Expert Council (Red Team) starting for knowledge_id={knowledge_id}"
    )
    try:
        import gc

        gc.collect()
        # 1. Выбираем автора и оппонентов
        author = await conn.fetchrow(
            "SELECT name, role FROM experts WHERE id = $1", original_expert_id
        )
        opponents = await conn.fetch(
            """
            SELECT id, name, role, system_prompt
            FROM experts
            WHERE id != $1
            ORDER BY RANDOM() LIMIT 2
        """,
            original_expert_id,
        )

        if not opponents or not author:
            return

        debate_log = []
        debate_log.append(f"📝 **Автор ({author['name']}):** {content}")

        # РАУНД 1: КРИТИКА (RED TEAM)
        criticisms = []
        for opp in opponents:
            prompt = f"""
            ВЫ - RED TEAM ЭКСПЕРТ.
            РОЛЬ: {opp["name"]}, {opp["role"]}.
            ЗАДАЧА: Найдите 3 критических уязвимости, логических ошибки или практических сложности в следующем инсайте:
            "{content}"

            ОТВЕТЬТЕ ЖЕСТКО И ПО СУЩЕСТВУ (2-3 предложения).
            """
            comment = await run_local_model(prompt) or await run_cursor_agent(prompt)
            if comment:
                criticisms.append(f"🧐 {opp['name']} ({opp['role']}): {comment}")
                debate_log.append(f"❌ **Критика от {opp['name']}:** {comment}")

        # РАУНД 2: ОТВЕТ АВТОРА
        if criticisms:
            rebuttal_prompt = f"""
            ВЫ - {author["name"]}, {author["role"]}.
            ВАШ ИНСАЙТ: "{content}"
            КРИТИКА:
            {chr(10).join(criticisms)}

            ЗАДАЧА: Ответьте на критику. Признайте ошибки, если они есть, или обоснуйте свою позицию.
            ОТВЕТЬТЕ КРАТКО (2-3 предложения).
            """
            rebuttal = await run_local_model(rebuttal_prompt) or await run_cursor_agent(
                rebuttal_prompt
            )
            if rebuttal:
                debate_log.append(f"🛡️ **Ответ автора ({author['name']}):** {rebuttal}")

        # РАУНД 3: ФИНАЛЬНЫЙ СИНТЕЗ (КОНСЕНСУС)
        synthesis_prompt = f"""
        ВЫ - НЕЙТРАЛЬНЫЙ АРБИТР КОРПОРАЦИИ.
        ХОД ОБСУЖДЕНИЯ:
        {chr(10).join(debate_log)}

        ЗАДАЧА: Сформулируйте итоговый консенсус. Насколько инсайт полезен для корпорации?
        Укажите финальный уровень уверенности (0.0 - 1.0).
        """
        consensus = await run_local_model(synthesis_prompt) or await run_cursor_agent(
            synthesis_prompt
        )

        if consensus:
            # Сохраняем дебаты
            full_summary = "\n\n".join(debate_log) + f"\n\n🏁 **ИТОГОВЫЙ КОНСЕНСУС:**\n{consensus}"
            await conn.execute(
                """
                INSERT INTO expert_discussions (knowledge_node_id, expert_ids, topic, consensus_summary, status)
                VALUES ($1, $2, $3, $4, 'closed')
            """,
                knowledge_id,
                [original_expert_id] + [o["id"] for o in opponents],
                content[:100],
                full_summary,
            )

            # Обновляем метаданные узла
            await conn.execute(
                """
                UPDATE knowledge_nodes
                SET metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object('council_review', $1::text, 'red_team_status', 'passed')
                WHERE id = $2
            """,
                consensus,
                knowledge_id,
            )
            _log_step("✅ Enhanced Expert Council finished successfully.")

    except Exception as e:
        print(f"❌ Enhanced Expert Council error: {e}")
        import traceback

        traceback.print_exc()


async def nightly_learning_cycle():
    async with acquire_resource_lock("nightly_learner"):
        start_time = datetime.now()
        _log_step(
            f"[{start_time}] Total Nightly Learning Cycle (Council Phase enabled) starting..."
        )

        # Обновляем знания корпорации перед обучением (один пул — меньше слотов к БД)
        _log_step("[NIGHTLY] Phase: corporation knowledge update")
        shared_pool = None
        try:
            shared_pool = await asyncpg.create_pool(
                DB_URL,
                min_size=1,
                max_size=4,
                command_timeout=60,
            )
            try:
                try:
                    from corporation_knowledge_system import update_all_agents_knowledge
                except ImportError:
                    from app.corporation_knowledge_system import update_all_agents_knowledge
                await update_all_agents_knowledge(pool=shared_pool)
                print("✅ Знания корпорации обновлены перед обучением")
            finally:
                await shared_pool.close()
        except Exception as e:
            print(f"⚠️ Не удалось обновить знания корпорации: {e}")
            if shared_pool:
                await shared_pool.close()

        # Сброс памяти после тяжёлой фазы (1948+ скриптов, эмбеддинги) — снижает риск OOM (CHANGES §74)
        import gc

        gc.collect()
        await asyncio.sleep(10)  # [SINGULARITY 21.9] Большая пауза для очистки RAM ОС

        # --- ФАЗА: ОБНОВЛЕНИЕ ЗНАНИЙ ГИГАНТОВ (External Docs → AI Research) [опционально] ---
        if os.getenv("ENABLE_NIGHTLY_EXTERNAL_INDEX", "false").lower() in ("true", "1"):
            _log_step("📚 Running External Docs indexing (знания гигантов)...")
            try:
                try:
                    from index_external_docs import run_indexing
                except ImportError:
                    from app.index_external_docs import run_indexing
                await run_indexing()
                print("✅ External Docs (AI Research) indexed.")
            except Exception as e:
                print(f"⚠️ External Docs indexing error: {e}")
        else:
            _log_step("ℹ️ External Docs indexing skipped (ENABLE_NIGHTLY_EXTERNAL_INDEX not set)")

        # --- ФАЗА: ОДИН ЦИКЛ ВНЕДРЕНИЯ ИЗ ЗНАНИЙ ГИГАНТОВ (Perpetual Evolution) ---
        _log_step("🌐 Running one Perpetual Evolution cycle (research from giants → task)...")
        try:
            try:
                from perpetual_evolution import PerpetualEvolution
            except ImportError:
                from app.perpetual_evolution import PerpetualEvolution
            engine = PerpetualEvolution()
            ok = await engine.run_one_cycle()
            if ok:
                print("✅ Perpetual Evolution: one upgrade task created from giants.")
            else:
                print("ℹ️ Perpetual Evolution: no new upgrade proposed this run.")
        except Exception as e:
            print(f"⚠️ Perpetual Evolution error: {e}")

        # Используем get_pool из evaluator для совместимости с подключением к БД
        from evaluator import get_pool

        pool = await get_pool()
        conn = await pool.acquire()

        # Ещё один сброс перед циклом по экспертам (освобождаем ссылки от corporation/PerpetualEvolution)
        import gc

        gc.collect()
        await asyncio.sleep(5)  # [SINGULARITY 21.9] Пауза перед циклом обучения экспертов

        # Phase 0: Получаем контекст OKR и ошибок
        okr_context, error_context = await get_nightly_context(conn)
        await sync_okrs(conn)

        # Получаем всех активных экспертов или тех, кто не обучался давно
        # Обучаем всех экспертов, но с учетом времени последнего обучения
        # Если эксперт обучался недавно (< 24 часов), пропускаем его
        experts = await conn.fetch("""
            SELECT id, name, role, department, system_prompt, last_learned_at
            FROM experts
            ORDER BY
                CASE
                    WHEN last_learned_at IS NULL THEN 0
                    WHEN last_learned_at < NOW() - INTERVAL '24 hours' THEN 1
                    ELSE 2
                END,
                RANDOM()
        """)

        total_learned = 0
        total_experts = len(experts)
        learned_today = 0
        skipped_recent = 0

        print(f"📚 Найдено экспертов для обучения: {total_experts}")

        for idx, expert in enumerate(experts):
            if idx % 3 == 0:
                import gc

                gc.collect()
                await asyncio.sleep(2)  # [SINGULARITY 21.9] Частая пауза в цикле обучения
            _log_step(f"[NIGHTLY] Expert {idx + 1}/{total_experts}: {expert.get('name', '?')}")

            # [SINGULARITY 14.3] Memory Guard
            if should_pause_heavy_task():
                _log_step("⏳ [MEMORY GUARD] High RAM usage. Pausing nightly learner for 60s...")
                await asyncio.sleep(60)
                if should_pause_heavy_task():
                    _log_step(
                        "⏭️ [MEMORY GUARD] Still high RAM. Skipping this expert to prevent OOM."
                    )
                    continue

            expert_name = expert["name"]
            expert_role = expert["role"]
            last_learned = expert.get("last_learned_at")

            # Пропускаем экспертов, которые обучались менее 24 часов назад
            # Проверка уже сделана в SQL запросе, но можно добавить дополнительную проверку
            if last_learned:
                # last_learned из БД - это timezone-aware datetime
                # Используем прямое сравнение в SQL, но для логирования конвертируем
                print(f"\n>>> Learning session for: {expert_name} ({expert_role})")

                # Вычисляем время с учетом timezone
                if hasattr(last_learned, "replace"):
                    # Это datetime объект
                    if last_learned.tzinfo:
                        # timezone-aware, конвертируем в naive для сравнения
                        last_learned_utc = last_learned.astimezone().replace(tzinfo=None)
                    else:
                        last_learned_utc = last_learned

                    hours_ago = (datetime.now() - last_learned_utc).total_seconds() / 3600
                    print(f"   Последнее обучение: {hours_ago:.1f} часов назад")

                    # Дополнительная проверка на клиенте (основная уже в SQL)
                    if hours_ago < 24:
                        print(
                            f"⏭️  Пропуск {expert_name} - уже обучался {hours_ago:.1f} часов назад"
                        )
                        skipped_recent += 1
                        continue
                else:
                    print(f"\n>>> Learning session for: {expert_name} ({expert_role})")
                    print(f"   Последнее обучение: {last_learned} (формат не datetime)")
            else:
                print(f"\n>>> Learning session for: {expert_name} ({expert_role})")
                print("   Первое обучение")

            # Используем локальную модель для обучения (run_local_model использует сканер Ollama/MLX)
            # Adversarial Self-Play: Эксперт должен учитывать OKR и прошлые ошибки
            gap_prompt = f"""ВЫ - {expert_name}, {expert_role}.
            ЦЕЛЬ КОРПОРАЦИИ (OKR):
            {okr_context}

            ПРОБЛЕМЫ ЗА ДЕНЬ (Phase 0):
            {error_context if error_context else "Ошибок не зафиксировано."}

            ЗАДАЧА: Какая одна самая важная технология или тренд 2026 года в области {expert["department"]}
            поможет решить указанные проблемы и достичь целей?
            ОТВЕТЬТЕ ОДНОЙ ФРАЗОЙ.
            """

            topic = await run_local_model(gap_prompt)
            if not topic or len(topic.strip()) < 5:
                topic = await run_cursor_agent(gap_prompt)
            if not topic or len(topic.strip()) < 5:
                dept = expert.get("department", "General")
                current_year = datetime.now().year
                topic = f"Актуальные технологии и тренды {current_year} года в области {dept}"

            # РЕФЛЕКСИЯ (Adversarial Self-Play Phase 2)
            search_prompt = f"""Исследуй '{topic}'.
            Сформулируй 1-2 глубоких инсайта.
            КРИТИЧЕСКИЙ ФИЛЬТР: Найди 1 причину, почему этот инсайт может быть ошибочным или бесполезным.

            Верни JSON:
            {{
                "topic": "{topic}",
                "summary": "...",
                "insights": [ {{"content": "...", "confidence": 0.95}} ],
                "self_criticism": "..."
            }}
            ОТВЕТЬ ТОЛЬКО ЧИСТЫМ JSON.
            """

            search_output = await run_local_model(search_prompt)
            if not search_output or ("insights" not in search_output and "{" not in search_output):
                search_output = await run_cursor_agent(search_prompt)

            if search_output:
                try:
                    data_str = search_output.strip()
                    if "```" in data_str:
                        data_str = data_str.split("```")[1].replace("json", "").strip()

                    learning_data = json.loads(data_str)

                    domain_id = await conn.fetchval(
                        "SELECT id FROM domains WHERE name = $1", expert["department"]
                    )
                    if not domain_id:
                        domain_id = await conn.fetchval(
                            "INSERT INTO domains (name) VALUES ($1) RETURNING id",
                            expert["department"],
                        )

                    for insight in learning_data.get("insights", []):
                        # Сохраняем знание (по возможности с embedding — VERIFICATION §5)
                        content_kn = insight["content"]
                        meta_kn = json.dumps(
                            {
                                "expert": expert_name,
                                "cycle": "nightly_council_v2",
                                "self_criticism": learning_data.get("self_criticism", ""),
                            }
                        )
                        embedding = None
                        try:
                            from semantic_cache import get_embedding

                            embedding = await get_embedding(content_kn[:8000])
                        except Exception:
                            pass
                        if embedding is not None:
                            k_id = await conn.fetchval(
                                """
                                INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified, embedding)
                                VALUES ($1, $2, $3, $4, $5, $6::vector)
                                RETURNING id
                            """,
                                domain_id,
                                content_kn,
                                insight["confidence"],
                                meta_kn,
                                True,
                                str(embedding),
                            )
                        else:
                            k_id = await conn.fetchval(
                                """
                                INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified)
                                VALUES ($1, $2, $3, $4, $5)
                                RETURNING id
                            """,
                                domain_id,
                                content_kn,
                                insight["confidence"],
                                meta_kn,
                                True,
                            )

                        total_learned += 1

                        # Если уверенность высокая, запускаем Совет Экспертов
                        if insight["confidence"] >= 0.9:
                            await run_expert_council(conn, k_id, insight["content"], expert["id"])

                    await conn.execute(
                        "INSERT INTO expert_learning_logs (expert_id, topic, summary) VALUES ($1, $2, $3)",
                        expert["id"],
                        learning_data.get("topic", topic),
                        learning_data.get("summary", ""),
                    )

                    # Обновляем время последнего обучения для конкретного эксперта
                    await conn.execute(
                        "UPDATE experts SET last_learned_at = CURRENT_TIMESTAMP WHERE id = $1",
                        expert["id"],
                    )
                    learned_today += 1

                except Exception as e:
                    print(f"Error for {expert_name}: {e}")

            await asyncio.sleep(5)  # Увеличенная задержка

        # Итоговая статистика
        print(f"\n{'=' * 60}")
        print("📊 ИТОГИ ОБУЧЕНИЯ:")
        print(f"   Всего экспертов: {total_experts}")
        print(f"   Обучилось сегодня: {learned_today}")
        print(f"   Пропущено (уже обучались < 24ч): {skipped_recent}")
        print(f"   Новых знаний добавлено: {total_learned}")
        print(f"{'=' * 60}\n")

        if total_learned > 0:
            # Обновляем общее время обучения (для совместимости)
            await conn.execute(
                "UPDATE experts SET last_learned_at = CURRENT_TIMESTAMP WHERE last_learned_at IS NULL"
            )
            await sync_okrs(conn)

            # --- ФАЗА 4: LM JUDGE (ВЕРИФИКАЦИЯ) ---
            try:
                _log_step("⚖️ Running LM Judge...")
                subprocess.run(
                    [sys.executable, os.path.join(_APP_DIR, "evaluator.py")], cwd=_APP_DIR
                )
            except Exception as e:
                logger.warning("LM Judge phase failed: %s", e)

            # --- ФАЗА 5: CORPORATE IMMUNITY (СТРЕСС-ТЕСТ) ---
            try:
                _log_step("🛡️ Running Adversarial Critic...")
                subprocess.run(
                    [sys.executable, os.path.join(_APP_DIR, "adversarial_critic.py")], cwd=_APP_DIR
                )
            except Exception as e:
                logger.warning("Adversarial Critic phase failed: %s", e)

        # --- ФАЗА 6: CONTEXTUAL LEARNING (КОНТЕКСТНАЯ ПАМЯТЬ) ---
        _log_step("🎓 Running Contextual Learning...")
        try:
            from contextual_learner import run_contextual_learning_cycle

            await run_contextual_learning_cycle()
        except Exception as e:
            print(f"⚠️ Contextual Learning error: {e}")

        # --- ФАЗА 7: ENHANCED EXPERT EVOLUTION (АВТОМАТИЧЕСКАЯ ЭВОЛЮЦИЯ) ---
        _log_step("🧬 Running Autonomous Talent Management...")
        try:
            # Теперь эксперты сами решают, какие скиллы им нужны
            from expert_evolver import evolve_experts

            await evolve_experts()
        except Exception as e:
            print(f"⚠️ Talent Management error: {e}")

        # --- ФАЗА 7.5: ENHANCED EXPERT EVOLVER (метрики → эволюция/специализация/удаление) ---
        _log_step("🧬 Running Enhanced Expert Evolution cycle...")
        try:
            try:
                from enhanced_expert_evolver import run_enhanced_evolution_cycle
            except ImportError:
                from app.enhanced_expert_evolver import run_enhanced_evolution_cycle
            await run_enhanced_evolution_cycle()
            print("✅ Phase 7.5: Enhanced Expert Evolution completed.")
        except Exception as e:
            print(f"⚠️ Enhanced Expert Evolution error: {e}")

        # --- ФАЗА 10: ADAPTIVE LEARNING (АДАПТИВНОЕ ОБУЧЕНИЕ) ---
        _log_step("🎓 Running Adaptive Learning...")
        try:
            from adaptive_learner import run_adaptive_learning_cycle

            await run_adaptive_learning_cycle()
        except Exception as e:
            print(f"⚠️ Adaptive Learning error: {e}")

        # --- ФАЗА 8: AUTO-TRANSLATION (АВТОМАТИЧЕСКИЙ ПЕРЕВОД) ---
        _log_step("🌍 Running Auto-Translation...")
        try:
            from translator import run_auto_translation_cycle

            await run_auto_translation_cycle()
        except Exception as e:
            print(f"⚠️ Auto-Translation error: {e}")

        # --- ФАЗА 9: UPDATE CURSORRULES (ОБНОВЛЕНИЕ .CURSORRULES) ---
        _log_step("📝 Updating .cursorrules from database...")
        try:
            from cursorrules_generator import update_cursorrules_file

            await update_cursorrules_file()
        except Exception as e:
            print(f"⚠️ .cursorrules update error: {e}")

        # --- ФАЗА 10: DEBATE PROCESSING (ОБРАБОТКА ДЕБАТОВ) ---
        _log_step("💬 Processing debates and creating tasks...")
        try:
            from debate_processor import DebateProcessor

            processor = DebateProcessor()
            stats = await processor.process_new_debates()
            if stats["processed"] > 0:
                print(f"✅ Processed {stats['processed']} debates:")
                print(f"   Created {stats['tasks_created']} tasks")
                print(f"   Prioritized {stats['knowledge_prioritized']} knowledge nodes")
                print(f"   Sent {stats['notifications_sent']} notifications")
        except Exception as e:
            print(f"⚠️ Debate processing error: {e}")
            import traceback

            traceback.print_exc()

        # --- ФАЗА 11: APPLY ALL KNOWLEDGE (SINGULARITY 10.0) ---
        _log_step(
            "🧠 Applying knowledge (lessons → guidance, retrospectives → knowledge_nodes, insights → tasks)..."
        )
        try:
            import gc

            gc.collect()
            from pathlib import Path

            _app_dir = Path(__file__).resolve().parent
            _ko_root = _app_dir.parent
            if str(_ko_root) not in sys.path:
                sys.path.insert(0, str(_ko_root))
            from observability.knowledge_applicator import apply_all_knowledge_async

            results = await apply_all_knowledge_async()
            if any(results.values()):
                print(
                    f"✅ Knowledge applied: guidance={results.get('guidance_updated')}, knowledge_base={results.get('knowledge_base_updated')}, prompts_evolved={results.get('prompts_evolved')}, code_tasks={results.get('code_tasks_created')}"
                )
        except Exception as e:
            print(f"⚠️ Knowledge application error: {e}")
            import traceback

            traceback.print_exc()

        # --- ФАЗА 12: DASHBOARD DAILY IMPROVEMENT (SINGULARITY 10.0) ---
        _log_step("📊 Running dashboard improvement cycle...")
        try:
            import gc

            gc.collect()
            from dashboard_daily_improver import run_dashboard_improvement_cycle

            dash_result = await run_dashboard_improvement_cycle()
            if dash_result.get("tasks_created", 0) > 0:
                print(f"✅ Dashboard improvement: {dash_result['tasks_created']} tasks created")
        except Exception as e:
            print(f"⚠️ Dashboard improvement error: {e}")
            import traceback

            traceback.print_exc()

        # --- ФАЗА 13: AUTONOMOUS TESTS (Living Brain) ---
        _log_step("🧪 Running autonomous test phase...")
        try:
            import gc

            gc.collect()
            tests_dir = os.path.join(_KNOWLEDGE_OS_ROOT, "tests")
            if os.path.exists(tests_dir):
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "pytest",
                        "tests/test_json_fast_http_client.py",
                        "tests/test_rest_api.py",
                        "-v",
                        "--tb=no",
                        "-q",
                    ],
                    cwd=_KNOWLEDGE_OS_ROOT,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                passed = result.returncode == 0
                summary = (result.stdout or "")[-500:] + (result.stderr or "")[-300:]
                content_kn = f"Autonomous tests run at {datetime.now().isoformat()}: passed={passed}, returncode={result.returncode}\n\n{summary}"
                domain_id = await conn.fetchval(
                    "SELECT id FROM domains WHERE name = $1 LIMIT 1", "QA"
                ) or await conn.fetchval("SELECT id FROM domains LIMIT 1")
                embedding = None
                try:
                    from semantic_cache import get_embedding

                    embedding = await get_embedding(content_kn[:8000])
                except Exception:
                    pass
                if embedding is not None:
                    await conn.execute(
                        """
                        INSERT INTO knowledge_nodes (domain_id, content, confidence_score, source_ref, metadata, embedding)
                        VALUES ($1, $2, $3, $4, $5, $6::vector)
                    """,
                        domain_id or 1,
                        content_kn,
                        1.0 if passed else 0.5,
                        "autonomous_tests",
                        json.dumps({"passed": passed, "returncode": result.returncode}),
                        str(embedding),
                    )
                else:
                    await conn.execute(
                        """
                        INSERT INTO knowledge_nodes (domain_id, content, confidence_score, source_ref, metadata)
                        VALUES ($1, $2, $3, $4, $5)
                    """,
                        domain_id or 1,
                        content_kn,
                        1.0 if passed else 0.5,
                        "autonomous_tests",
                        json.dumps({"passed": passed, "returncode": result.returncode}),
                    )
                if not passed:
                    await conn.execute(
                        """
                        INSERT INTO tasks (title, description, status, priority, metadata)
                        VALUES ($1, $2, 'pending', 'high', $3::jsonb)
                        ON CONFLICT (title, COALESCE(project_context, 'default'))
                        WHERE status IN ('pending', 'in_progress')
                        DO NOTHING
                    """,
                        "🔧 Исправить падающие автотесты (Nightly Learner)",
                        content_kn[:2000],
                        json.dumps({"source": "nightly_learner", "assignee_hint": "QA"}),
                    )
                    print("⚠️ Tests failed, task created for QA")
                else:
                    print("✅ Autonomous tests passed")
        except Exception as e:
            logger.warning("Autonomous tests phase failed: %s", e)

        # --- ФАЗА 13.5: AUTONOMOUS TESTER (Self-Healing QA, Singularity 24.0) ---
        _log_step("🧪 Running Autonomous Tester (full suite + Anna healing)...")
        try:
            try:
                from autonomous_tester import AutonomousTester
            except ImportError:
                from app.autonomous_tester import AutonomousTester
            tester = AutonomousTester()
            await tester.run_cycle()
            print("✅ Phase 13.5: Autonomous Tester (Self-Healing QA) completed.")
        except Exception as e:
            print(f"⚠️ Autonomous Tester error: {e}")

        # --- ФАЗА 14: GIT DIFF → ЗАДАЧИ НА ГЕНЕРАЦИЮ ТЕСТОВ (Living Brain §6.1) ---
        _log_step("📝 Running git diff → test generation tasks...")
        try:
            repo_root = os.path.dirname(_KNOWLEDGE_OS_ROOT)
            if os.path.exists(os.path.join(repo_root, ".git")):
                r = subprocess.run(
                    ["git", "log", "--since=24 hours ago", "--name-only", "--pretty=format:"],
                    cwd=repo_root,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                changed = [
                    f.strip()
                    for f in (r.stdout or "").splitlines()
                    if f.strip() and f.strip().endswith(".py")
                ]
                changed = list(dict.fromkeys(changed))  # dedupe
                tests_dir_rel = "knowledge_os/tests" if repo_root != _KNOWLEDGE_OS_ROOT else "tests"
                created = 0
                for path in changed[:10]:
                    if "knowledge_os/app/" not in path and "knowledge_os/" not in path:
                        continue
                    mod = path.replace("knowledge_os/", "").replace(".py", "").replace("/", ".")
                    test_name = f"test_{mod.split('.')[-1]}.py"
                    if any(test_name in p for p in changed):
                        continue
                    test_path = os.path.join(repo_root, tests_dir_rel, test_name)
                    if os.path.exists(test_path):
                        continue
                    exists = await conn.fetchval(
                        "SELECT 1 FROM tasks WHERE metadata->>'module' = $1 AND status NOT IN ('completed','cancelled') AND created_at > NOW() - INTERVAL '7 days' LIMIT 1",
                        mod,
                    )
                    if exists:
                        continue
                    meta = json.dumps(
                        {"source": "nightly_learner", "assignee_hint": "QA", "module": mod}
                    )
                    await conn.execute(
                        """
                        INSERT INTO tasks (title, description, status, priority, metadata)
                        VALUES ($1, $2, 'pending', 'medium', $3::jsonb)
                    """,
                        f"🧪 Сгенерировать pytest для {mod}",
                        f"Модуль изменён за 24ч. Создать тесты в {tests_dir_rel}/{test_name}. Модуль: {path}",
                        meta,
                    )
                    created += 1
                    if created >= 3:
                        break
                if created > 0:
                    print(f"✅ Phase 14: {created} test generation task(s) created")
            else:
                logger.debug("Phase 14 skipped: no .git in repo root")
        except Exception as e:
            logger.debug("Phase 14 (git diff → test tasks) failed: %s", e)

        # --- ФАЗА 15: АВТО-ПРОФИЛИРОВАНИЕ (Living Brain §6.3, AUTO_PROFILING_GUIDE) ---
        # Запускаем раз в неделю (воскресенье) чтобы не замедлять каждый Nightly
        if datetime.now().weekday() == 6:  # 0=Mon, 6=Sun
            _log_step("📊 Running auto-profiling phase (cProfile)...")
            try:
                import cProfile
                import io
                import pstats

                try:
                    from app.json_fast import dumps, loads
                except ImportError:
                    try:
                        from json_fast import dumps, loads
                    except ImportError:
                        loads, dumps = __import__("json").loads, __import__("json").dumps
                prof = cProfile.Profile()
                prof.enable()
                for _ in range(500):
                    loads(dumps({"test": "value", "n": 42}))
                prof.disable()
                s = io.StringIO()
                pstats.Stats(prof, stream=s).sort_stats("cumulative").print_stats(15)
                report = s.getvalue()
                domain_id = await conn.fetchval(
                    "SELECT id FROM domains WHERE name = $1 LIMIT 1", "Performance"
                ) or await conn.fetchval("SELECT id FROM domains LIMIT 1")
                content = f"Auto-profiling at {datetime.now().isoformat()} (json_fast roundtrip x500)\n\n{report[:3000]}"
                embedding = None
                try:
                    from semantic_cache import get_embedding

                    embedding = await get_embedding(content[:8000])
                except Exception:
                    pass
                if embedding is not None:
                    await conn.execute(
                        """
                        INSERT INTO knowledge_nodes (domain_id, content, confidence_score, source_ref, metadata, embedding)
                        VALUES ($1, $2, 0.8, $3, $4, $5::vector)
                    """,
                        domain_id or 1,
                        content,
                        "auto_profiling",
                        json.dumps({"phase": 15, "workload": "json_roundtrip"}),
                        str(embedding),
                    )
                else:
                    await conn.execute(
                        """
                        INSERT INTO knowledge_nodes (domain_id, content, confidence_score, source_ref, metadata)
                        VALUES ($1, $2, 0.8, $3, $4)
                    """,
                        domain_id or 1,
                        content,
                        "auto_profiling",
                        json.dumps({"phase": 15, "workload": "json_roundtrip"}),
                    )
                print("✅ Phase 15: profiling result saved to knowledge_nodes")
            except Exception as e:
                logger.debug("Phase 15 (auto-profiling) failed: %s", e)

        # --- ФАЗА 16: ЗАДАЧА НА СИНХРОНИЗАЦИЮ ДОКУМЕНТАЦИИ (Living Organism §8, Татьяна) ---
        # При merge в main за 24ч — создать задачу для Technical Writer обновить MASTER_REFERENCE/docs
        _log_step("📄 Checking for documentation sync task...")
        try:
            repo_root = os.path.dirname(_KNOWLEDGE_OS_ROOT)
            if os.path.exists(os.path.join(repo_root, ".git")):
                r = subprocess.run(
                    ["git", "log", "--since=24 hours ago", "--merges", "--oneline"],
                    cwd=repo_root,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                merge_count = len([l for l in (r.stdout or "").strip().splitlines() if l.strip()])
                if merge_count > 0:
                    exists = await conn.fetchval("""
                        SELECT 1 FROM tasks
                        WHERE title LIKE '%Синхронизировать документацию%'
                        AND created_at > NOW() - INTERVAL '7 days'
                        AND status NOT IN ('completed', 'cancelled')
                        LIMIT 1
                    """)
                    if not exists:
                        meta = json.dumps(
                            {
                                "source": "nightly_learner",
                                "assignee_hint": "Technical Writer",
                                "phase": 16,
                            }
                        )
                        await conn.execute(
                            """
                            INSERT INTO tasks (title, description, status, priority, metadata)
                            VALUES ($1, $2, 'pending', 'low', $3::jsonb)
                        """,
                            "📝 Синхронизировать документацию с последними изменениями",
                            f"В main за 24ч было {merge_count} merge(ов). Проверить MASTER_REFERENCE, CHANGES_FROM_OTHER_CHATS и связанные доки (правило библии).",
                            meta,
                        )
                        print("✅ Phase 16: documentation sync task created")
        except Exception as e:
            logger.debug("Phase 16 (doc sync task) failed: %s", e)

        # --- ФАЗА 17: АВТООЧИСТКА СТАРЫХ ЗАДАЧ (completed > 30 дней, cancelled) ---
        _log_step("🗑️ Running tasks cleanup (completed >30 days, cancelled)...")
        try:
            deleted_completed = (
                await conn.fetchval("""
                WITH d AS (
                    DELETE FROM tasks
                    WHERE status = 'completed' AND updated_at < NOW() - INTERVAL '30 days'
                    RETURNING id
                )
                SELECT count(*)::int FROM d
            """)
                or 0
            )
            deleted_cancelled = (
                await conn.fetchval("""
                WITH d AS (DELETE FROM tasks WHERE status = 'cancelled' RETURNING id)
                SELECT count(*)::int FROM d
            """)
                or 0
            )
            if deleted_completed or deleted_cancelled:
                print(
                    f"✅ Phase 17: deleted {deleted_completed} old completed, {deleted_cancelled} cancelled"
                )
            else:
                print("✅ Phase 17: nothing to clean")
        except Exception as e:
            logger.debug("Phase 17 (tasks cleanup) failed: %s", e)

        # --- ФАЗА 17.5: СБРОС ЗАВИСШИХ ЗАДАЧ (in_progress > 4ч → failed, 1–4ч → pending) ---
        _log_step("🔄 Running reset stuck tasks...")
        try:
            _scripts_dir = os.path.join(_KNOWLEDGE_OS_ROOT, "scripts")
            _reset_script = os.path.join(_scripts_dir, "reset_stuck_tasks.py")
            if os.path.isfile(_reset_script):
                _proc = subprocess.run(
                    [sys.executable, _reset_script],
                    cwd=_KNOWLEDGE_OS_ROOT,
                    timeout=60,
                    capture_output=True,
                    text=True,
                    env={
                        **os.environ,
                        "PYTHONPATH": _KNOWLEDGE_OS_ROOT
                        + os.pathsep
                        + os.path.join(_KNOWLEDGE_OS_ROOT, "app"),
                    },
                )
                if _proc.returncode == 0 and _proc.stdout:
                    print(_proc.stdout.strip()[:400])
                print("✅ Phase 17.5: Reset stuck tasks completed.")
            else:
                logger.debug("Phase 17.5 skipped: reset_stuck_tasks.py not found")
        except Exception as e:
            print(f"⚠️ Reset stuck tasks error: {e}")

        # --- ФАЗА 18: SELF-DISTILLATION (SINGULARITY 13.0) ---
        _log_step("🧠 Running Recursive Self-Distillation cycle...")
        try:
            try:
                from distillation_engine import get_distillation_engine
            except ImportError:
                from app.distillation_engine import get_distillation_engine
            engine = get_distillation_engine()
            success = await engine.run_cycle()
            if success:
                print("✅ Phase 18: Self-Distillation cycle completed successfully")
            else:
                print("ℹ️ Phase 18: Self-Distillation cycle skipped (no new data)")
        except Exception as e:
            print(f"⚠️ Self-Distillation error: {e}")

        # --- ФАЗА 19: PROMOTION ENGINE (SHADOW PROMPT EVOLUTION) ---
        _log_step("🚀 Running Shadow Prompt Promotion cycle...")
        try:
            from promotion_engine import run_promotion_cycle

            await run_promotion_cycle()
            print("✅ Phase 19: Shadow Prompt Promotion cycle completed.")
        except Exception as e:
            print(f"⚠️ Shadow Prompt Promotion error: {e}")

        # --- ФАЗА 19.5: META-ARCHITECT SELF-EVOLUTION (SINGULARITY 10.0) ---
        _log_step("🧬 Running MetaArchitect Self-Evolution (hot spots → mutations → shadow)...")
        try:
            try:
                from meta_architect import MetaArchitect
            except ImportError:
                from app.meta_architect import MetaArchitect
            architect = MetaArchitect()
            await architect.self_evolution_cycle()
            print("✅ Phase 19.5: MetaArchitect Self-Evolution completed.")
        except Exception as e:
            print(f"⚠️ MetaArchitect Self-Evolution error: {e}")

        # --- ФАЗА 20: WISDOM SYNTHESIS (SINGULARITY 20.0) ---
        _log_step("🏛️ Running Wisdom Synthesis (Meta-Strategies & Tacit Knowledge)...")
        try:
            # 0. Self-Healing Infrastructure
            try:
                from self_healing_tunnels import check_and_heal_tunnels

                await check_and_heal_tunnels()
            except Exception as she:
                print(f"⚠️ Self-Healing error: {she}")

            # 1. Update Style Profiles (Tacit Knowledge)
            from tacit_knowledge_miner import update_style_profiles

            await update_style_profiles()

            # 2. Mentorship Audit
            from mentorship_engine import run_mentorship_cycle

            await run_mentorship_cycle()

            # 3. SOP Generation
            from sop_generator import run_sop_cycle

            await run_sop_cycle()

            # 4. Adversarial Red Teaming (SOP & Knowledge verification)
            from adversarial_critic import run_adversarial_cycle

            await run_adversarial_cycle(limit=10)

            # 5. Synthesize Meta-Wisdom
            from meta_synthesizer import synthesize_wisdom

            await synthesize_wisdom()
            print("✅ Phase 20: Wisdom Synthesis completed.")
        except Exception as e:
            print(f"⚠️ Wisdom Synthesis error: {e}")

        # --- ФАЗА 20.5: ENHANCED IMMUNITY (один цикл за ночь) ---
        _log_step("🛡️ Running Enhanced Immunity cycle...")
        try:
            try:
                from enhanced_immunity import run_enhanced_immunity_cycle
            except ImportError:
                from app.enhanced_immunity import run_enhanced_immunity_cycle
            await run_enhanced_immunity_cycle()
            print("✅ Phase 20.5: Enhanced Immunity completed.")
        except Exception as e:
            print(f"⚠️ Enhanced Immunity error: {e}")

        # --- ФАЗА 20.6: STRATEGIC BOARD (одно заседание за ночь) ---
        _log_step("🏛️ Running Strategic Board meeting...")
        try:
            try:
                from strategic_board import run_board_meeting
            except ImportError:
                from app.strategic_board import run_board_meeting
            await run_board_meeting()
            print("✅ Phase 20.6: Strategic Board meeting completed.")
        except Exception as e:
            print(f"⚠️ Strategic Board error: {e}")

        # --- ФАЗА 20.7: SYNC EMPLOYEES (employees.json → БД) ---
        _log_step("👥 Running Employees sync (nightly)...")
        try:
            try:
                from employees_sync_daemon import trigger_employees_sync
            except ImportError:
                from app.employees_sync_daemon import trigger_employees_sync
            await trigger_employees_sync(reason="nightly")
            print("✅ Phase 20.7: Employees sync completed.")
        except Exception as e:
            print(f"⚠️ Employees sync error: {e}")

        # --- ФАЗА 20.8: KNOWLEDGE NODES TTL CLEANUP ---
        _log_step("🧹 Running knowledge_nodes TTL cleanup...")
        try:
            rows = await conn.fetch("SELECT * FROM cleanup_knowledge_nodes(30, 180, 0.5)")
            for row in rows:
                print(f"✅ Phase 20.8: Deleted {row['deleted_count']} nodes ({row['reason']})")
            if not rows:
                print("✅ Phase 20.8: knowledge_nodes TTL cleanup — nothing to delete.")
        except Exception as e:
            print(f"⚠️ knowledge_nodes TTL cleanup error: {e}")

        await pool.release(conn)
        await pool.close()
        _log_step(f"[{datetime.now()}] Total cycle with Council Review finished.")


if __name__ == "__main__":
    asyncio.run(nightly_learning_cycle())
