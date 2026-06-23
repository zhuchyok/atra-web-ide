import asyncio
import json
import logging
import os
import random
import httpx
import asyncpg
import re
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("distill_audit")

# Use host.docker.internal for DB if running in container, or localhost if outside
DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")

# Smart Ollama URL detection
def get_ollama_url():
    base = os.getenv("OLLAMA_API_URL")
    if base:
        return base.rstrip('/') + "/api/generate"

    # Try host.docker.internal first (if in container)
    try:
        import socket
        socket.gethostbyname('host.docker.internal')
        return "http://host.docker.internal:11434/api/generate"
    except:
        return "http://localhost:11434/api/generate"

OLLAMA_URL = get_ollama_url()
AUDIT_MODEL = "gemma3n:e4b"
AUDIT_SAMPLE_SIZE = 50

async def call_auditor(prompt: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                OLLAMA_URL,
                json={
                    "model": AUDIT_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1}
                }
            )
            if response.status_code == 200:
                return response.json().get("response", "")
            return ""
    except Exception as e:
        logger.error(f"Error calling auditor: {e}")
        return ""

async def audit_node(node):
    content = node['content']
    metadata = json.loads(node['metadata']) if isinstance(node['metadata'], str) else node['metadata']
    summary = metadata.get('wisdom_summary', '')
    instruction = metadata.get('instruction', '')

    prompt = f"""
    SYSTEM: You are an expert Knowledge Quality Auditor. Evaluate the quality of a distilled knowledge node.

    ORIGINAL CONTENT:
    {content}

    DISTILLED SUMMARY:
    {summary}

    DISTILLED INSTRUCTION:
    {instruction}

    TASK: Rate the quality from 1 to 5 (5 is best) based on:
    1. Accuracy: Does the summary correctly reflect the content?
    2. Density: Is it concise but informative?
    3. Actionability: Is the instruction clear and useful?

    OUTPUT FORMAT (JSON):
    {{
      "score": 1-5,
      "reason": "Short explanation",
      "is_hallucination": true/false
    }}
    """

    resp = await call_auditor(prompt)
    try:
        match = re.search(r'(\{.*\})', resp, re.DOTALL)
        if match:
            return json.loads(match.group(1))
    except:
        pass
    return {"score": 0, "reason": f"Audit failed or invalid JSON: {resp[:100]}", "is_hallucination": False}

async def run_audit():
    logger.info(f"🚀 Starting distillation audit using {AUDIT_MODEL}...")

    try:
        conn = await asyncpg.connect(DB_URL)

        # Get nodes distilled in the last 24 hours
        # Note: metadata is jsonb in Postgres, asyncpg returns it as dict
        nodes = await conn.fetch("""
            SELECT id, content, metadata
            FROM knowledge_nodes
            WHERE metadata->>'distilled' = 'true'
            AND (metadata->>'distilled_at')::timestamp > NOW() - INTERVAL '24 hours'
            LIMIT 200
        """)

        if not nodes:
            logger.warning("No nodes found distilled in the last 24 hours.")
            await conn.close()
            return

        sample = random.sample(nodes, min(len(nodes), AUDIT_SAMPLE_SIZE))
        logger.info(f"Selected {len(sample)} nodes for audit.")

        results = []
        for node in sample:
            res = await audit_node(node)
            results.append(res)
            logger.info(f"Node {node['id']} - Score: {res.get('score', 0)}/5")

        # Calculate stats
        scores = [r.get('score', 0) for r in results if isinstance(r.get('score'), (int, float)) and r.get('score', 0) > 0]
        avg_score = sum(scores) / len(scores) if scores else 0
        hallucinations = sum(1 for r in results if r.get('is_hallucination') is True)

        report = {
            "timestamp": datetime.now().isoformat(),
            "auditor_model": AUDIT_MODEL,
            "sample_size": len(sample),
            "average_score": round(avg_score, 2),
            "hallucination_count": hallucinations,
            "failed_audits": len(results) - len(scores)
        }

        logger.info(f"📊 Audit Report: {json.dumps(report, indent=2)}")

        # Save report to file
        os.makedirs("docs/audits", exist_ok=True)
        report_path = f"docs/audits/distill_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)

        await conn.close()
        logger.info(f"✅ Audit complete. Report saved to {report_path}")

    except Exception as e:
        logger.error(f"Audit failed: {e}")

if __name__ == "__main__":
    asyncio.run(run_audit())
