"""
Swarm Studio - Web UI for Multi-Agent Swarm Management
Dashboard for monitoring and controlling swarm agents.

Usage:
    uvicorn swarm_studio:app --port 8006
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

app = FastAPI(title="Swarm Studio", version="1.1.0")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")

_swarm_state: Dict[str, Any] = {
    "agents": {},
    "tasks": [],
    "messages": [],
}


async def _load_agents_from_db():
    """Load agents from database."""
    try:
        import asyncpg

        conn = await asyncpg.connect(DATABASE_URL)
        rows = await conn.fetch("""
            SELECT id, name, role, system_prompt, department, created_at
            FROM experts
            WHERE is_active = TRUE
            ORDER BY name
            LIMIT 50
        """)
        await conn.close()
        return [
            {
                "id": str(r["id"]),
                "name": r["name"],
                "role": r["role"],
                "department": r.get("department", ""),
                "status": "running" if r["name"] in _swarm_state["agents"] else "idle",
                "started_at": r["created_at"].isoformat()
                if r["created_at"]
                else datetime.now(timezone.utc).isoformat(),
                "messages_count": 0,
            }
            for r in rows
        ]
    except Exception as e:
        logger.warning(f"[SwarmStudio] DB error: {e}")
        return []


class AgentInfo(BaseModel):
    id: str
    name: str
    status: str
    started_at: str
    messages_count: int


class TaskInfo(BaseModel):
    id: str
    description: str
    status: str
    assigned_agent: Optional[str]
    created_at: str


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return """<!DOCTYPE html>
<html>
<head>
    <title>Swarm Studio</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #1a1a2e; color: #eee; }
        h1 { color: #00d4ff; }
        .card { background: #16213e; padding: 15px; margin: 10px 0; border-radius: 8px; }
        .agent { border-left: 4px solid #00d4ff; }
        .task { border-left: 4px solid #ffd700; }
        .status-running { color: #00ff88; }
        .status-pending { color: #ffa500; }
    </style>
</head>
<body>
    <h1>🐝 Swarm Studio</h1>
    <div class="card">
        <h2>Active Agents</h2>
        <div id="agents">Loading...</div>
    </div>
    <div class="card">
        <h2>Tasks</h2>
        <div id="tasks">Loading...</div>
    </div>
    <script>
        async function update() {
            const r = await fetch('/api/state');
            const s = await r.json();
            document.getElementById('agents').innerHTML =
                s.agents.map(a => `<div class="card agent">${a.name} - <span class="status-${a.status}">${a.status}</span></div>`).join('');
            document.getElementById('tasks').innerHTML =
                s.tasks.map(t => `<div class="card task">${t.description} - ${t.status}</div>`).join('');
        }
        setInterval(update, 5000);
        update();
    </script>
</body>
</html>"""


@app.get("/api/state")
async def get_state():
    """Get full state with agents from DB."""
    agents = await _load_agents_from_db()
    return {
        "agents": agents,
        "tasks": _swarm_state.get("tasks", []),
        "messages_count": len(_swarm_state.get("messages", [])),
    }


@app.get("/api/agents")
async def list_agents():
    """List all agents from DB."""
    return await _load_agents_from_db()


@app.post("/api/agents")
async def add_agent(agent: AgentInfo):
    _swarm_state["agents"][agent.id] = agent.dict()
    return {"status": "ok"}


@app.delete("/api/agents/{agent_id}")
async def remove_agent(agent_id: str):
    if agent_id in _swarm_state["agents"]:
        del _swarm_state["agents"][agent_id]
        return {"status": "ok"}
    raise HTTPException(404, "Agent not found")


@app.get("/api/tasks")
async def get_tasks():
    return _swarm_state.get("tasks", [])


@app.post("/api/tasks")
async def add_task(task: TaskInfo):
    _swarm_state["tasks"].append(task.dict())
    return {"status": "ok"}


@app.get("/api/stream")
async def stream_state():
    """Server-Sent Events stream for real-time updates."""

    async def event_generator():
        while True:
            state = await get_state()
            yield f"data: {json.dumps(state)}\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/experts/{expert_name}/chat")
async def expert_chat(expert_name: str, message: str):
    """Chat with specific expert via ai_core."""
    try:
        from ai_core import run_smart_agent_async

        result = await run_smart_agent_async(message, expert_name=expert_name, category="chat")
        return {"expert": expert_name, "response": result}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/checkpoints")
async def list_checkpoints(task_id: str = None, limit: int = 20):
    """List checkpoints from DB."""
    try:
        import asyncpg

        conn = await asyncpg.connect(DATABASE_URL)
        if task_id:
            rows = await conn.fetch(
                """
                SELECT * FROM checkpoints
                WHERE task_id = $1
                ORDER BY created_at DESC
                LIMIT $2
            """,
                task_id,
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT * FROM checkpoints
                ORDER BY created_at DESC
                LIMIT $1
            """,
                limit,
            )
        await conn.close()
        return [
            {
                "checkpoint_id": r["checkpoint_id"],
                "task_id": r["task_id"],
                "agent": r["agent_name"],
                "step": r["step"],
                "progress": r["progress"],
                "created": r["created_at"].isoformat(),
            }
            for r in rows
        ]
    except Exception as e:
        return []


@app.get("/api/plans")
async def list_plans(status: str = None):
    """Get long-term plans from long_term_memory."""
    try:
        import asyncpg

        conn = await asyncpg.connect(DATABASE_URL)
        rows = await conn.fetch("""
            SELECT goal_summary, outcome_summary, created_at
            FROM long_term_memory
            ORDER BY created_at DESC
            LIMIT 20
        """)
        await conn.close()
        return [
            {
                "goal": r["goal_summary"],
                "outcome": r["outcome_summary"],
                "created": r["created_at"].isoformat(),
            }
            for r in rows
        ]
    except Exception as e:
        return []


def get_swarm_studio():
    return app


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("SWARM_STUDIO_PORT", "8006"))
    uvicorn.run(app, host="0.0.0.0", port=port)
