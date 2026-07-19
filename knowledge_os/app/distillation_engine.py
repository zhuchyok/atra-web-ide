# knowledge_os/app/distillation_engine.py
"""
[SINGULARITY 21.0] Knowledge Distillation Engine.
Compresses raw knowledge nodes into high-density "Wisdom Adapters" (LoRA-ready)
using Victoria-Wisdom-30b as the teacher model.
"""

import asyncio
import json
import logging
import os
from datetime import datetime

import asyncpg

logger = logging.getLogger(__name__)

DB_URL = os.getenv(
    "POSTGRES_DIRECT_URL",
    os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os"),
)
DEFAULT_DISTILLATION_BATCH_SIZE = 40
MAX_DISTILL_RETRIES = int(os.getenv("DISTILL_MAX_RETRIES", "3"))
RETRY_BASE_SECONDS = int(os.getenv("DISTILL_RETRY_BASE_SECONDS", "300"))


class KnowledgeDistiller:
    def __init__(self):
        self.teacher_model = os.getenv("DISTILL_TEACHER_MODEL", "phi3.5:3.8b")
        self.teacher_fallback_model = os.getenv(
            "DISTILL_TEACHER_FALLBACK_MODEL", "phi3.5:3.8b-stable"
        )
        self.strict_json_schema = os.getenv("DISTILL_STRICT_JSON_SCHEMA", "true").lower() in (
            "1",
            "true",
            "yes",
            "on",
        )

    def _ollama_response_format(self):
        """Return Ollama response format: strict schema or plain json."""
        if not self.strict_json_schema:
            return "json"
        return {
            "type": "object",
            "properties": {
                "wisdom_summary": {"type": "string"},
                "instruction": {"type": "string"},
                "category": {"type": "string"},
            },
            "required": ["wisdom_summary", "instruction", "category"],
            "additionalProperties": False,
        }

    async def _get_elastic_batch_size(self) -> int:
        """
        [SINGULARITY 30.6] Elastic Batch: Динамический расчет размера батча на основе RAM.
        [SINGULARITY 30.7] Throttled to 30 max to prevent DB write-lock contention.
        [SINGULARITY 31.0] Quantum Leap: Increased to 50 when using DuckDB accelerator.
        """
        forced = os.getenv("DISTILL_FORCE_BATCH_SIZE")
        if forced:
            try:
                forced_size = max(1, int(forced))
                logger.info(f"📌 [ELASTIC-BATCH] Forced batch size via env: {forced_size}")
                return forced_size
            except Exception:
                logger.warning(f"⚠️ [ELASTIC-BATCH] Invalid DISTILL_FORCE_BATCH_SIZE={forced}")

        try:
            from resource_monitor import get_resource_monitor

            rm = get_resource_monitor()
            res = await rm.get_system_resources()
            avail_gb = res.get("ram", {}).get("available_gb", 8)

            # Логика масштабирования (DuckDB Accelerated):
            if avail_gb > 32:
                batch_size = 50
            elif avail_gb > 10:
                batch_size = 40
            else:
                batch_size = DEFAULT_DISTILLATION_BATCH_SIZE

            logger.info(
                f"📊 [ELASTIC-BATCH] Available RAM: {avail_gb:.1f}GB. Batch size set to {batch_size} (v31.0 DuckDB)"
            )
            return batch_size
        except Exception as e:
            logger.warning(f"⚠️ [ELASTIC-BATCH] Failed to calculate batch size: {e}")
            return DEFAULT_DISTILLATION_BATCH_SIZE

    async def get_relevant_examples(self, query: str, category: str = "coding") -> str:
        """
        [SINGULARITY 21.5] Получает релевантные примеры (few-shot) из дистиллированных знаний.
        """
        try:
            # [FIX] Используем внутренний импорт, чтобы избежать циклической зависимости
            import asyncpg

            conn = await asyncpg.connect(DB_URL)
            # Ищем дистиллированные знания по категории
            rows = await conn.fetch(
                """
                SELECT metadata->>'wisdom_summary' as summary,
                       metadata->>'instruction' as instruction
                FROM knowledge_nodes
                WHERE metadata->>'distilled' = 'true'
                AND (metadata->>'category' = $1 OR $1 = 'coding')
                ORDER BY confidence_score DESC
                LIMIT 3
            """,
                category,
            )
            await conn.close()

            if not rows:
                return ""

            examples = "### РЕЛЕВАНТНЫЕ ПРИМЕРЫ (FEW-SHOT):\n"
            for row in rows:
                if row["summary"] and row["instruction"]:
                    examples += f"- СУТЬ: {row['summary']}\n  ИНСТРУКЦИЯ: {row['instruction']}\n"
            return examples
        except Exception as e:
            logger.warning(f"⚠️ [DISTILLER] Ошибка получения примеров: {e}")
            return ""

    async def _call_teacher_direct(self, prompt: str) -> str:
        """
        [SINGULARITY 31.10] Direct call to Ollama for distillation.
        Bypasses complex ai_core orchestration for maximum speed.
        """
        import httpx

        cloud_only = os.getenv("DISTILL_CLOUD_ONLY", "false").lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        openrouter_key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
        if openrouter_key:
            openrouter_model = os.getenv(
                "DISTILL_CLOUD_MODEL",
                os.getenv(
                    "OPENROUTER_CODING_MODEL",
                    os.getenv("OPENROUTER_FALLBACK_MODEL", "qwen/qwen-2.5-coder-32b-instruct:free"),
                ),
            )
            try:
                async with httpx.AsyncClient(timeout=90.0) as client:
                    resp = await client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {openrouter_key}",
                            "HTTP-Referer": os.getenv(
                                "OPENROUTER_HTTP_REFERER",
                                "https://github.com/atra-web-ide",
                            ),
                            "X-Title": os.getenv("OPENROUTER_APP_TITLE", "ATRA Web IDE"),
                        },
                        json={
                            "model": openrouter_model,
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": 0.1,
                        },
                    )
                if resp.status_code == 200:
                    text = (resp.json().get("choices", [{}])[0].get("message", {}) or {}).get(
                        "content", ""
                    ) or ""
                    if text.strip():
                        logger.info(
                            "☁️ [DISTILL-CLOUD] OpenRouter response received (%s)", openrouter_model
                        )
                        return text
                logger.warning(
                    "⚠️ [DISTILL-CLOUD] OpenRouter error %s: %s",
                    resp.status_code,
                    resp.text[:200],
                )
                if cloud_only:
                    return ""
            except Exception as cloud_err:
                logger.warning("⚠️ [DISTILL-CLOUD] OpenRouter request failed: %s", cloud_err)
                if cloud_only:
                    return ""

        url = os.getenv("OLLAMA_API_URL", "http://host.docker.internal:11434") + "/api/generate"

        teacher_timeout = float(os.getenv("DISTILL_TEACHER_TIMEOUT_SEC", "180"))
        try:
            async with httpx.AsyncClient(timeout=teacher_timeout) as client:
                response = await client.post(
                    url,
                    json={
                        "model": self.teacher_model,
                        "prompt": prompt,
                        "stream": False,
                        "format": self._ollama_response_format(),
                        "keep_alive": "10m",
                        "options": {"temperature": 0.1, "num_predict": 512},
                    },
                )
                if response.status_code == 200:
                    return response.json().get("response", "")
                if (
                    response.status_code == 404
                    and self.teacher_model != self.teacher_fallback_model
                ):
                    logger.warning(
                        f"⚠️ [OLLAMA-DIRECT] Teacher model {self.teacher_model} missing, fallback to {self.teacher_fallback_model}"
                    )
                    fallback_resp = await client.post(
                        url,
                        json={
                            "model": self.teacher_fallback_model,
                            "prompt": prompt,
                            "stream": False,
                            "format": self._ollama_response_format(),
                            "options": {"temperature": 0.1, "num_predict": 512},
                        },
                    )
                    if fallback_resp.status_code == 200:
                        return fallback_resp.json().get("response", "")
                    logger.error(
                        f"❌ [OLLAMA-DIRECT] Fallback error {fallback_resp.status_code}: {fallback_resp.text}"
                    )
                    return ""
                else:
                    logger.error(
                        f"❌ [OLLAMA-DIRECT] Error {response.status_code}: {response.text}"
                    )
                    return ""
        except Exception as e:
            logger.error(f"❌ [OLLAMA-DIRECT] Failed to call Ollama: {e}")
            return ""

    def _build_distill_prompt(self, content: str) -> str:
        return f"""
                SYSTEM: You are the Supreme Knowledge Distiller. Your task is to compress raw information into a high-density wisdom node.

                INPUT CONTENT:
                {content}

                OUTPUT FORMAT (STRICT JSON):
                {{
                  "wisdom_summary": "One concise sentence capturing the core insight",
                  "instruction": "One clear actionable command or rule for an AI agent",
                  "category": "One word: coding, strategy, ops, or research"
                }}
                """

    def _parse_wisdom_json(self, text: str) -> dict:
        import re

        def _normalize(parsed):
            """Normalize parsed payload into dict when model returns wrapped JSON."""
            for _ in range(3):
                if isinstance(parsed, dict):
                    return parsed
                if isinstance(parsed, list):
                    parsed = parsed[0] if parsed else {}
                    continue
                if isinstance(parsed, str):
                    s = re.sub(r"```json\s*", "", parsed)
                    s = re.sub(r"```\s*", "", s).strip()
                    if not s:
                        return {}
                    if s[:1] in "{[" or (s[:1] == '"' and any(ch in s for ch in "{[")):
                        try:
                            parsed = json.loads(s)
                            continue
                        except Exception:
                            return {}
                    return {}
                return {}
            return parsed if isinstance(parsed, dict) else {}

        # 1. Clean markdown and whitespace
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*", "", text)
        text = text.strip()

        # 2. Try direct parse
        try:
            parsed = json.loads(text)
            return _normalize(parsed)
        except Exception:
            pass

        # 3. Try array extraction first
        array_match = re.search(r"(\[.*\])", text, re.DOTALL)
        if array_match:
            try:
                parsed = json.loads(array_match.group(1))
                return _normalize(parsed)
            except Exception:
                pass

        # 4. Try object extraction and normalize trailing commas
        obj_match = re.search(r"(\{.*\})", text, re.DOTALL)
        if obj_match:
            try:
                # [SINGULARITY 31.22] Enhanced cleaning: remove trailing commas before closing braces
                clean_obj = obj_match.group(1)
                clean_obj = re.sub(r",\s*([\}\]])", r"\1", clean_obj)
                # Remove potential comments if model added them
                clean_obj = re.sub(r"//.*?\n", "", clean_obj)
                parsed = json.loads(clean_obj)
                return _normalize(parsed)
            except Exception:
                pass

        # 5. Last resort: scan first decodable JSON token in text
        decoder = json.JSONDecoder()
        starts = [i for i, ch in enumerate(text) if ch in "{["]
        for start_idx in starts:
            try:
                parsed, _ = decoder.raw_decode(text[start_idx:])
                return _normalize(parsed)
            except Exception:
                continue

        # 6. Salvage fields from malformed JSON/text (best effort)
        try:
            key_patterns = {
                "wisdom_summary": r'"?(wisdom_summary|summary|knowledge_summary)"?\s*:\s*"([^"]+)"',
                "instruction": r'"?(instruction|action|next_step|command)"?\s*:\s*"([^"]+)"',
                "category": r'"?(category|topic|type|Тип)"?\s*:\s*"([^"]+)"',
            }
            salvaged = {}
            for out_key, pattern in key_patterns.items():
                m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
                if m:
                    salvaged[out_key] = m.group(2).strip()
            if salvaged:
                salvaged.setdefault(
                    "instruction", "Использовать как сжатый контекст и сверять с первоисточником."
                )
                salvaged.setdefault("category", "strategy")
                return salvaged
        except Exception:
            pass

        # 7. Line-based extraction for non-JSON model outputs:
        #    WISDOM_SUMMARY: ...
        #    INSTRUCTION: ...
        #    CATEGORY: ...
        try:
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            line_salvaged = {}
            for ln in lines:
                lower = ln.lower()
                if lower.startswith(
                    ("wisdom_summary:", "summary:", "knowledge_summary:", "суть:", "итог:")
                ):
                    line_salvaged["wisdom_summary"] = ln.split(":", 1)[1].strip().strip('"')
                elif lower.startswith(
                    ("instruction:", "action:", "next_step:", "команда:", "шаг:")
                ):
                    line_salvaged["instruction"] = ln.split(":", 1)[1].strip().strip('"')
                elif lower.startswith(("category:", "topic:", "type:", "категория:", "тип:")):
                    line_salvaged["category"] = ln.split(":", 1)[1].strip().strip('"')
            if line_salvaged.get("wisdom_summary"):
                line_salvaged.setdefault(
                    "instruction", "Использовать как сжатый контекст и сверять с первоисточником."
                )
                line_salvaged.setdefault("category", "strategy")
                return line_salvaged
        except Exception:
            pass

        raise ValueError("Could not extract valid JSON")

    async def _distill_single_node(self, node_id: str, content: str) -> dict | None:
        prompt = self._build_distill_prompt(content)
        distilled_json = ""
        for attempt in range(3):
            distilled_json = await self._call_teacher_direct(prompt)
            if distilled_json:
                break
            logger.warning(f"⚠️ [OLLAMA-RETRY] Attempt {attempt + 1} failed for node {node_id}")
            await asyncio.sleep(2)

        if not distilled_json:
            logger.error(
                f"❌ [DISTILLATION] Failed to get response for node {node_id} after 3 attempts."
            )
            return {"_error": "no_response"}

        try:
            wisdom = self._parse_wisdom_json(distilled_json)
            if not isinstance(wisdom, dict):
                raise ValueError(f"Expected dict, got {type(wisdom)}")
            return wisdom
        except Exception as parse_err:
            logger.error(
                f"❌ [DISTILLATION] Failed to parse wisdom for node {node_id}: {parse_err}. Response: {distilled_json[:100]}..."
            )
            if distilled_json and str(distilled_json).strip():
                logger.warning(
                    f"⚠️ [DISTILLATION] Using fallback wisdom for node {node_id} due to parse_error."
                )
                return self._fallback_wisdom_from_text(distilled_json, content)
            return {"_error": "parse_error"}

    @staticmethod
    def _as_text(value) -> str:
        """Convert arbitrary LLM field to compact text safely."""
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (int, float, bool)):
            return str(value).strip()
        if isinstance(value, dict):
            for key in ("text", "summary", "value", "content", "strategy", "tone"):
                v = value.get(key) if isinstance(value, dict) else None
                if isinstance(v, str) and v.strip():
                    return v.strip()
            try:
                return json.dumps(value, ensure_ascii=False)[:500].strip()
            except Exception:
                return str(value).strip()
        if isinstance(value, list):
            parts = [KnowledgeDistiller._as_text(v) for v in value]
            return " ".join([p for p in parts if p]).strip()
        return str(value).strip()

    @staticmethod
    def _fallback_wisdom_from_text(raw_text: str, content: str) -> dict:
        """Build minimal valid wisdom when model ignores JSON contract."""
        import re

        text = (raw_text or "").strip()
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*", "", text).strip()
        text = re.sub(r"^\*+", "", text).strip()
        text = re.sub(r"\s+", " ", text).strip()

        summary_src = text or (content or "")
        summary = summary_src[:220].strip()
        if len(summary) > 200:
            summary = summary[:197].rstrip() + "..."
        if not summary:
            summary = "Краткий вывод по узлу знаний сформирован."

        return {
            "wisdom_summary": summary,
            "instruction": "Использовать как сжатый контекст и сверять с первоисточником перед применением.",
            "category": "strategy",
            "_quality_source": "fallback_parse",
        }

    @staticmethod
    def _compute_quality_gate(
        wisdom_summary: str, instruction: str, category: str, wisdom: dict
    ) -> tuple[float, str]:
        """
        Compute honest confidence and verification reason for distilled node.
        Returns (confidence_score, verification_reason).
        """
        category_norm = (category or "").strip().lower()
        valid_categories = {"coding", "strategy", "ops", "research"}
        reasons = []
        score = 0.20  # [FIX] Lower base score to better distinguish quality

        if wisdom_summary:
            summary_len = len(wisdom_summary.strip())
            if summary_len >= 90:
                score += 0.30
                reasons.append("summary_rich")
            elif summary_len >= 45:
                score += 0.15
                reasons.append("summary_ok")
            else:
                score += 0.05
                reasons.append("summary_short")
        else:
            reasons.append("summary_empty")

        if instruction and len(instruction.strip()) >= 25:
            score += 0.15
            reasons.append("instruction_present")
        else:
            reasons.append("instruction_weak")

        if category_norm in valid_categories:
            score += 0.10
            reasons.append("category_valid")
        else:
            reasons.append("category_fallback")

        if (wisdom or {}).get("_quality_source") == "fallback_parse":
            score -= 0.25
            reasons.append("fallback_parse_penalty")

        # Short content penalty
        if wisdom_summary and len(wisdom_summary.strip()) < 30:
            score -= 0.20
            reasons.append("too_short")

        score = max(0.10, min(1.0, round(score, 4)))
        return score, "|".join(reasons)

    @staticmethod
    def _ensure_string_list(value) -> list[str]:
        """Normalize value to list[str] without empty entries."""
        if value is None:
            return []
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if isinstance(value, str):
            text = value.strip()
            return [text] if text else []
        return [str(value).strip()] if str(value).strip() else []

    @staticmethod
    def _to_float_score(value, default: float) -> float:
        try:
            v = float(value)
            return round(max(0.0, min(1.0, v)), 4)
        except Exception:
            return round(default, 4)

    def _compose_structured_metadata(
        self,
        old_metadata: dict,
        content: str,
        wisdom_summary: str,
        instruction: str,
        category: str,
        quality_confidence: float,
    ) -> dict:
        """
        Build RAG-friendly v2 metadata in a backward-compatible way.
        """
        source = self._as_text(old_metadata.get("source")) or "knowledge_node"
        domains = self._ensure_string_list(old_metadata.get("domains"))
        topics = self._ensure_string_list(old_metadata.get("topics"))
        if not domains and topics:
            domains = topics[:]

        claims = old_metadata.get("claims")
        if not isinstance(claims, list):
            claims = []

        takeaways = self._ensure_string_list(old_metadata.get("takeaways"))
        if not takeaways and instruction:
            takeaways = [instruction]

        return {
            # Existing colleague schema fields (when available) are preserved.
            "core_thesis": self._as_text(old_metadata.get("core_thesis")) or wisdom_summary,
            "mental_models": self._ensure_string_list(old_metadata.get("mental_models")),
            "claims": claims,
            "takeaways": takeaways,
            "domains": domains,
            "topics": topics,
            # Yesterday's v2 structure for decision-grade RAG.
            "decision_context": self._as_text(old_metadata.get("decision_context"))
            or self._as_text(old_metadata.get("type"))
            or category,
            "risk_level": self._as_text(old_metadata.get("risk_level")) or "medium",
            "counter_claims": self._ensure_string_list(old_metadata.get("counter_claims")),
            "invalidates_if": self._ensure_string_list(old_metadata.get("invalidates_if")),
            "actionability_score": self._to_float_score(
                old_metadata.get("actionability_score"), 0.8 if instruction else 0.5
            ),
            "source_reliability_score": self._to_float_score(
                old_metadata.get("source_reliability_score"),
                0.7 if source != "unknown" else 0.5,
            ),
            "applicability_scope": self._as_text(old_metadata.get("applicability_scope"))
            or category,
            "evidence_strength": self._as_text(old_metadata.get("evidence_strength"))
            or ("strong" if claims else "moderate"),
            "freshness_half_life_days": int(old_metadata.get("freshness_half_life_days") or 180),
            "distillation_schema_version": "v2",
            "distillation_quality_band": (
                "high"
                if quality_confidence >= 0.8
                else ("medium" if quality_confidence >= 0.6 else "low")
            ),
            "source_type": self._as_text(old_metadata.get("type")) or source,
            "summary": self._as_text(old_metadata.get("summary")) or wisdom_summary,
            "source": source,
            # Content length helps retrieval/ranking heuristics downstream.
            "content_length_chars": len((content or "").strip()),
        }

    async def _mark_retry_or_failed(
        self, conn, node_id: str, metadata_str: str | None, reason: str
    ):
        """Mark node as retry/failed to avoid infinite processing loops."""
        try:
            old_metadata = json.loads(metadata_str) if metadata_str else {}
        except Exception:
            old_metadata = {}

        attempts = int(old_metadata.get("distill_attempts", 0)) + 1
        now_ts = int(datetime.now().timestamp())
        next_retry_ts = now_ts + min(RETRY_BASE_SECONDS * (2 ** (attempts - 1)), 3600)
        status = "failed" if attempts >= MAX_DISTILL_RETRIES else "retry"

        patch = {
            "distill_status": status,
            "distill_attempts": attempts,
            "distill_last_error": reason,
            "distill_last_attempt_at": datetime.now().isoformat(),
            "distill_next_retry_ts": next_retry_ts,
            "distilled": "false",
        }

        await conn.execute(
            """
            UPDATE knowledge_nodes
            SET metadata = COALESCE(metadata, '{}'::jsonb) || $1::jsonb
            WHERE id = $2::uuid
            """,
            json.dumps(patch),
            node_id,
        )
        logger.warning(
            f"⚠️ [DISTILL-STATE] Node {node_id}: {status} (attempt {attempts}/{MAX_DISTILL_RETRIES}) reason={reason}"
        )

    async def distill_knowledge_batch(self):
        """
        [SINGULARITY 31.0] Quantum Leap: DuckDB-accelerated batch distillation.
        [SINGULARITY 31.12] Top-10,000 Prioritization: Focus on high-value nodes.
        """
        logger.info("⚗️ [DISTILLATION] Starting Quantum Leap distillation cycle...")

        tx = None
        try:
            import duckdb

            lancedb_svc = None
            try:
                from app.lancedb_service import get_lancedb_service

                lancedb_svc = get_lancedb_service()
            except Exception as ldb_err:
                logger.warning(
                    "⚠️ [LANCEDB] unavailable, continuing without vector sync: %s", ldb_err
                )

            # 1. Connect to Postgres and claim a small locked batch window
            # [SINGULARITY 31.21] Giants practice: row-level leasing via FOR UPDATE SKIP LOCKED
            conn = await asyncpg.connect(DB_URL)
            batch_size = await self._get_elastic_batch_size()
            candidate_pool = max(batch_size * 3, 30)
            tx = conn.transaction()
            await tx.start()

            # 2. Use DuckDB to "grind" the data in-memory
            # [SINGULARITY 31.12] Fetching nodes, prioritizing low confidence (< 0.5) for quality lift
            raw_nodes = await conn.fetch(
                """
                SELECT id::text, content, domain_id, metadata::text as metadata_str, confidence_score, embedding::text as vector_str
                FROM knowledge_nodes
                WHERE is_verified = TRUE
                AND (metadata->>'distilled' IS NULL OR metadata->>'distilled' = 'false')
                AND COALESCE(metadata->>'distill_status', 'pending') != 'failed'
                AND (
                    metadata->>'distill_status' IS DISTINCT FROM 'retry'
                    OR COALESCE((metadata->>'distill_next_retry_ts')::bigint, 0) <= EXTRACT(EPOCH FROM NOW())::bigint
                )
                ORDER BY
                    CASE WHEN confidence_score < 0.5 THEN 0 ELSE 1 END ASC,
                    confidence_score DESC,
                    created_at DESC
                FOR UPDATE SKIP LOCKED
                LIMIT $1
                """,
                candidate_pool,
            )

            if not raw_nodes:
                logger.info("😴 [DISTILLATION] No nodes to distill.")
                await tx.rollback()
                await conn.close()
                return

            # Load into DuckDB
            duck_conn = duckdb.connect(database=":memory:")

            # Convert asyncpg records to list of dicts for DuckDB
            data_for_duck = []
            for r in raw_nodes:
                data_for_duck.append(
                    {
                        "id": r["id"],
                        "content": r["content"],
                        "metadata_str": r["metadata_str"],
                        "confidence_score": r["confidence_score"],
                        "vector_str": r["vector_str"],
                    }
                )

            # [FIX v31.1] Use PyArrow for reliable DuckDB ingestion
            import pyarrow as pa

            table = pa.Table.from_pylist(data_for_duck)
            duck_conn.register("raw_nodes_source", table)

            # 3. Fast filtering/sorting in DuckDB
            processed_nodes = duck_conn.execute(f"""
                SELECT id, content, metadata_str, vector_str
                FROM raw_nodes_source
                ORDER BY confidence_score DESC
                LIMIT {batch_size}
            """).fetchall()

            # 4. Parallel teacher calls within the selected batch
            llm_concurrency = min(batch_size, int(os.getenv("DISTILL_LLM_CONCURRENCY", "1")))
            semaphore = asyncio.Semaphore(llm_concurrency)

            async def distill_one(node_row):
                node_id, content, metadata_str, vector_str = node_row
                logger.info(f"🧪 [DISTILLATION] Distilling node: {node_id}")
                async with semaphore:
                    wisdom = await self._distill_single_node(node_id, content)
                return node_id, content, metadata_str, vector_str, wisdom

            distilled_results = await asyncio.gather(*(distill_one(row) for row in processed_nodes))

            # 5. Persist successful results
            db_connection_lost = False
            for node_id, content, metadata_str, vector_str, wisdom in distilled_results:
                if not wisdom:
                    await self._mark_retry_or_failed(conn, node_id, metadata_str, "no_wisdom")
                    continue

                if wisdom.get("_error"):
                    await self._mark_retry_or_failed(
                        conn, node_id, metadata_str, wisdom.get("_error")
                    )
                    continue

                old_metadata = json.loads(metadata_str) if metadata_str else {}

                # Normalize possible non-standard model output keys (Role/Tone/Strategy/etc)
                wisdom_summary = self._as_text(wisdom.get("wisdom_summary"))
                if not wisdom_summary:
                    wisdom_summary = self._as_text(wisdom.get("summary")) or self._as_text(
                        wisdom.get("Strategy")
                    )

                instruction = self._as_text(wisdom.get("instruction"))
                if not instruction:
                    instruction = self._as_text(wisdom.get("action")) or self._as_text(
                        wisdom.get("next_step")
                    )

                category = (
                    self._as_text(wisdom.get("category"))
                    or self._as_text(wisdom.get("topic"))
                    or "strategy"
                )
                quality_confidence, verification_reason = self._compute_quality_gate(
                    wisdom_summary, instruction, category, wisdom
                )

                # Guardrail: do not mark as distilled if summary is empty
                if not wisdom_summary:
                    logger.warning(
                        f"⚠️ [QUALITY-GUARD] Empty wisdom_summary for node {node_id}, skipping update."
                    )
                    await self._mark_retry_or_failed(
                        conn, node_id, metadata_str, "empty_wisdom_summary"
                    )
                    continue

                new_metadata = dict(old_metadata)
                structured_metadata = self._compose_structured_metadata(
                    old_metadata=old_metadata,
                    content=content,
                    wisdom_summary=wisdom_summary,
                    instruction=instruction,
                    category=category,
                    quality_confidence=quality_confidence,
                )
                new_metadata.update(
                    {
                        "distilled": "true",
                        "distilled_at": datetime.now().isoformat(),
                        "wisdom_summary": wisdom_summary,
                        "instruction": instruction,
                        "distilled_by": self.teacher_model,
                        "category": category,
                        "distill_status": "done",
                        "distill_last_error": "",
                        "distill_attempts": 0,
                        "distill_next_retry_ts": 0,
                        "verification_reason": verification_reason,
                        "distill_confidence": quality_confidence,
                    }
                )
                new_metadata.update(structured_metadata)

                try:
                    exists = await conn.fetchval(
                        "SELECT count(*) FROM knowledge_nodes WHERE id = $1::uuid", node_id
                    )
                    if not exists:
                        logger.warning(
                            f"⏭️ [POSTGRES-SYNC] Node {node_id} no longer exists (likely merged/deleted). Skipping."
                        )
                        continue

                    distill_patch = {
                        "distilled": "true",
                        "distilled_at": datetime.now().isoformat(),
                        "wisdom_summary": wisdom_summary,
                        "instruction": instruction,
                        "distilled_by": self.teacher_model,
                        "category": category,
                        "distill_status": "done",
                        "distill_last_error": "",
                        "distill_attempts": 0,
                        "distill_next_retry_ts": 0,
                        "verification_reason": verification_reason,
                        "distill_confidence": quality_confidence,
                    }
                    distill_patch.update(structured_metadata)

                    res = await conn.execute(
                        """
                        UPDATE knowledge_nodes
                        SET metadata = COALESCE(metadata, '{}'::jsonb) || $1::jsonb,
                            confidence_score = $2
                        WHERE id = $3::uuid
                        """,
                        json.dumps(distill_patch),
                        quality_confidence,
                        node_id,
                    )

                    if res == "UPDATE 0":
                        logger.warning(
                            f"⚠️ [POSTGRES-SYNC] Node {node_id} update result: {res} (not found)"
                        )
                        continue

                    verify_count = await conn.fetchval(
                        "SELECT count(*) FROM knowledge_nodes WHERE id = $1::uuid AND metadata->>'distilled' = 'true'",
                        node_id,
                    )
                    if verify_count > 0:
                        logger.info(f"✅ [VERIFIED] Node {node_id} is distilled.")
                    else:
                        logger.warning(
                            f"⚠️ [VERIFY-FAILED] Node {node_id} update reported success but check failed."
                        )
                except Exception as pg_err:
                    err_text = str(pg_err).lower()
                    logger.error(f"❌ [POSTGRES-SYNC] Failed to update node {node_id}: {pg_err}")
                    if "connection is closed" in err_text:
                        # Stop current batch on lost DB connection to avoid error storms.
                        db_connection_lost = True
                        logger.warning(
                            "⚠️ [POSTGRES-SYNC] Connection lost during batch; stopping current persist loop."
                        )
                        break
                    continue

                if lancedb_svc and vector_str and vector_str != "None":
                    try:
                        if isinstance(vector_str, list):
                            vector = [float(x) for x in vector_str]
                        else:
                            vector = [
                                float(x)
                                for x in str(vector_str).strip("[]").split(",")
                                if x.strip()
                            ]
                        await lancedb_svc.upsert_batch(
                            [
                                {
                                    "id": node_id,
                                    "vector": vector,
                                    "content": content,
                                    "metadata": new_metadata,
                                    "confidence_score": quality_confidence,
                                }
                            ]
                        )
                    except Exception as vec_err:
                        logger.warning(
                            f"⚠️ [LANCEDB-SYNC] Failed to sync vector for {node_id}: {vec_err}"
                        )
                else:
                    logger.debug(
                        f"⏭️ [LANCEDB-SYNC] Skipping node {node_id} (no vector sync backend)."
                    )

                logger.info(f"✅ [DISTILLATION] Node {node_id} compressed and synced.")

            if db_connection_lost:
                raise RuntimeError("distillation_db_connection_closed")

            await tx.commit()
            await conn.close()

        except Exception as e:
            try:
                await tx.rollback()
            except Exception:
                pass
            logger.error(f"❌ [DISTILLATION] Quantum Leap error: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    distiller = KnowledgeDistiller()
    asyncio.run(distiller.distill_knowledge_batch())
