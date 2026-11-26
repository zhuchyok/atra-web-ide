"""
Agent Dependency Graph — отслеживает взаимодействия между агентами.

Предоставляет граф вызовов агентов: кто кого вызвал, с какой задержкой,
успешностью. Позволяет анализировать цепочки зависимостей, критические пути
и статистику по каждому агенту.

Edges хранятся в памяти + асинхронно сбрасываются в PostgreSQL.
"""

import asyncio
import logging
import os
import threading
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Database connection
try:
    import asyncpg

    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")


@dataclass
class AgentCallEdge:
    """Одно ребро в графе зависимостей агентов — представляет interaction агент→агент."""

    source_agent: str
    target_agent: str
    edge_type: str  # handoff, message, delegate, observe, bid
    task_id: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    latency_ms: float = 0.0
    success: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_agent": self.source_agent,
            "target_agent": self.target_agent,
            "edge_type": self.edge_type,
            "task_id": self.task_id,
            "timestamp": self.timestamp.isoformat(),
            "latency_ms": self.latency_ms,
            "success": self.success,
        }


class AgentDependencyGraph:
    """
    Граф зависимостей между агентами.

    Потокобезопасен (threading.Lock). Рёбра хранятся в памяти;
    асинхронно сбрасываются в PostgreSQL при вызове record_call().
    """

    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or DB_URL
        self._edges: List[AgentCallEdge] = []
        self._pending_edges: List[AgentCallEdge] = []
        self._lock = threading.Lock()

        # Stats per target agent (только in-memory, не персистентны)
        # Структура: agent_name -> {call_count, success_count, total_latency}
        self._stats: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {"call_count": 0, "success_count": 0, "total_latency": 0.0}
        )

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_call(
        self,
        source_agent: str,
        target_agent: str,
        edge_type: str,
        task_id: Optional[str] = None,
        latency_ms: float = 0.0,
        success: bool = True,
    ) -> AgentCallEdge:
        """
        Записать interaction агент→агент.

        Добавляет ребро в память и пытается запустить асинхронный flush в БД.
        Возвращает созданный AgentCallEdge.
        """
        edge = AgentCallEdge(
            source_agent=source_agent,
            target_agent=target_agent,
            edge_type=edge_type,
            task_id=task_id,
            timestamp=datetime.now(timezone.utc),
            latency_ms=latency_ms,
            success=success,
        )

        with self._lock:
            self._edges.append(edge)
            self._pending_edges.append(edge)

            # Stats: со стороны target-agent (кто вызывал этого агента)
            tgt = self._stats[target_agent]
            tgt["call_count"] += 1
            if success:
                tgt["success_count"] += 1
            tgt["total_latency"] += latency_ms

            # Также трекаем out-degree source-agent
            src_key = f"__out_{source_agent}"
            src = self._stats[src_key]
            src["call_count"] += 1

        # Fire-and-forget async flush (только если есть running loop)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self._flush_to_db())
        except RuntimeError:
            pass

        logger.debug(
            "📊 [DEP GRAPH] %s → %s (%s) lat=%.1fms success=%s",
            source_agent,
            target_agent,
            edge_type,
            latency_ms,
            success,
        )
        return edge

    # ------------------------------------------------------------------
    # Query: upstream / downstream
    # ------------------------------------------------------------------

    def get_upstream(self, agent_name: str) -> List[str]:
        """
        Агенты, которые вызывали данного агента (предшественники).
        Уникальные имена, отсортированные по алфавиту.
        """
        with self._lock:
            return sorted({e.source_agent for e in self._edges if e.target_agent == agent_name})

    def get_downstream(self, agent_name: str) -> List[str]:
        """
        Агенты, которых вызывал данный агент (преемники).
        Уникальные имена, отсортированные по алфавиту.
        """
        with self._lock:
            return sorted({e.target_agent for e in self._edges if e.source_agent == agent_name})

    # ------------------------------------------------------------------
    # Critical path (shortest path via BFS)
    # ------------------------------------------------------------------

    def get_critical_path(self, from_agent: str, to_agent: str) -> List[str]:
        """
        Кратчайшая цепочка зависимостей от from_agent до to_agent.

        Использует BFS на ориентированном графе вызовов.
        Возвращает список имён агентов (включая from и to) или
        пустой список, если пути нет.
        """
        if from_agent == to_agent:
            return [from_agent]

        adj: Dict[str, Set[str]] = defaultdict(set)
        with self._lock:
            for e in self._edges:
                adj[e.source_agent].add(e.target_agent)

        visited: Set[str] = {from_agent}
        queue: deque = deque([(from_agent, [from_agent])])

        while queue:
            current, path = queue.popleft()
            for neighbor in adj.get(current, []):
                if neighbor == to_agent:
                    return path + [neighbor]
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return []

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self, agent_name: str) -> Dict[str, Any]:
        """
        Статистика по агенту (на основе входящих вызовов).

        Returns:
            call_count, success_count, failed_count, success_rate, avg_latency_ms
        """
        with self._lock:
            s = self._stats.get(
                agent_name, {"call_count": 0, "success_count": 0, "total_latency": 0.0}
            )
            call_count = int(s["call_count"])
            success_count = int(s["success_count"])
            total_latency = s["total_latency"]

        failed_count = call_count - success_count
        return {
            "agent": agent_name,
            "call_count": call_count,
            "success_count": success_count,
            "failed_count": failed_count,
            "success_rate": round(success_count / call_count, 4) if call_count > 0 else 0.0,
            "avg_latency_ms": round(total_latency / call_count, 2) if call_count > 0 else 0.0,
            "total_latency_ms": round(total_latency, 2),
        }

    # ------------------------------------------------------------------
    # Visualization
    # ------------------------------------------------------------------

    def to_visualization_data(self) -> Dict[str, Any]:
        """
        Данные для визуализации графа.

        Возвращает dict с nodes, edges и сводной статистикой.
        Подходит для передачи в D3.js / Cytoscape / vis.js.
        """
        nodes: Dict[str, Dict[str, Any]] = {}
        edges: List[Dict[str, Any]] = []

        with self._lock:
            for e in self._edges:
                if e.source_agent not in nodes:
                    stats = self.get_stats(e.source_agent)
                    nodes[e.source_agent] = {
                        "id": e.source_agent,
                        "label": e.source_agent,
                        "call_count": stats["call_count"],
                        "success_rate": stats["success_rate"],
                        "avg_latency_ms": stats["avg_latency_ms"],
                    }
                if e.target_agent not in nodes:
                    stats = self.get_stats(e.target_agent)
                    nodes[e.target_agent] = {
                        "id": e.target_agent,
                        "label": e.target_agent,
                        "call_count": stats["call_count"],
                        "success_rate": stats["success_rate"],
                        "avg_latency_ms": stats["avg_latency_ms"],
                    }
                edges.append(
                    {
                        "source": e.source_agent,
                        "target": e.target_agent,
                        "edge_type": e.edge_type,
                        "task_id": e.task_id,
                        "latency_ms": e.latency_ms,
                        "success": e.success,
                    }
                )

            total_edges = len(self._edges)

        return {
            "nodes": list(nodes.values()),
            "edges": edges,
            "stats": {
                "total_edges": total_edges,
                "unique_agents": len(nodes),
            },
        }

    # ------------------------------------------------------------------
    # DB Persistence
    # ------------------------------------------------------------------

    async def flush(self) -> int:
        """
        Принудительный flush всех неперсистентных рёбер в PostgreSQL.
        Returns: количество записанных строк.
        """
        return await self._flush_to_db()

    async def _flush_to_db(self) -> int:
        """
        Асинхронно сбросить все неперсистентные рёбра в PostgreSQL.
        """
        edges_to_flush: List[AgentCallEdge] = []
        with self._lock:
            if not self._pending_edges:
                return 0
            edges_to_flush = list(self._pending_edges)
            self._pending_edges.clear()

        if not edges_to_flush:
            return 0

        if not ASYNCPG_AVAILABLE:
            logger.warning("[DEP GRAPH] asyncpg not available, edges kept in memory only")
            return 0

        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                await conn.executemany(
                    """
                    INSERT INTO agent_dependency_edges
                        (source_agent, target_agent, edge_type, task_id, latency_ms, success, recorded_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    [
                        (
                            e.source_agent,
                            e.target_agent,
                            e.edge_type,
                            e.task_id,
                            e.latency_ms,
                            e.success,
                            e.timestamp,
                        )
                        for e in edges_to_flush
                    ],
                )
            finally:
                await conn.close()

            logger.info(f"[DEP GRAPH] Flushed {len(edges_to_flush)} edges to DB")
            return len(edges_to_flush)
        except Exception as e:
            logger.error(f"[DEP GRAPH] Failed to flush edges to DB: {e}")
            # Возвращаем рёбра обратно в очередь для повторной попытки
            with self._lock:
                self._pending_edges.extend(edges_to_flush)
            return 0

    # ------------------------------------------------------------------
    # In-memory edge access
    # ------------------------------------------------------------------

    def get_all_edges(self) -> List[AgentCallEdge]:
        """Вернуть копию всех рёбер в памяти."""
        with self._lock:
            return list(self._edges)

    def clear(self):
        """Очистить все in-memory данные (НЕ трогает БД)."""
        with self._lock:
            self._edges.clear()
            self._pending_edges.clear()
            self._stats.clear()


# -------------------------------------------------------------------
# Singleton access
# -------------------------------------------------------------------

_graph_instance: Optional[AgentDependencyGraph] = None


def get_agent_dependency_graph() -> AgentDependencyGraph:
    """Получить глобальный экземпляр AgentDependencyGraph (singleton)."""
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = AgentDependencyGraph()
    return _graph_instance
