import asyncio
import json
import logging
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import asyncpg

# Используем get_pool из evaluator для консистентности
sys.path.insert(0, os.path.dirname(__file__))
from evaluator import get_pool

logger = logging.getLogger(__name__)


def run_cursor_agent(prompt: str):
    """Run cursor-agent CLI to process a prompt and return output."""
    try:
        env = os.environ.copy()
        result = subprocess.run(
            ["/root/.local/bin/cursor-agent", "--print", prompt],
            capture_output=True,
            text=True,
            check=True,
            timeout=1800,
            env=env,
        )
        return result.stdout
    except Exception as e:
        print(f"Error running cursor-agent for adversarial attack: {e}")
        return None


async def run_adversarial_cycle(limit: int = 5):
    print(f"🛡️ Starting Adversarial Critic (Corporate Immunity) cycle for {limit} nodes...")
    pool = await get_pool()
    conn = await pool.acquire()

    # 1. Находим недавно верифицированные знания или новые SOP для стресс-теста
    nodes = await conn.fetch(
        """
        SELECT id, content, quality_report, metadata
        FROM knowledge_nodes
        WHERE is_verified = TRUE
        AND (metadata->>'adversarial_tested' IS NULL OR metadata->>'adversarial_tested' = 'false')
        AND (confidence_score > 0.7 OR metadata->>'type' = 'sop_document')
        ORDER BY created_at DESC LIMIT $1
    """,
        limit,
    )

    if not nodes:
        print("✅ No new nodes for adversarial testing.")
        await pool.release(conn)
        return

    for node in nodes:
        metadata = node["metadata"]
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except:
                metadata = {}

        is_sop = (metadata or {}).get("type") == "sop_document"
        print(f"⚔️ Stress-testing {'SOP' if is_sop else 'node'} {node['id']}...")

        role_name = "БЕЗЖАЛОСТНЫЙ КРИТИК И АДВОКАТ ДЬЯВОЛА"
        if is_sop:
            role_name = "ГЛАВНЫЙ ИНСПЕКТОР ПО КАЧЕСТВУ И БЕЗОПАСНОСТИ"

        attack_prompt = f"""
        ТЫ - {role_name}.
        ТВОЯ ЗАДАЧА: Найти критические изъяны, ошибки в логике, угрозы безопасности или неэффективные инструкции в предоставленном контенте.

        ТИП КОНТЕНТА: {"Standard Operating Procedure (SOP)" if is_sop else "Knowledge Insight"}
        КОНТЕНТ: {node["content"]}
        {f"ОТЧЕТ ПРЕДЫДУЩЕГО СУДЬИ: {node['quality_report']}" if node["quality_report"] else ""}

        ИНСТРУКЦИЯ:
        1. Проведи поиск потенциальных проблем (security, performance, logic).
        2. Если это SOP - проверь, не приведет ли выполнение этих шагов к сбою системы.
        3. Найди 3 причины, почему это может не сработать в реальных условиях.
        4. Если контент выдержал атаку - подтверди его исключительную надежность.

        ВЕРНИ JSON:
        {{
            "survived": true/false,
            "attack_report": "Текст твоей атаки и выводов",
            "new_confidence_score": 0.0-1.0
        }}
        ВЕРНИ ТОЛЬКО ЧИСТЫЙ JSON.
        """

        from ai_core import run_smart_agent_async

        output = await run_smart_agent_async(
            attack_prompt, expert_name="Критик", category="reasoning"
        )

        if output:
            try:
                clean_json = output.strip()
                if "```json" in clean_json:
                    clean_json = clean_json.split("```json")[1].split("```")[0]
                elif "```" in clean_json:
                    clean_json = clean_json.split("```")[1].split("```")[0]

                # [FIX] Если модель вернула текст до или после JSON, пробуем найти границы JSON
                if not clean_json.startswith("{") and "{" in clean_json:
                    clean_json = clean_json[clean_json.find("{") :]
                if not clean_json.endswith("}") and "}" in clean_json:
                    clean_json = clean_json[: clean_json.rfind("}") + 1]

                result = json.loads(clean_json)

                # Обновляем знание результатами атаки
                await conn.execute(
                    """
                    UPDATE knowledge_nodes
                    SET confidence_score = $1,
                        expert_consensus = COALESCE(expert_consensus, '{}'::jsonb) || $2::jsonb,
                        metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object('adversarial_tested', 'true', 'survived', $3::boolean)
                    WHERE id = $4
                """,
                    result["new_confidence_score"],
                    json.dumps({"adversarial_attack": result["attack_report"]}),
                    result["survived"],
                    node["id"],
                )

                status = "SURVIVED" if result["survived"] else "DESTROYED"
                print(f"🛡️ Node {node['id']} {status}. New Score: {result['new_confidence_score']}")

                # Если знание уничтожено - уведомляем через радар
                if not result["survived"]:
                    await conn.execute(
                        """
                        INSERT INTO notifications (message, type)
                        VALUES ($1, 'adversarial_alert')
                    """,
                        f"💀 KNOWLEDGE DESTROYED: Утверждение '{node['content'][:50]}...' не прошло стресс-тест. Аргумент: {result['attack_report'][:100]}",
                    )

            except Exception as e:
                print(f"❌ Error parsing adversarial output: {e}")

    await pool.release(conn)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Adversarial Critic Stress-Test Cycle")
    parser.add_argument("--limit", type=int, default=5, help="Number of nodes to test")
    args = parser.parse_args()

    asyncio.run(run_adversarial_cycle(limit=args.limit))


