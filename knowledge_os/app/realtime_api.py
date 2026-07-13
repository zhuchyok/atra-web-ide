import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiohttp
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/realtime", tags=["realtime"])


class RealtimeSession(BaseModel):
    session_id: str
    model: str = "gpt-4o-realtime-preview"
    modalities: list[str] = ["text", "audio"]
    instructions: str = "You are a helpful AI assistant."
    voice: str = "alloy"
    temperature: float = 0.8
    max_tokens: Optional[int] = None


class RealtimeMessage(BaseModel):
    role: str
    content: str
    type: str = "message"


class TranscriptChunk(BaseModel):
    transcript: str
    is_final: bool


_sessions: dict[str, dict] = {}
_active_connections: dict[str, list] = {}


async def create_realtime_session(
    model: str = "gpt-4o-realtime-preview",
    modalities: list[str] = ["text", "audio"],
    instructions: str = "You are a helpful AI assistant.",
    voice: str = "alloy",
) -> dict:
    session_id = f"session_{uuid.uuid4().hex[:12]}"

    session = {
        "session_id": session_id,
        "model": model,
        "modalities": modalities,
        "instructions": instructions,
        "voice": voice,
        "created_at": int(datetime.now().timestamp()),
        "messages": [],
    }

    _sessions[session_id] = session
    _active_connections[session_id] = []

    return session


async def send_realtime_message(
    session_id: str, role: str, content: str, type: str = "message"
) -> dict:
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = _sessions[session_id]
    message = {
        "role": role,
        "content": content,
        "type": type,
        "timestamp": int(datetime.now().timestamp()),
    }

    session["messages"].append(message)

    return message


async def stream_audio_response(session_id: str, text: str) -> AsyncGenerator[bytes, None]:
    url = "https://api.openai.com/v1/realtime"
    headers = {"Authorization": "Bearer NOT_SET", "Content-Type": "application/json"}

    session = _sessions.get(session_id)
    if not session:
        return

    data = {
        "model": session["model"],
        "modalities": session["modalities"],
        "instructions": session["instructions"],
        "voice": session["voice"],
        "input": text,
    }

    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as client:
        try:
            ws = await client.ws_connect(url, headers=headers)

            await ws.send_json(data)

            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.BINARY:
                    yield msg.data
                elif msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        if data.get("type") == "audio":
                            yield base64.b64decode(data["data"])
                    except json.JSONDecodeError:
                        pass
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    break

            await ws.close()
        except Exception:
            pass


@router.post("/sessions", response_model=dict)
async def create_session(request: RealtimeSession):
    session = await create_realtime_session(
        request.model, request.modalities, request.instructions, request.voice
    )
    return session


@router.get("/sessions/{session_id}", response_model=dict)
async def get_session(session_id: str):
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return _sessions[session_id]


@router.get("/sessions")
async def list_sessions(limit: int = 50):
    sessions = sorted(_sessions.values(), key=lambda x: x["created_at"], reverse=True)
    return sessions[:limit]


@router.post("/sessions/{session_id}/messages")
async def add_message(session_id: str, message: RealtimeMessage):
    return await send_realtime_message(session_id, message.role, message.content, message.type)


@router.get("/sessions/{session_id}/transcript")
async def get_transcript(session_id: str, format: str = "text"):
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = _sessions[session_id]["messages"]

    if format == "text":
        transcript = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
    else:
        transcript = messages

    return {"transcript": transcript}


@router.websocket("/ws/{session_id}")
async def realtime_websocket(websocket: WebSocket, session_id: str):
    await websocket.accept()

    if session_id not in _sessions:
        await websocket.close(code=4004, reason="Session not found")
        return

    if session_id not in _active_connections:
        _active_connections[session_id] = []
    _active_connections[session_id].append(websocket)

    try:
        while True:
            data = await websocket.receive_json()

            msg_type = data.get("type", "message")

            if msg_type == "message":
                content = data.get("content", "")
                await send_realtime_message(session_id, "user", content)

                response_text = f"Echo: {content}"
                await websocket.send_json({"type": "message", "content": response_text})

            elif msg_type == "audio":
                await websocket.send_json({"type": "audio", "data": ""})

            elif msg_type == "interrupt":
                await websocket.send_json({"type": "interrupt", "status": "ok"})

    except WebSocketDisconnect:
        pass
    finally:
        if session_id in _active_connections:
            try:
                _active_connections[session_id].remove(websocket)
            except ValueError:
                pass


@router.post("/sessions/{session_id}/audio")
async def generate_audio(session_id: str, text: str):
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = _sessions[session_id]

    if "audio" not in session.get("modalities", []):
        raise HTTPException(status_code=400, detail="Audio modality not enabled")

    async def audio_generator():
        async for chunk in stream_audio_response(session_id, text):
            yield chunk

    return StreamingResponse(audio_generator(), media_type="audio/pcm")


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    del _sessions[session_id]

    if session_id in _active_connections:
        for ws in _active_connections[session_id]:
            await ws.close()
        del _active_connections[session_id]

    return {"status": "deleted", "session_id": session_id}


async def get_realtime_stats() -> dict:
    return {
        "sessions_count": len(_sessions),
        "active_connections": sum(len(conns) for conns in _active_connections.values()),
    }
