"""
Enhanced Immunity System with Auto-Fixing
Расширенная система иммунитета с автоматическим исправлением знаний
"""

import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import asyncpg

# Используем get_pool из evaluator для консистентности
sys.path.insert(0, os.path.dirname(__file__))
from evaluator import get_pool
from resource_manager import acquire_resource_lock


def run_cursor_agent(prompt: str, timeout: int = 600):
    """Запуск Cursor Agent для генерации контента"""
    try:
        env = os.environ.copy()
        result = subprocess.run(
            ["/root/.local/bin/cursor-agent", "--print", prompt],
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout,
            env=env,
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"Agent error: {e}")
        return None


async def identify_weak_knowledge(conn: asyncpg.Connection) -> List[Dict]:
    """Идентификация слабых знаний для исправления"""
    # Критерии слабых знаний:
    # 1. Низкий confidence_score (< 0.5)
    # 2. Не прошли adversarial testing (survived = false)
    # 3. Низкое использование (usage_count = 0) и старые (> 7 дней)
    # 4. Противоречия с другими знаниями

    weak_nodes = await conn.fetch("""
        SELECT id, content, confidence_score, usage_count, created_at, metadata, domain_id
        FROM knowledge_nodes
        WHERE (
            -- Низкий confidence_score
            confidence_score < 0.5
            OR
            -- Не прошли adversarial testing
            (metadata->>'survived' = 'false' AND metadata->>'adversarial_tested' = 'true')
            OR
            -- Низкое использование и старые
            (usage_count = 0 AND created_at < NOW() - INTERVAL '7 days' AND confidence_score < 0.7)
        )
        AND (metadata->>'auto_fixed' IS NULL OR metadata->>'auto_fixed' = 'false')
        AND is_verified = FALSE  -- Не трогаем верифицированные
        ORDER BY confidence_score ASC, usage_count ASC
        LIMIT 10
    """)

    return [dict(node) for node in weak_nodes]


async def regenerate_knowledge(
    conn: asyncpg.Connection,
    node_id: str,
    original_content: str,
    confidence_score: float,
    domain_id: str,
) -> Optional[str]:
    """Регенерация знания с улучшением"""
    print(f"🔄 Regenerating knowledge node {node_id}...")

    # Получаем контекст из домена
    domain_name = await conn.fetchval("SELECT name FROM domains WHERE id = $1", domain_id)

    # Получаем похожие успешные знания из того же домена
    similar_successful = await conn.fetch(
        """
        SELECT content, confidence_score
        FROM knowledge_nodes
        WHERE domain_id = $1
        AND confidence_score > 0.8
        AND usage_count > 5
        AND id != $2
        ORDER BY confidence_score DESC, usage_count DESC
        LIMIT 3
    """,
        domain_id,
        node_id,
    )

    examples = "\n".join([f"- {ex['content'][:200]}" for ex in similar_successful])

    # Промпт для регенерации
    regeneration_prompt = f"""
    ТЫ - ЭКСПЕРТ ПО УЛУЧШЕНИЮ ЗНАНИЙ.

    ЗАДАЧА: Улучши и исправь следующее знание, сделав его более точным, полезным и достоверным.

    ОРИГИНАЛЬНОЕ ЗНАНИЕ (confidence: {confidence_score:.2f}):
    {original_content}

    ПРИМЕРЫ УСПЕШНЫХ ЗНАНИЙ ИЗ ДОМЕНА "{domain_name}":
    {examples}

    ИНСТРУКЦИИ:
    1. Сохрани основную идею, но улучши формулировку
    2. Убери неточности и галлюцинации
    3. Сделай знание более конкретным и полезным
    4. Используй стиль из примеров успешных знаний
    5. Если знание полностью неверно - верни NULL

    ВЕРНИ ТОЛЬКО УЛУЧШЕННОЕ ЗНАНИЕ БЕЗ ДОПОЛНИТЕЛЬНЫХ КОММЕНТАРИЕВ.
    """

    regenerated_content = run_cursor_agent(regeneration_prompt)

    if not regenerated_content or len(regenerated_content) < 20:
        print(f"❌ Failed to regenerate knowledge {node_id}")
        return None

    # Очистка от markdown
    if "```" in regenerated_content:
        regenerated_content = regenerated_content.split("```")[-1].split("```")[0].strip()

    return regenerated_content


