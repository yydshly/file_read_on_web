"""LLM provider base class + shared types/exceptions."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import AsyncIterator, Iterable


class Capability:
    TEXT = "text"        # async chat(messages) -> stream of text deltas
    VISION = "vision"    # async vision(image_bytes, prompt) -> str
    TTS = "tts"          # async tts(text) -> bytes (audio)
    ASR = "asr"          # async asr(audio_bytes) -> str


class ProviderConfigError(Exception):
    """Raised when a provider is asked to start without the necessary config."""


class CapabilityNotSupported(Exception):
    """Raised when a caller asks a provider to do something it doesn't do."""


@dataclass
class Message:
    role: str   # "system" | "user" | "assistant"
    content: str


_ENV_RE = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")


def expand_env(value):
    """Recursively expand ``${VAR}`` references against ``os.environ``.
    Used so configs can keep API keys out of the JSON file."""
    if isinstance(value, str):
        return _ENV_RE.sub(lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, dict):
        return {k: expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [expand_env(v) for v in value]
    return value


class LLMProvider:
    """All providers conform to this interface. Override only the capabilities
    you support; unsupported ones raise ``CapabilityNotSupported`` by default."""

    name: str = "base"
    type: str = "base"
    capabilities: set[str] = set()

    def __init__(self, config: dict):
        self.config = expand_env(config or {})

    # ---- text ----

    async def chat(
        self,
        messages: Iterable[Message] | Iterable[dict],
        *,
        stream: bool = True,
        max_tokens: int = 2048,
        temperature: float = 0.6,
    ) -> AsyncIterator[str]:
        raise CapabilityNotSupported(f"{self.name} 不支持 text chat")
        yield ""  # pragma: no cover  - make this a generator regardless

    # ---- vision ----

    async def vision(
        self,
        image_bytes: bytes,
        prompt: str,
        *,
        mime: str = "image/jpeg",
    ) -> str:
        raise CapabilityNotSupported(f"{self.name} 不支持 vision")

    # ---- tts ----

    async def tts(
        self,
        text: str,
        *,
        voice: str | None = None,
        speed: float = 1.0,
    ) -> tuple[bytes, str]:
        """Return (audio_bytes, mime_type). Common mimes: audio/mpeg, audio/wav."""
        raise CapabilityNotSupported(f"{self.name} 不支持 TTS")

    # ---- asr ----

    async def asr(self, audio_bytes: bytes, *, mime: str = "audio/wav") -> str:
        raise CapabilityNotSupported(f"{self.name} 不支持 ASR")

    # ---- introspection ----

    def supports(self, cap: str) -> bool:
        return cap in self.capabilities

    def info(self) -> dict:
        return {
            "name": self.name,
            "type": self.type,
            "capabilities": sorted(self.capabilities),
        }


def normalize_messages(messages: Iterable[Message] | Iterable[dict]) -> list[dict]:
    """Convert Message objects or dicts to plain ``{role, content}`` dicts."""
    out: list[dict] = []
    for m in messages:
        if isinstance(m, Message):
            out.append({"role": m.role, "content": m.content})
        elif isinstance(m, dict) and "role" in m and "content" in m:
            out.append({"role": m["role"], "content": m["content"]})
        else:
            raise ValueError(f"invalid message: {m!r}")
    return out
