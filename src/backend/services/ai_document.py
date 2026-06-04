"""AI application-service module.

Owns:
- AI document eligibility rules
- AI document loading rules
- AI document text extraction orchestration
- AI status / masked credential helper logic
- AI thresholds
- user-facing unsupported-file messages for AI text flow
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException

from src.backend.services import converter
from src.backend.services import search as search_mod
from src.ai import factory as ai_factory

AI_TEXT_HARD_LIMIT_CHARS = 1_400_000   # ~500K tokens at avg 2.8 chars/token
AI_TEXT_SOFT_LIMIT_CHARS = 280_000     # ~100K tokens — above this we do summarize-first


class AiDocumentService:
    """Owns AI document eligibility checking and text extraction."""

    def __init__(
        self,
        cache_dir: Path,
        hard_limit_chars: int = AI_TEXT_HARD_LIMIT_CHARS,
        soft_limit_chars: int = AI_TEXT_SOFT_LIMIT_CHARS,
    ):
        self._cache_dir = cache_dir
        self._hard_limit = hard_limit_chars
        self._soft_limit = soft_limit_chars

    async def eligibility(self, src: Path, rel_path: str) -> dict:
        """Return AI eligibility info for the given file.

        Mirrors the behaviour of the former ``api_file_ai_eligibility`` route.
        Raises ``HTTPException`` for root/path errors before reaching here.
        """
        info: dict[str, Any] = {
            "path": rel_path,
            "supported": True,
            "mode": "direct",
            "reasons": [],
            "char_count": 0,
            "is_scanned": False,
        }
        kind = converter.classify(src)
        if kind == "image":
            info["supported"] = False
            info["mode"] = "vision_required"
            info["reasons"].append(
                "图片当前仅支持预览，暂不支持 AI 整理 / 问答。"
                "未来可作为 Vision/OCR 扩展能力评估。"
            )
            return info
        if kind == "unsupported":
            info["supported"] = False
            info["mode"] = "unsupported"
            info["reasons"].append(f"不支持的文件类型：{src.suffix}")
            return info

        if kind in ("pdf", "office", "markdown", "text"):
            # CPU-bound (pypdf extraction); run off the event loop.
            loop = asyncio.get_running_loop()
            text = await loop.run_in_executor(
                None, search_mod.get_indexed_text, src, self._cache_dir
            )
            info["char_count"] = len(text)
            if kind == "pdf" and search_mod.is_scanned(src):
                info["supported"] = False
                info["is_scanned"] = True
                info["mode"] = "unsupported"
                info["reasons"].append(
                    "扫描版 PDF 无文本层，当前仅支持预览，暂不支持 AI 整理 / 问答。"
                    "未来可作为 Vision/OCR 扩展能力评估。"
                )
                return info
            if not text.strip():
                if kind == "office":
                    info["mode"] = "needs_conversion"
                    info["reasons"].append(
                        "首次使用时需要先转换为 PDF（首条 AI 请求会触发，约 3-15s）"
                    )
                    return info
                info["supported"] = False
                info["mode"] = "unsupported"
                info["reasons"].append("尚未索引到任何文本内容（可能预转换/索引还没跑完）")
                return info
            if info["char_count"] > self._hard_limit:
                info["supported"] = False
                info["mode"] = "unsupported"
                info["reasons"].append(
                    f"文档过大（{info['char_count']:,} 字符 > {self._hard_limit:,}），"
                    "未来可作为 RAG/切分检索能力评估"
                )
                return info
            if info["char_count"] > self._soft_limit:
                info["mode"] = "summarize_first"
                info["reasons"].append(
                    f"文档较长（{info['char_count']:,} 字符），将先生成结构化摘要，"
                    "后续问答基于摘要 + 检索片段"
                )
        return info

    async def load_document(self, src: Path) -> tuple[Path, str]:
        """Resolve a file and return (Path, indexed text).

        Raises ``HTTPException`` with a clear reason if AI features are
        unavailable for this file.  For office files this awaits
        ``office_to_pdf`` if needed — extraction relies on the converted PDF
        being present in cache.
        """
        if src.is_dir():
            raise HTTPException(400, "path is a directory")
        kind = converter.classify(src)
        if kind == "image":
            raise HTTPException(
                400,
                "图片当前仅支持预览，暂不支持 AI 整理 / 问答。"
                "未来可作为 Vision/OCR 扩展能力评估。",
            )
        if kind == "unsupported":
            raise HTTPException(400, f"不支持的文件类型：{src.suffix}")
        if kind == "pdf" and search_mod.is_scanned(src):
            raise HTTPException(
                422,
                "扫描版 PDF 无文本层，当前仅支持预览，暂不支持 AI 整理 / 问答。"
                "未来可作为 Vision/OCR 扩展能力评估。",
            )

        # Office: ensure the converted PDF exists before we try to read text.
        if kind == "office":
            try:
                await converter.office_to_pdf(src, self._cache_dir)
            except RuntimeError as e:
                raise HTTPException(
                    422, f"该 office 文件无法转换为 PDF，AI 不可用：{e}"
                )

        # HOTFIX-LOCAL-RESPONSIVENESS-V1 #1 continuation:
        # Offload text extraction so a large uncached PDF does not block the
        # event loop for 10-30s.
        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(
            None, search_mod.get_indexed_text, src, self._cache_dir
        )
        if kind == "pdf" and (search_mod.is_scanned(src) or not text.strip()):
            raise HTTPException(
                422,
                "扫描版 PDF 没有可提取的文本层，暂不支持 AI 整理 / 对话。"
                "请先通过 OCR 转成可复制文本后再使用。",
            )
        if not text.strip():
            raise HTTPException(422, "文档尚未索引到文本（预转换 / 索引可能还没跑完）")
        if len(text) > self._hard_limit:
            raise HTTPException(
                413,
                f"文档过大（{len(text):,} 字符 > {self._hard_limit:,}）；"
                "未来可作为 RAG/切分检索能力评估。",
            )
        return src, text

    def thresholds(self) -> dict:
        return {
            "hard_limit_chars": self._hard_limit,
            "soft_limit_chars": self._soft_limit,
        }


def mask_key(k: Optional[str]) -> str:
    """Return a human-readable masked preview of an API key."""
    if not k:
        return "(empty)"
    k = str(k)
    if len(k) <= 8:
        return "*" * len(k)
    return f"{k[:4]}…{k[-4:]} (len={len(k)})"


def build_ai_status(text_provider: Any, tts_provider: Any) -> dict:
    """Build the ``/api/ai/status`` response payload.

    Returns provider info with masked credential previews, available provider
    types, AI thresholds, and masked environment-variable previews.
    """
    text_info = text_provider.info() if text_provider else None
    tts_info = tts_provider.info() if tts_provider else None
    if text_info and hasattr(text_provider, "api_key"):
        text_info["api_key_preview"] = mask_key(text_provider.api_key)
        if hasattr(text_provider, "group_id"):
            text_info["group_id_preview"] = mask_key(getattr(text_provider, "group_id", ""))
    if tts_info and hasattr(tts_provider, "api_key"):
        tts_info["api_key_preview"] = mask_key(tts_provider.api_key)
        if hasattr(tts_provider, "group_id"):
            tts_info["group_id_preview"] = mask_key(getattr(tts_provider, "group_id", ""))
        if hasattr(tts_provider, "base_url"):
            tts_info["base_url"] = getattr(tts_provider, "base_url")
    env_seen = {}
    for k in ("MINIMAX_API_KEY", "MINIMAX_GROUP_ID", "MIMO_API_KEY"):
        env_seen[k] = mask_key(os.environ.get(k))
    return {
        "text": text_info,
        "tts": tts_info,
        "providers_available": ai_factory.available_provider_types(),
        "thresholds": {
            "hard_limit_chars": AI_TEXT_HARD_LIMIT_CHARS,
            "soft_limit_chars": AI_TEXT_SOFT_LIMIT_CHARS,
        },
        "env": env_seen,
    }
