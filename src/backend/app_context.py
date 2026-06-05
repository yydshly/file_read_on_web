"""Central application context for shared runtime dependencies and mutable state."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass
class AppPaths:
    """Immutable path constants for the application."""
    app_dir: Path
    data_dir: Path
    resource_dir: Path
    static_dir: Path
    cache_dir: Path
    tts_cache_dir: Path
    config_path: Path
    state_path: Path
    anno_path: Path
    search_index_path: Path
    default_root_rel: str


@dataclass
class AppContext:
    """Central context for shared runtime dependencies and mutable application state.

    Single source of truth for:
    - root: current data root directory (may be None)
    - preconvert_enabled: whether background preconvert is active
    - ai_text_provider: active text AI provider
    - ai_tts_provider: active TTS AI provider
    - anno_store: annotation persistence
    - state_store: runtime state persistence
    - tts_cache: TTS audio cache
    - ai_doc_service: AI document processing service
    - tray_controller: system tray controller
    """
    paths: AppPaths

    # Services (already instantiated before ctx creation)
    anno_store: Any
    state_store: Any
    tts_cache: Any
    ai_doc_service: Any

    # Mutable runtime state
    root: Optional[Path] = None
    preconvert_enabled: bool = True

    # AI providers (set during main())
    ai_text_provider: Any = None
    ai_tts_provider: Any = None

    # Tray controller (set during main())
    tray_controller: Any = None
