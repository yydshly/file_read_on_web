"""Minimax provider via the Anthropic-compatible Messages API.

This is a separate provider from ``minimax.py``:
- ``minimax`` uses Minimax's native API (chatcompletion_v2 + t2a_v2 + VL).
  Use it for TTS / vision.
- ``minimax_anthropic`` (this module) speaks the Anthropic Messages API
  protocol. Use it for the **M2 / M2.7 / M3** family text models (including
  the ``MiniMax-M2.7-highspeed`` model the user asked for).

Endpoint (from official docs https://platform.minimaxi.com/docs/api-reference/text-anthropic-api):
    POST https://api.minimaxi.com/anthropic/v1/messages

Authentication is the standard Anthropic style:
    x-api-key: <your-key>
    anthropic-version: 2023-06-01

Request body fields fully supported:
    model, messages, max_tokens, stream, system, temperature,
    tool_choice, tools, top_p, thinking, metadata

Ignored: top_k, stop_sequences, mcp_servers, context_management, container.
"""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator, Iterable

import httpx

from .base import (
    Capability,
    LLMProvider,
    Message,
    ProviderConfigError,
    normalize_messages,
)

log = logging.getLogger("ai.minimax_anthropic")

DEFAULT_BASE_URL = "https://api.minimaxi.com/anthropic"
DEFAULT_MODEL = "MiniMax-M2.7-highspeed"
DEFAULT_ANTHROPIC_VERSION = "2023-06-01"


class MinimaxAnthropicProvider(LLMProvider):
    type = "minimax_anthropic"

    def __init__(self, config: dict):
        super().__init__(config)
        api_key = (self.config.get("api_key") or "").strip()
        if not api_key:
            raise ProviderConfigError("minimax_anthropic: api_key 未配置")
        self.api_key = api_key
        self.base_url = (self.config.get("base_url") or DEFAULT_BASE_URL).rstrip("/")
        models = self.config.get("models") or {}
        self.model = models.get("text") or self.config.get("model") or DEFAULT_MODEL
        self.anthropic_version = (
            self.config.get("anthropic_version") or DEFAULT_ANTHROPIC_VERSION
        )
        self.name = self.config.get("name") or "minimax-anthropic"
        # Anthropic-compatible endpoint is text-only on Minimax's side
        # (vision/tts use the other endpoints — see minimax.py).
        self.capabilities = {Capability.TEXT}

    # ---- helpers ----

    def _headers(self) -> dict:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": self.anthropic_version,
            "Content-Type": "application/json",
        }

    def _build_payload(
        self,
        messages: list[dict],
        *,
        stream: bool,
        max_tokens: int,
        temperature: float,
    ) -> dict:
        # Anthropic Messages API puts system prompts in a top-level "system"
        # field, NOT inside the messages list. Split them out.
        system_texts: list[str] = []
        chat_msgs: list[dict] = []
        for m in messages:
            if m["role"] == "system":
                if m.get("content"):
                    system_texts.append(m["content"])
            else:
                # Anthropic only accepts "user" / "assistant"; anything else
                # we coerce to "user" rather than 500 the request.
                role = m["role"] if m["role"] in ("user", "assistant") else "user"
                chat_msgs.append({"role": role, "content": m["content"]})

        # Anthropic requires alternating user/assistant and must start with user.
        # Our prompts (see ai/tasks.py) already do this, but be defensive.
        chat_msgs = _coerce_alternating(chat_msgs)

        payload: dict = {
            "model": self.model,
            "messages": chat_msgs,
            "max_tokens": int(max_tokens),
            "stream": bool(stream),
            "temperature": float(temperature),
        }
        if system_texts:
            payload["system"] = "\n\n".join(system_texts)
        return payload

    # ---- chat ----

    async def chat(
        self,
        messages: Iterable[Message] | Iterable[dict],
        *,
        stream: bool = True,
        max_tokens: int = 2048,
        temperature: float = 0.6,
    ) -> AsyncIterator[str]:
        url = f"{self.base_url}/v1/messages"
        payload = self._build_payload(
            normalize_messages(messages),
            stream=stream,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        timeout = httpx.Timeout(connect=10, read=120, write=30, pool=10)
        if not stream:
            async with httpx.AsyncClient(timeout=timeout) as cli:
                r = await cli.post(url, headers=self._headers(), json=payload)
                if r.status_code != 200:
                    raise RuntimeError(
                        f"minimax_anthropic {r.status_code}: {r.text[:500]}"
                    )
                data = r.json()
                yield _extract_full_text(data)
            return

        # Anthropic SSE: lines come in `event: ...` / `data: ...` pairs.
        # Only the data lines carry JSON; we only care about
        # `content_block_delta` events whose delta has type=text_delta.
        async with httpx.AsyncClient(timeout=timeout) as cli:
            async with cli.stream(
                "POST", url, headers=self._headers(), json=payload
            ) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    raise RuntimeError(
                        f"minimax_anthropic {resp.status_code}: "
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
                        if line.startswith("event:"):
                            # we don't act on event types directly; the
                            # following data line carries the same type
                            continue
                        if line.startswith("data:"):
                            payload_str = line[5:].strip()
                            if not payload_str or payload_str == "[DONE]":
                                continue
                            try:
                                obj = json.loads(payload_str)
                            except json.JSONDecodeError:
                                continue
                            delta = _extract_stream_delta(obj)
                            if delta:
                                yield delta
                            # message_stop signals end; we just let the
                            # stream close naturally afterwards.


# ---------- module helpers ----------

def _coerce_alternating(msgs: list[dict]) -> list[dict]:
    """Anthropic requires messages to alternate user/assistant and start
    with a user message. Merge consecutive same-role messages and prepend
    an empty user if needed."""
    if not msgs:
        return msgs
    merged: list[dict] = []
    for m in msgs:
        if merged and merged[-1]["role"] == m["role"]:
            merged[-1]["content"] = (merged[-1]["content"] or "") + "\n\n" + (m["content"] or "")
        else:
            merged.append({"role": m["role"], "content": m["content"]})
    if merged[0]["role"] != "user":
        merged.insert(0, {"role": "user", "content": "(继续)"})
    return merged


def _extract_full_text(obj: dict) -> str:
    content = obj.get("content") or []
    parts = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts)


def _extract_stream_delta(obj: dict) -> str:
    """Anthropic SSE schema (relevant subset):
      {"type":"content_block_delta","index":0,
       "delta":{"type":"text_delta","text":"..."}}
    We ignore other event types (message_start, content_block_start,
    content_block_stop, message_delta, message_stop, ping).
    """
    if obj.get("type") != "content_block_delta":
        return ""
    d = obj.get("delta") or {}
    if d.get("type") == "text_delta":
        return d.get("text", "") or ""
    return ""
