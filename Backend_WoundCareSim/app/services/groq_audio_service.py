import base64
from typing import Optional

import httpx

from app.core.config import (
    GROQ_API_KEY,
    GROQ_STT_MODEL,
    GROQ_TTS_MODEL,
    GROQ_TTS_VOICE,
    GROQ_API_BASE_URL,
)


class GroqAudioService:
    def __init__(
        self,
        api_key: Optional[str] = None,
        stt_model: Optional[str] = None,
        tts_model: Optional[str] = None,
        tts_voice: Optional[str] = None,
    ) -> None:
        self.api_key = api_key or GROQ_API_KEY
        self.stt_model = stt_model or GROQ_STT_MODEL
        self.tts_model = tts_model or GROQ_TTS_MODEL
        self.tts_voice = tts_voice or GROQ_TTS_VOICE

    def _headers(self) -> dict:
        if not self.api_key:
            raise ValueError("GROQ_API_KEY is not configured")
        return {"Authorization": f"Bearer {self.api_key}"}

    async def transcribe_audio(self, filename: str, content: bytes, content_type: str) -> str:
        data = {"model": self.stt_model}
        files = {
            "file": (filename, content, content_type or "application/octet-stream")
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{GROQ_API_BASE_URL}/audio/transcriptions",
                headers=self._headers(),
                data=data,
                files=files,
            )
        response.raise_for_status()
        payload = response.json()
        return payload.get("text", "")

    async def text_to_speech(
        self,
        text: str,
        model: Optional[str] = None,
        voice: Optional[str] = None,
    ) -> dict:
        payload = {
            "model": model or self.tts_model,
            "input": text,
            "voice": voice or self.tts_voice,
            "response_format": "wav",
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{GROQ_API_BASE_URL}/audio/speech",
                headers=self._headers(),
                json=payload,
            )
        response.raise_for_status()
        audio_base64 = base64.b64encode(response.content).decode("utf-8")
        return {
            "audio_base64": audio_base64,
            "content_type": response.headers.get("content-type", "audio/mpeg"),
        }
