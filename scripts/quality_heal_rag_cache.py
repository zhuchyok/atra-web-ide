#!/usr/bin/env python3
"""
Self-healing: очистка RAG кэша при падении качества (Фаза 4.1, День 6).
Рекомендации Backend (Игорь): инвалидация кэша после провала валидации.
Рекомендации SRE (Елена): runbook — при алерте качества выполнить этот скрипт и перезапустить валидацию.

Использование: python3 scripts/quality_heal_rag_cache.py
"""
import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "backend"))


async def main() -> int:
    try:
        from app.services.rag_context_cache import get_rag_context_cache
    except ImportError:
        print("❌ Запустите из корня репо с PYTHONPATH=backend или из backend/")
        return 1
    cache = get_rag_context_cache()
    count = await cache.clear_all()
    print(f"✅ RAG кэш очищен: {count} записей")
    print("💡 Запустите повторную валидацию: ./scripts/run_quality_pipeline.sh")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
