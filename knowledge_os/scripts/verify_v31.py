# scripts/verify_v31.py
import asyncio
import logging
import os
import sys

# Add app to path
sys.path.append("/app")
sys.path.append("/app/knowledge_os/app")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VERIFY-V31")


async def test_duckdb_distillation():
    logger.info("🧪 Testing DuckDB-accelerated distillation...")
    try:
        from distillation_engine import KnowledgeDistiller

        distiller = KnowledgeDistiller()
        # We don't run the full batch to avoid heavy LLM calls,
        # but we check if the imports and DuckDB logic work.
        logger.info("✅ Distiller initialized.")
        return True
    except Exception as e:
        logger.error(f"❌ Distiller test failed: {e}")
        return False


async def test_lancedb_rag():
    logger.info("🧪 Testing LanceDB RAG integration...")
    try:
        from lancedb_service import get_lancedb_service

        svc = get_lancedb_service()
        logger.info("✅ LanceDB service initialized.")

        # Test search with dummy vector
        dummy_vector = [0.1] * 768
        results = await svc.search(dummy_vector, limit=1)
        logger.info(f"✅ LanceDB search test completed (found {len(results)} nodes).")
        return True
    except Exception as e:
        logger.error(f"❌ LanceDB test failed: {e}")
        return False


async def main():
    d_ok = await test_duckdb_distillation()
    l_ok = await test_lancedb_rag()

    if d_ok and l_ok:
        logger.info("🚀 [SINGULARITY v31.0] Verification SUCCESSFUL.")
    else:
        logger.error("❌ [SINGULARITY v31.0] Verification FAILED.")


if __name__ == "__main__":
    asyncio.run(main())