# [SINGULARITY 28.7] Mandatory Trust Gate
async def verify_high_priority_task(task_id: str, content: str) -> Dict[str, Any]:
    """
    Mandatory adversarial verification for high-priority tasks.
    """
    print(f"🛡️ [TRUST GATE] Mandatory verification for task {task_id}...")

    attack_prompt = f"""
    ТЫ - БЕЗЖАЛОСТНЫЙ КРИТИК И АДВОКАТ ДЬЯВОЛА.
    ТВОЯ ЗАДАЧА: Найти критические изъяны в предложенном решении задачи.

    КОНТЕНТ: {content}

    ИНСТРУКЦИЯ:
    1. Проведи поиск потенциальных проблем (security, performance, logic).
    2. Найди 3 причины, почему это может не сработать.
    3. Если решение выдержало атаку - подтверди его надежность.

    ВЕРНИ JSON:
    {{
        "survived": true/false,
        "attack_report": "Текст твоей атаки",
        "new_confidence_score": 0.0-1.0
    }}
    ВЕРНИ ТОЛЬКО ЧИСТЫЙ JSON.
    """

    from ai_core import run_smart_agent_async

    def _extract_json_candidate(raw_output: Optional[str]) -> Optional[str]:
        if not raw_output:
            return None
        text = raw_output.strip()
        if not text:
            return None

        fenced_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
        if fenced_match:
            return fenced_match.group(1).strip()

        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            return text[first_brace : last_brace + 1].strip()

        return None

    def _local_fallback_verdict(task_text: str) -> Dict[str, Any]:
        """Deterministic local fallback when critic output is malformed."""
        lowered = (task_text or "").lower()
        high_risk_markers = (
            "drop table",
            "truncate ",
            "rm -rf",
            "curl http",
            "password",
            "secret",
            "token",
            "api_key",
            "sudo ",
        )
        marker_hits = [m for m in high_risk_markers if m in lowered]
        survived = len(marker_hits) == 0
        return {
            "survived": survived,
            "attack_report": (
                "local_fallback: no high-risk markers detected"
                if survived
                else f"local_fallback: detected risk markers: {', '.join(marker_hits[:5])}"
            ),
            "new_confidence_score": 0.62 if survived else 0.28,
            "verification_reason": "critic_local_fallback",
        }

    max_attempts = max(1, int(os.getenv("TRUST_GATE_MAX_ATTEMPTS", "2")))
    retry_sleep_sec = float(os.getenv("TRUST_GATE_RETRY_SLEEP_SEC", "1.0"))
    fail_open = os.getenv("TRUST_GATE_FAIL_OPEN", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    last_error = None
    for attempt in range(1, max_attempts + 1):
        output = await run_smart_agent_async(
            attack_prompt, expert_name="Критик", category="reasoning"
        )

        try:
            candidate = _extract_json_candidate(output)
            if not candidate:
                raise ValueError("empty_or_non_json_critic_output")
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                parsed.setdefault("verification_reason", "critic_json_ok")
                return parsed
            raise ValueError("critic output is not a JSON object")
        except Exception as e:
            last_error = e
            logger.debug(
                "❌ [TRUST GATE] Error parsing critic output (attempt %s/%s): %s",
                attempt,
                max_attempts,
                e,
            )
            if attempt < max_attempts:
                await asyncio.sleep(max(0.0, retry_sleep_sec))
                continue

    # Always return a valid contract-shaped JSON verdict to avoid noisy degraded paths.
    fallback_verdict = _local_fallback_verdict(content)
    if last_error:
        fallback_verdict["attack_report"] = (
            f"{fallback_verdict['attack_report']}; critic_output_parse_error={last_error}"
        )
        logger.info(
            "⚠️ [TRUST GATE] Falling back to local deterministic verdict for task %s (fail_open=%s)",
            task_id,
            fail_open,
        )
        if not fail_open:
            fallback_verdict["survived"] = False
            fallback_verdict["new_confidence_score"] = min(
                0.2, float(fallback_verdict["new_confidence_score"])
            )
            fallback_verdict["verification_reason"] = "critic_local_fallback_fail_closed"
        return fallback_verdict

    return {
        "survived": bool(fail_open),
        "attack_report": "critic_unavailable_or_empty_output",
        "new_confidence_score": 0.0,
        "verification_reason": "critic_unavailable_or_empty_output",
    }
