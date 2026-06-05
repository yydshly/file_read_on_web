"""Minimax provider — text chat (streaming SSE) + TTS.

Vision (MiniMax-VL-01) is wired but disabled by default; set
enable_vision=true in config to activate.

Docs (current as of 2026-06):
- Chat:  POST {base_url}/text/chatcompletion_v2  (SSE streaming via `stream=true`)
- TTS:   POST {base_url}/t2a_v2                  (returns audio bytes)

Required config fields:
- api_key      (string; supports ${ENV_VAR})
- group_id     (string; minimax tenant id)
- base_url     (default: https://api.minimaxi.com/v1)
- models.text  (default: MiniMax-Text-01)
- models.tts   (default: speech-01-turbo)
- enable_vision (default: false; current product does not wire Vision/OCR flow)
- models.vision  (optional; defaults to MiniMax-VL-01 only when enable_vision=true)
"""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator, Iterable

import httpx

from .base import (
    Capability,
    CapabilityNotSupported,
    LLMProvider,
    Message,
    ProviderConfigError,
    normalize_messages,
)

log = logging.getLogger("ai.minimax")

DEFAULT_BASE_URL = "https://api.minimaxi.com/v1"
DEFAULT_TEXT_MODEL = "MiniMax-Text-01"
DEFAULT_TTS_MODEL = "speech-01-turbo"
DEFAULT_VISION_MODEL = "MiniMax-VL-01"
DEFAULT_VOICE = "female-shaonv"


class MinimaxProvider(LLMProvider):
    type = "minimax"

    def __init__(self, config: dict):
        super().__init__(config)
        api_key = (self.config.get("api_key") or "").strip()
        if not api_key:
            raise ProviderConfigError("minimax: api_key 未配置")
        self.api_key = api_key
        self.group_id = (self.config.get("group_id") or "").strip()
        self.base_url = (self.config.get("base_url") or DEFAULT_BASE_URL).rstrip("/")
        models = self.config.get("models") or {}
        self.text_model = models.get("text", DEFAULT_TEXT_MODEL)
        self.tts_model = models.get("tts", DEFAULT_TTS_MODEL)
        self.enable_vision = bool(self.config.get("enable_vision", False))
        self.vision_model = models.get("vision") or (
            DEFAULT_VISION_MODEL if self.enable_vision else None
        )
        self.default_voice = self.config.get("default_voice", DEFAULT_VOICE)

        self.name = self.config.get("name") or "minimax"
        self.capabilities = {Capability.TEXT, Capability.TTS}
        if self.enable_vision and self.vision_model:
            self.capabilities.add(Capability.VISION)

    # ---- helpers ----

    def _auth_headers(self) -> dict:
        h = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        return h

    # ---- text chat ----

    async def chat(
        self,
        messages: Iterable[Message] | Iterable[dict],
        *,
        stream: bool = True,
        max_tokens: int = 2048,
        temperature: float = 0.6,
    ) -> AsyncIterator[str]:
        url = f"{self.base_url}/text/chatcompletion_v2"
        payload = {
            "model": self.text_model,
            "messages": normalize_messages(messages),
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": bool(stream),
        }
        timeout = httpx.Timeout(connect=10, read=120, write=30, pool=10)
        if not stream:
            async with httpx.AsyncClient(timeout=timeout) as cli:
                r = await cli.post(url, headers=self._auth_headers(), json=payload)
                r.raise_for_status()
                data = r.json()
                yield self._extract_text(data)
            return

        # Streamed SSE-like response: lines beginning with "data:".
        async with httpx.AsyncClient(timeout=timeout) as cli:
            async with cli.stream(
                "POST", url, headers=self._auth_headers(), json=payload
            ) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    raise RuntimeError(
                        f"minimax chat {resp.status_code}: "
                        f"{body.decode('utf-8', errors='ignore')[:500]}"
                    )
                buffer = ""
                async for chunk in resp.aiter_text():
                    buffer += chunk
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line or line.startswith(":"):
                            continue
                        if line.startswith("data:"):
                            payload_str = line[5:].strip()
                            if payload_str == "[DONE]":
                                return
                            try:
                                obj = json.loads(payload_str)
                            except json.JSONDecodeError:
                                continue
                            delta = self._extract_delta(obj)
                            if delta:
                                yield delta

    @staticmethod
    def _extract_delta(obj: dict) -> str:
        # Minimax v2 schema mirrors OpenAI: choices[0].delta.content
        try:
            choices = obj.get("choices") or []
            if not choices:
                return ""
            delta = choices[0].get("delta") or {}
            content = delta.get("content")
            if isinstance(content, str):
                return content
            # vision-style content list
            if isinstance(content, list):
                texts = []
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "text":
                        texts.append(c.get("text", ""))
                return "".join(texts)
        except Exception:
            return ""
        return ""

    @staticmethod
    def _extract_text(obj: dict) -> str:
        try:
            choices = obj.get("choices") or []
            if not choices:
                return ""
            msg = choices[0].get("message") or {}
            return msg.get("content", "") or ""
        except Exception:
            return ""

    # ---- TTS ----

    async def tts(
        self,
        text: str,
        *,
        voice: str | None = None,
        speed: float = 1.0,
    ) -> tuple[bytes, str]:
        url = f"{self.base_url}/t2a_v2"
        if self.group_id:
            url += f"?GroupId={self.group_id}"
        voice_id = voice or self.default_voice
        payload = {
            "model": self.tts_model,
            "text": text[:5000],
            "stream": False,
            "voice_setting": {
                "voice_id": voice_id,
                "speed": speed,
                "vol": 1.0,
                "pitch": 0,
            },
            "audio_setting": {
                "sample_rate": 32000,
                "bitrate": 128000,
                "format": "mp3",
                "channel": 1,
            },
        }
        timeout = httpx.Timeout(connect=10, read=60, write=30, pool=10)
        async with httpx.AsyncClient(timeout=timeout) as cli:
            r = await cli.post(url, headers=self._auth_headers(), json=payload)
            r.raise_for_status()
            data = r.json()
        # Minimax returns hex-encoded audio in data.audio
        audio_hex = (data.get("data") or {}).get("audio")
        if not audio_hex:
            base = data.get("base_resp") or {}
            raise RuntimeError(
                f"minimax tts 返回为空: status={base.get('status_code')} "
                f"msg={base.get('status_msg')}"
            )
        try:
            return bytes.fromhex(audio_hex), "audio/mpeg"
        except ValueError:
            raise RuntimeError("minimax tts 返回的不是有效 hex 音频")

    # ---- vision ----

    async def vision(
        self,
        image_bytes: bytes,
        prompt: str,
        *,
        mime: str = "image/jpeg",
    ) -> str:
        if Capability.VISION not in self.capabilities:
            raise CapabilityNotSupported("minimax: 未配置 vision 模型")
        import base64
        b64 = base64.b64encode(image_bytes).decode("ascii")
        url = f"{self.base_url}/text/chatcompletion_v2"
        payload = {
            "model": self.vision_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{b64}"},
                        },
                    ],
                }
            ],
            "stream": False,
            "max_tokens": 2048,
            "temperature": 0.1,
        }
        timeout = httpx.Timeout(connect=10, read=120, write=60, pool=10)
        async with httpx.AsyncClient(timeout=timeout) as cli:
            r = await cli.post(url, headers=self._auth_headers(), json=payload)
            r.raise_for_status()
            data = r.json()
        return self._extract_text(data)
