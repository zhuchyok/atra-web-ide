"""
Swarm Studio - Web UI for Multi-Agent Swarm Management
Dashboard for monitoring and controlling swarm agents.

Usage:
    uvicorn swarm_studio:app --port 8006
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

app = FastAPI(title="Swarm Studio", version="1.0.0")

_swarm_state: Dict[str, Any] = {
    "agents": {},
    "tasks": [],
    "messages": [],
}


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
    return _swarm_state


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


def get_swarm_studio():
    return app


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("SWARM_STUDIO_PORT", "8006"))
    uvicorn.run(app, host="0.0.0.0", port=port)
