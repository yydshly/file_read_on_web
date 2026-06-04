"""LLM provider abstraction.

Public surface:
- LLMProvider, Capability, CapabilityNotSupported, ProviderConfigError
- make_provider(config) → LLMProvider instance built from config dict
- get_default_provider() / set_default_provider()
- High-level tasks via src.ai.tasks (summarize_document, chat_about_document, ...)

Adding a new provider:
1. Subclass LLMProvider in a new module (e.g. src/ai/foo.py)
2. Register it in src/ai/factory.py:_REGISTRY = {"foo": FooProvider, ...}
3. Add a `providers.foo` block in config.json
"""
from .base import (
    Capability,
    CapabilityNotSupported,
    LLMProvider,
    Message,
    ProviderConfigError,
)
from .factory import make_provider, available_provider_types

__all__ = [
    "Capability",
    "CapabilityNotSupported",
    "LLMProvider",
    "Message",
    "ProviderConfigError",
    "make_provider",
    "available_provider_types",
]