async def auto_fix_weak_knowledge(conn: asyncpg.Connection):
    """Автоматическое исправление слабых знаний"""
    print("🛡️ Phase 1: Identifying weak knowledge...")
    weak_nodes = await identify_weak_knowledge(conn)

    if not weak_nodes:
        print("✅ No weak knowledge found.")
        return

    print(f"🔍 Found {len(weak_nodes)} weak knowledge nodes")

    fixed_count = 0
    deleted_count = 0

    for node in weak_nodes:
        node_id = node["id"]
        original_content = node["content"]
        confidence_score = node["confidence_score"]
        domain_id = node["domain_id"]

        # Если confidence слишком низкий (< 0.3) и не использовалось - удаляем
        if confidence_score < 0.3 and node["usage_count"] == 0:
            print(f"🗑️ Deleting very weak knowledge {node_id} (confidence: {confidence_score:.2f})")
            await conn.execute("DELETE FROM knowledge_nodes WHERE id = $1", node_id)
            deleted_count += 1
            continue

        # Пытаемся регенерировать
        regenerated = await regenerate_knowledge(
            conn, node_id, original_content, confidence_score, domain_id
        )

        if regenerated:
            # Получаем новый эмбеддинг
            from enhanced_search import get_embedding

            new_embedding = await get_embedding(regenerated)

            # Обновляем знание
            await conn.execute(
                """
                UPDATE knowledge_nodes
                SET content = $1,
                    embedding = $2::vector,
                    confidence_score = LEAST(confidence_score + 0.2, 0.9),  -- Повышаем confidence
                    metadata = metadata || jsonb_build_object(
                        'auto_fixed', 'true',
                        'auto_fixed_at', NOW()::text,
                        'original_content', $3,
                        'fix_reason', 'low_confidence'
                    ),
                    updated_at = NOW()
                WHERE id = $4
            """,
                regenerated,
                str(new_embedding),
                original_content,
                node_id,
            )

            print(
                f"✅ Fixed knowledge {node_id}: confidence {confidence_score:.2f} → {min(confidence_score + 0.2, 0.9):.2f}"
            )
            fixed_count += 1
        else:
            # Если не удалось регенерировать - помечаем для ручной проверки
            await conn.execute(
                """
                UPDATE knowledge_nodes
                SET metadata = metadata || jsonb_build_object(
                    'needs_manual_review', 'true',
                    'auto_fix_failed', 'true'
                )
                WHERE id = $1
            """,
                node_id,
            )
            print(f"⚠️ Could not auto-fix {node_id}, marked for manual review")

    print(f"✅ Auto-fix completed: {fixed_count} fixed, {deleted_count} deleted")


