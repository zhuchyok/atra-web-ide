import asyncio
import logging
import os
from typing import Dict, Optional

import asyncpg

logger = logging.getLogger(__name__)


class DomainCache:
    """
    [SINGULARITY 21.22] In-memory cache for domain IDs to speed up RAG.
    """

    _cache: Dict[str, int] = {}
    _lock = asyncio.Lock()

    @classmethod
    async def get_domain_id(cls, conn, domain_name: str) -> Optional[int]:
        if domain_name in cls._cache:
            return cls._cache[domain_name]

        async with cls._lock:
            # Double check after lock
            if domain_name in cls._cache:
                return cls._cache[domain_name]

            row = await conn.fetchrow("SELECT id FROM domains WHERE name = $1 LIMIT 1", domain_name)
            if row:
                cls._cache[domain_name] = row["id"]
                return row["id"]
        return None


async def get_domain_id(conn, domain_name: str) -> Optional[int]:
    return await DomainCache.get_domain_id(conn, domain_name)
