import asyncio
import base64
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiohttp
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/tts", tags=["tts"])


class TTSRequest(BaseModel):
    input: str
    model: str = "tts-1"
    voice: str = "alloy"
    response_format: str = "mp3"
    speed: float = 1.0


class TTSResponse(BaseModel):
    audio_base64: Optional[str] = None
    model: str
    voice: str
    duration_ms: int


class VoiceListResponse(BaseModel):
    voices: list[dict]


TTS_STORAGE_PATH = Path("/tmp/atra_tts")
TTS_STORAGE_PATH.mkdir(exist_ok=True)


VOICES = {
    "alloy": {"id": "alloy", "name": "Alloy", "gender": "neutral"},
    "echo": {"id": "echo", "name": "Echo", "gender": "neutral"},
    "fable": {"id": "fable", "name": "Fable", "gender": "male"},
    "onyx": {"id": "onyx", "name": "Onyx", "gender": "male"},
    "nova": {"id": "nova", "name": "Nova", "gender": "female"},
    "shimmer": {"id": "shimmer", "name": "Shimmer", "gender": "female"},
    "ballad": {"id": "ballad", "name": "Ballad", "gender": "neutral"},
    "sage": {"id": "sage", "name": "Sage", "gender": "neutral"},
}


MODELS = {
    "tts-1": {"id": "tts-1", "name": "OpenAI TTS", "quality": "standard"},
    "tts-1-hd": {"id": "tts-1-hd", "name": "OpenAI TTS HD", "quality": "high"},
    "gpt-4o-mini-tts": {"id": "gpt-4o-mini-tts", "name": "GPT-4o Mini TTS", "quality": "ultra"},
}


async def generate_speech_openai(
    text: str,
    model: str = "tts-1",
    voice: str = "alloy",
    response_format: str = "mp3",
    speed: float = 1.0,
) -> bytes:
    api_key = "NOT_SET"
    if not api_key or api_key == "NOT_SET":
        raise HTTPException(status_code=503, detail="TTS API key not configured")

    url = "https://api.openai.com/v1/audio/speech"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {
        "model": model,
        "input": text,
        "voice": voice,
        "response_format": response_format,
        "speed": speed,
    }

    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, json=data, headers=headers) as resp:
            if resp.status != 200:
                raise HTTPException(status_code=resp.status, detail="TTS generation failed")
            return await resp.read()


async def generate_speech_coqui(text: str, voice: str = "alloy") -> bytes:
    url = "http://localhost:5002/generate"
    data = {"text": text, "voice_id": voice}

    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, json=data) as resp:
            if resp.status != 200:
                raise HTTPException(status_code=503, detail="Coqui TTS unavailable")
            return await resp.read()


async def generate_speech_edge_tts(text: str) -> bytes:
    url = "https://speech.platform.bing.microsoft.com/cgs/recognition/https://api.platform.binaurang.azure.com/webses/v2.0/engines/2.0"
    headers = {"Content-Type": "application/json"}
    data = {"text": text, "voice": "en-US-AriaNeural"}

    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, json=data, headers=headers) as resp:
            if resp.status != 200:
                raise HTTPException(status_code=503, detail="Edge TTS unavailable")
            return await resp.read()


@router.post("/generate", response_model=TTSResponse)
async def generate_speech(request: TTSRequest):
    try:
        audio_data = await generate_speech_openai(
            request.input, request.model, request.voice, request.response_format, request.speed
        )
    except HTTPException:
        try:
            audio_data = await generate_speech_coqui(request.input, request.voice)
        except HTTPException:
            audio_data = await generate_speech_edge_tts(request.input)

    audio_base64 = base64.b64encode(audio_data).decode("utf-8")

    return TTSResponse(
        audio_base64=audio_base64,
        model=request.model,
        voice=request.voice,
        duration_ms=len(audio_data) * 8,
    )


@router.get("/voices", response_model=VoiceListResponse)
async def list_voices():
    return VoiceListResponse(voices=list(VOICES.values()))


@router.get("/models")
async def list_models():
    return {"models": list(MODELS.values())}


@router.post("/speak")
async def speak_text(text: str, voice: str = "alloy", model: str = "tts-1"):
    if text.length > 4096:
        raise HTTPException(status_code=400, detail="Text exceeds 4096 characters")

    if voice not in VOICES:
        raise HTTPException(status_code=400, detail=f"Voice {voice} not found")

    try:
        audio_data = await generate_speech_openai(text, model, voice)
    except HTTPException:
        try:
            audio_data = await generate_speech_coqui(text, voice)
        except HTTPException:
            raise HTTPException(status_code=503, detail="All TTS backends unavailable")

    output_path = TTS_STORAGE_PATH / f"{uuid.uuid4().hex}.mp3"
    output_path.write_bytes(audio_data)

    return {
        "audio_path": str(output_path),
        "duration_ms": len(audio_data) * 8,
        "voice": voice,
        "model": model,
    }


async def get_tts_processor() -> dict:
    return {"voices": VOICES, "models": MODELS, "storage_path": str(TTS_STORAGE_PATH)}