async def run_adversarial_testing_with_auto_fix(conn: asyncpg.Connection):
    """Adversarial testing с автоматическим исправлением"""
    print("⚔️ Phase 2: Adversarial testing with auto-fix...")

    # Находим знания для тестирования
    nodes = await conn.fetch("""
        SELECT id, content, confidence_score, metadata
        FROM knowledge_nodes
        WHERE is_verified = TRUE
        AND (metadata->>'adversarial_tested' IS NULL OR metadata->>'adversarial_tested' = 'false')
        AND confidence_score > 0.7
        ORDER BY created_at DESC
        LIMIT 5
    """)

    if not nodes:
        print("✅ No nodes for adversarial testing.")
        return

    for node in nodes:
        print(f"⚔️ Stress-testing node {node['id']}...")

        attack_prompt = f"""
        ТЫ - БЕЗЖАЛОСТНЫЙ КРИТИК И АДВОКАТ ДЬЯВОЛА.
        ТВОЯ ЗАДАЧА: Уничтожить это утверждение, найти в нем ложь, галлюцинацию или критическую ошибку.

        УТВЕРЖДЕНИЕ: {node["content"]}

        ИНСТРУКЦИЯ:
        1. Проведи поиск альтернативных точек зрения.
        2. Найди логические противоречия.
        3. Если знание ошибочно - аргументируй почему.
        4. Если знание выдержало атаку - подтверди его стойкость.

        ВЕРНИ JSON:
        {{
            "survived": true/false,
            "attack_report": "Текст твоей атаки и выводов",
            "new_confidence_score": 0.0-1.0,
            "suggested_fix": "Предложение по исправлению (если survived=false)"
        }}
        """

        output = run_cursor_agent(attack_prompt)

        if output:
            try:
                # Парсинг JSON
                clean_json = output.strip()
                if "```json" in clean_json:
                    clean_json = clean_json.split("```json")[1].split("```")[0]
                elif "```" in clean_json:
                    clean_json = clean_json.split("```")[1].split("```")[0]
                
                # [FIX] Если модель вернула текст до или после JSON, пробуем найти границы JSON
                if not clean_json.startswith("{") and "{" in clean_json:
                    clean_json = clean_json[clean_json.find("{"):]
                if not clean_json.endswith("}") and "}" in clean_json:
                    clean_json = clean_json[:clean_json.rfind("}")+1]

                result = json.loads(clean_json)

                # Обновляем знание
                await conn.execute(
                    """
                    UPDATE knowledge_nodes
                    SET confidence_score = $1,
                        metadata = metadata || jsonb_build_object(
                            'adversarial_tested', 'true',
                            'survived', $2::boolean,
                            'adversarial_attack', $3
                        )
                    WHERE id = $4
                """,
                    result["new_confidence_score"],
                    result["survived"],
                    result["attack_report"],
                    node["id"],
                )

                status = "✅ SURVIVED" if result["survived"] else "💀 DESTROYED"
                print(
                    f"🛡️ Node {node['id']} {status}. New Score: {result['new_confidence_score']:.2f}"
                )

                # Если не выдержало - пытаемся исправить
                if not result["survived"] and result.get("suggested_fix"):
                    print(f"🔧 Attempting to fix destroyed knowledge {node['id']}...")

                    # Используем предложенное исправление
                    fixed_content = result["suggested_fix"]

                    # Получаем новый эмбеддинг
                    from enhanced_search import get_embedding

                    new_embedding = await get_embedding(fixed_content)

                    # Обновляем знание
                    await conn.execute(
                        """
                        UPDATE knowledge_nodes
                        SET content = $1,
                            embedding = $2::vector,
                            confidence_score = $3,
                            metadata = metadata || jsonb_build_object(
                                'auto_fixed', 'true',
                                'auto_fixed_at', NOW()::text,
                                'fix_reason', 'adversarial_destroyed',
                                'original_content', $4
                            ),
                            updated_at = NOW()
                        WHERE id = $5
                    """,
                        fixed_content,
                        str(new_embedding),
                        min(result["new_confidence_score"] + 0.3, 0.9),
                        node["content"],
                        node["id"],
                    )

                    print(f"✅ Auto-fixed knowledge {node['id']} after adversarial attack")

            except Exception as e:
                print(f"❌ Error parsing adversarial output: {e}")


async def cleanup_outdated_knowledge(conn: asyncpg.Connection):
    """Очистка устаревших знаний"""
    print("🧹 Phase 3: Cleaning up outdated knowledge...")

    # Находим устаревшие знания
    outdated = await conn.fetch("""
        SELECT id, content, created_at, usage_count, confidence_score
        FROM knowledge_nodes
        WHERE (
            -- Не использовались > 60 дней
            (usage_count = 0 AND created_at < NOW() - INTERVAL '60 days')
            OR
            -- Очень низкий confidence и старые
            (confidence_score < 0.3 AND created_at < NOW() - INTERVAL '30 days')
            OR
            -- Помечены как устаревшие
            (metadata->>'outdated' = 'true')
        )
        AND is_verified = FALSE
        AND (metadata->>'source' != 'cross_domain_linker')  -- Не трогаем гипотезы
        LIMIT 20
    """)

    if not outdated:
        print("✅ No outdated knowledge found.")
        return

    node_ids = [n["id"] for n in outdated]
    print(f"🗑️ Deleting {len(node_ids)} outdated knowledge nodes...")

    await conn.execute("DELETE FROM knowledge_nodes WHERE id = ANY($1)", node_ids)
    print(f"✅ Deleted {len(node_ids)} outdated nodes")


async def run_enhanced_immunity_cycle():
    """Основной цикл расширенной системы иммунитета"""
    async with acquire_resource_lock("enhanced_immunity"):
        print(f"[{datetime.now()}] 🛡️ ENHANCED IMMUNITY SYSTEM v3.1 starting...")
        pool = await get_pool()
        conn = await pool.acquire()

        try:
            # Фаза 1: Автоматическое исправление слабых знаний
            await auto_fix_weak_knowledge(conn)

            # Фаза 2: Adversarial testing с автоисправлением
            await run_adversarial_testing_with_auto_fix(conn)

            # Фаза 3: Очистка устаревших знаний
            await cleanup_outdated_knowledge(conn)

            print(f"[{datetime.now()}] ✅ Enhanced Immunity cycle completed.")

        finally:
            try:
                await pool.release(conn)
            except:
                pass
            try:
                await pool.close()
            except:
                pass


if __name__ == "__main__":
    asyncio.run(run_enhanced_immunity_cycle())
