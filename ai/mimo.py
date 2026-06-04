"""Xiaomi MiMo provider.

Uses the MiMo open platform's /v1/chat/completions endpoint with audio output:
https://platform.xiaomimimo.com/docs/zh-CN/usage-guide/speech-synthesis-v2.5

Auth header is ``api-key: <KEY>`` (not Bearer). The text to synthesise is sent
as a chat user message; the response carries the audio in
``choices[0].message.audio.data`` as **base64-encoded bytes**.

Supported models / variants:
- ``mimo-v2.5-tts``               — preset voices (Chloe, etc.)
- ``mimo-v2.5-tts-voicedesign``   — describe voice in system prompt
- ``mimo-v2.5-tts-voiceclone``    — clone from a reference audio sample

Required config fields:
- ``api_key``      (string; supports ${ENV_VAR})

Optional config fields:
- ``base_url``     default https://api.xiaomimimo.com/v1
- ``models.tts``   default mimo-v2.5-tts
- ``default_voice`` default Chloe
- ``format``        wav | pcm16; default wav (browser-friendly)
- ``system_prompt``  optional system message — pass voice-style instructions
"""
from __future__ import annotations

import base64
import logging

import httpx

from .base import Capability, LLMProvider, ProviderConfigError

log = logging.getLogger("ai.mimo")

DEFAULT_BASE_URL  = "https://api.xiaomimimo.com/v1"
DEFAULT_TTS_MODEL = "mimo-v2.5-tts"
DEFAULT_VOICE     = "Chloe"
DEFAULT_FORMAT    = "wav"

_FORMAT_MIME = {
    "wav":   "audio/wav",
    "mp3":   "audio/mpeg",
    "pcm16": "audio/wav",   # raw PCM — browsers can't play directly, but kept for completeness
    "opus":  "audio/ogg",
}


class MimoProvider(LLMProvider):
    type = "mimo"

    def __init__(self, config: dict):
        super().__init__(config)
        api_key = (self.config.get("api_key") or "").strip()
        if not api_key:
            raise ProviderConfigError("mimo: api_key 未配置")
        self.api_key = api_key
        self.base_url = (self.config.get("base_url") or DEFAULT_BASE_URL).rstrip("/")
        models = self.config.get("models") or {}
        self.tts_model = models.get("tts", DEFAULT_TTS_MODEL)
        self.default_voice = self.config.get("default_voice", DEFAULT_VOICE)
        self.audio_format = self.config.get("format", DEFAULT_FORMAT)
        self.system_prompt = self.config.get("system_prompt") or ""
        self.name = self.config.get("name") or "mimo"
        self.capabilities = {Capability.TTS}

    def _headers(self) -> dict:
        # The MiMo platform exposes an OpenAI-compatible endpoint at
        # /v1/chat/completions, so the canonical auth is
        # ``Authorization: Bearer <key>`` (what the OpenAI SDK sends).
        # We also include the docs' alternate ``api-key`` header — some
        # MiMo gateway variants accept it. Sending both is safe; the server
        # uses whichever it recognises.
        return {
            "Authorization": f"Bearer {self.api_key}",
            "api-key": self.api_key,
            "Content-Type": "application/json",
        }

    async def tts(
        self,
        text: str,
        *,
        voice: str | None = None,
        speed: float = 1.0,
    ) -> tuple[bytes, str]:
        url = f"{self.base_url}/chat/completions"
        # MiMo's TTS-via-chat convention is unusual: the text to be
        # synthesised must be carried by an **assistant** role message.
        # ``system`` (and optionally ``user``) describe voice/style; their
        # content is NOT spoken. This matches the doc note:
        #   "...也可以是对话历史（消息内容不会出现在合成的语音中）"
        # and the upstream 400 error:
        #   "messages must contain an assistant role for TTS model".
        messages: list[dict] = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "assistant", "content": text[:5000]})

        payload = {
            "model": self.tts_model,
            "messages": messages,
            "audio": {
                "format": self.audio_format,
                "voice": voice or self.default_voice,
            },
        }
        # MiMo's API ignores 'speed' on the basic mimo-v2.5-tts model; you'd
        # use the voicedesign variant + describe pace in the system prompt to
        # control it. We keep the parameter so the LLMProvider interface stays
        # consistent.
        _ = speed

        timeout = httpx.Timeout(connect=10, read=120, write=60, pool=10)
        async with httpx.AsyncClient(timeout=timeout) as cli:
            r = await cli.post(url, headers=self._headers(), json=payload)
            if r.status_code == 401:
                raise RuntimeError(
                    "mimo tts 401 Unauthorized — 常见原因：\n"
                    " 1) MIMO_API_KEY 跟 MINIMAX_API_KEY 用了同一个值"
                    "（MiMo 是小米平台、Minimax 是另一家，两边的 key 不通用）\n"
                    " 2) key 复制时夹带了首尾空白/引号/换行\n"
                    " 3) key 在 https://platform.xiaomimimo.com/ 控制台已禁用/未激活\n"
                    " 4) 服务进程没读到最新环境变量（用 GET /api/ai/status 看 api_key_preview 验证）\n"
                    f"原始返回: {r.text[:300]}"
                )
            if r.status_code == 400:
                raise RuntimeError(
                    "mimo tts 400 Param Incorrect。请检查："
                    f" model={self.tts_model}, voice={voice or self.default_voice},"
                    f" format={self.audio_format}, text_len={len(text)}。"
                    f" 原始返回: {r.text[:400]}"
                )
            if r.status_code != 200:
                raise RuntimeError(
                    f"mimo tts {r.status_code}: {r.text[:400]}"
                )
            data = r.json()

        try:
            audio_b64 = data["choices"][0]["message"]["audio"]["data"]
        except (KeyError, IndexError, TypeError) as e:
            raise RuntimeError(
                f"mimo tts 响应结构异常: {e}; body[:300]={str(data)[:300]}"
            )

        try:
            audio_bytes = base64.b64decode(audio_b64)
        except Exception as e:
            raise RuntimeError(f"mimo tts base64 解码失败: {e}")

        mime = _FORMAT_MIME.get(self.audio_format, "application/octet-stream")
        return audio_bytes, mime
