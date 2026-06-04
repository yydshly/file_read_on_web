"""Provider registry & factory.

Add a new provider by importing its class and adding an entry to ``_REGISTRY``.
The active provider (if any) is selected by ``config["ai"]["active"]``;
``tts_provider`` may override TTS specifically.
"""
from __future__ import annotations

import logging
from typing import Optional

from .base import LLMProvider, ProviderConfigError
from .minimax import MinimaxProvider
from .minimax_anthropic import MinimaxAnthropicProvider
from .mimo import MimoProvider

log = logging.getLogger("ai.factory")

_REGISTRY: dict[str, type[LLMProvider]] = {
    "minimax": MinimaxProvider,
    "minimax_anthropic": MinimaxAnthropicProvider,
    "mimo": MimoProvider,
}


def available_provider_types() -> list[str]:
    return sorted(_REGISTRY.keys())


def make_provider(provider_name: str, ai_config: dict) -> LLMProvider:
    """Instantiate the provider named ``provider_name`` from the ``ai`` section
    of config. Raises ``ProviderConfigError`` on missing/invalid config."""
    providers = (ai_config or {}).get("providers") or {}
    cfg = providers.get(provider_name)
    if cfg is None:
        raise ProviderConfigError(
            f"未在 config.ai.providers 中找到 '{provider_name}'"
        )
    ptype = cfg.get("type") or provider_name
    cls = _REGISTRY.get(ptype)
    if cls is None:
        raise ProviderConfigError(
            f"未知 provider type '{ptype}'，可用：{available_provider_types()}"
        )
    return cls(cfg)


def make_active(ai_config: dict) -> Optional[LLMProvider]:
    """Build the active text provider; returns None if AI is not configured."""
    if not ai_config:
        return None
    active = ai_config.get("active")
    if not active:
        return None
    try:
        return make_provider(active, ai_config)
    except ProviderConfigError as e:
        log.warning("AI text provider 未启用: %s", e)
        return None


def make_tts(ai_config: dict) -> Optional[LLMProvider]:
    """Build the TTS provider. Falls back to the active provider if it supports
    TTS; otherwise tries ``ai.tts_provider`` explicitly."""
    if not ai_config:
        return None
    tts_name = ai_config.get("tts_provider")
    if tts_name:
        try:
            return make_provider(tts_name, ai_config)
        except ProviderConfigError as e:
            log.warning("AI tts_provider 未启用: %s", e)
            return None
    # Fallback to active if it supports TTS.
    p = make_active(ai_config)
    if p is not None and "tts" in p.capabilities:
        return p
    return None
