"""AI routes: /api/file/ai-eligibility, /api/ai/*."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.ai import tasks as ai_tasks
from src.ai.base import Message as AIMessage, CapabilityNotSupported
from src.backend.app_context import AppContext
from src.backend.infra.logging_setup import get_logger
from src.backend.services.ai_document import build_ai_status


class AiChatBody(BaseModel):
    path: str
    question: str
    history: list[dict] = []   # list of {role, content}
    summarize_first: bool = False
    stream: bool = True


class AiSummarizeBody(BaseModel):
    path: str
    force: bool = False        # ignore cached ai_summary in annotations
    stream: bool = True


class AiTtsBody(BaseModel):
    text: str
    voice: str | None = None
    speed: float = 1.0


def create_ai_router(
    ctx: AppContext,
    *,
    require_root: Callable[[], Path],
    safe_resolve: Callable[[str], Path],
) -> APIRouter:
    """Create the AI router for AI endpoints."""
    router = APIRouter()

    async def _ai_anno_patch_async(root: Path, rel_path: str, partial: dict) -> dict:
        """Offload annotation JSON write from async handlers to avoid blocking the event loop."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: ctx.anno_store.patch(root, rel_path, partial),
        )

    def _ai_require_text() -> Any:
        if ctx.ai_text_provider is None:
            raise HTTPException(503, "AI 未启用：请在 config.json.ai 中配置 active provider")
        return ctx.ai_text_provider

    def _ai_require_tts() -> Any:
        if ctx.ai_tts_provider is None:
            raise HTTPException(503, "AI TTS 未启用：请配置 ai.tts_provider 或让 active provider 支持 TTS")
        return ctx.ai_tts_provider

    def _sse_stream(token_iter):
        """Wrap an async iterator of text deltas in Server-Sent-Events frames."""
        async def gen():
            try:
                async for item in token_iter:
                    if not item:
                        continue
                    if isinstance(item, dict):
                        payload = json.dumps(item, ensure_ascii=False)
                        yield f"data: {payload}\n\n"
                        continue
                    delta = item
                    payload = json.dumps({"delta": delta}, ensure_ascii=False)
                    yield f"data: {payload}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                err = json.dumps({"error": str(e)}, ensure_ascii=False)
                yield f"data: {err}\n\n"
                yield "data: [DONE]\n\n"
        return StreamingResponse(gen(), media_type="text/event-stream")

    @router.get("/api/file/ai-eligibility")
    async def api_file_ai_eligibility(path: str = Query(...)):
        """Tell the UI whether AI features apply to this file and why not."""
        require_root()
        src = safe_resolve(path)
        return await ctx.ai_doc_service.eligibility(src, path)

    @router.get("/api/ai/status")
    def api_ai_status():
        """Status + masked credential preview so users can verify the running
        process actually picked up their env vars."""
        return build_ai_status(ctx.ai_text_provider, ctx.ai_tts_provider)

    @router.post("/api/ai/summarize")
    async def api_ai_summarize(body: AiSummarizeBody):
        provider = _ai_require_text()

        async def run_stream():
            yield {"stage": "准备文档"}
            src = safe_resolve(body.path)
            src, text = await ctx.ai_doc_service.load_document(src)
            root = require_root()
            rel = body.path

            if not body.force:
                yield {"stage": "检查已生成摘要"}
                anno = ctx.anno_store.get(root, rel)
                cached = (anno or {}).get("ai_summary")
                if cached:
                    yield {"stage": "使用已生成摘要", "cached": True}
                    yield cached
                    return

            yield {"stage": "AI 正在整理文档"}
            chunks = []
            async for d in ai_tasks.summarize_document(provider, src.name, text):
                chunks.append(d)
                yield d

            full = "".join(chunks).strip()
            if full:
                yield {"stage": "保存生成结果"}
                await _ai_anno_patch_async(root, rel, {"ai_summary": full})

        if body.stream:
            return _sse_stream(run_stream())

        src = safe_resolve(body.path)
        src, text = await ctx.ai_doc_service.load_document(src)
        root = require_root()
        rel = body.path
        if not body.force:
            anno = ctx.anno_store.get(root, rel)
            cached = (anno or {}).get("ai_summary")
            if cached:
                return {"summary": cached, "cached": True}

        full = ""
        async for d in ai_tasks.summarize_document(provider, src.name, text):
            full += d
        if full.strip():
            await _ai_anno_patch_async(root, rel, {"ai_summary": full.strip()})
        return {"summary": full, "cached": False}

    @router.post("/api/ai/chat")
    async def api_ai_chat(body: AiChatBody):
        provider = _ai_require_text()
        src = safe_resolve(body.path)
        src, text = await ctx.ai_doc_service.load_document(src)
        history = [AIMessage(role=m["role"], content=m["content"]) for m in body.history
                   if m.get("role") in {"user", "assistant"} and m.get("content")]

        async def run():
            async for d in ai_tasks.chat_about_document(
                provider, src.name, text, history, body.question
            ):
                yield d

        if body.stream:
            return _sse_stream(run())

        full = ""
        async for d in run():
            full += d
        return {"answer": full}

    @router.post("/api/ai/tts")
    async def api_ai_tts(body: AiTtsBody):
        """HOTFIX-LOCAL-RESPONSIVENESS-V1 #3:
        Cache read / write are blocking file IO (audio can be multi-MB).
        Offload them to the default executor so they don't stall the async
        event loop while other AI requests are in flight.

        HOTFIX-MIGRATION-TTS-CLEANUP-V1 Fix C:
        Normalise the effective text once (cap at TtsCache.TEXT_LIMIT_CHARS) so
        cache lookup, provider call, and cache write all hash / synthesise
        the same bytes. Inputs that differ only beyond the cap now collapse
        to a single cache entry instead of wasting storage and missing the
        cache.
        """
        provider = _ai_require_tts()
        raw_text = body.text
        if not raw_text.strip():
            raise HTTPException(400, "text 不能为空")
        tts_text = ctx.tts_cache.normalize_text(raw_text)
        loop = asyncio.get_running_loop()

        # 1) Try local cache first — same text/voice/speed = same audio.
        hit = await loop.run_in_executor(
            None,
            lambda: ctx.tts_cache.get(provider.name, tts_text, body.voice, body.speed),
        )
        if hit is not None:
            audio, mime = hit
            return Response(content=audio, media_type=mime,
                            headers={"X-TTS-Cache": "hit"})

        # 2) Cache miss — call the provider.
        try:
            result = await provider.tts(tts_text, voice=body.voice, speed=body.speed)
        except CapabilityNotSupported as e:
            raise HTTPException(400, str(e))
        except Exception as e:
            get_logger("ai").exception("TTS 失败")
            raise HTTPException(502, f"TTS 失败：{e}")

        # Providers return (bytes, mime). Tolerate old bytes-only too.
        if isinstance(result, tuple) and len(result) == 2:
            audio, mime = result
        else:
            audio, mime = result, "audio/mpeg"

        # 3) Save to disk for next time (off the event loop).
        await loop.run_in_executor(
            None,
            lambda: ctx.tts_cache.put(provider.name, tts_text, body.voice, body.speed,
                                  audio, mime),
        )

        return Response(content=audio, media_type=mime,
                        headers={"X-TTS-Cache": "miss"})

    @router.get("/api/ai/tts/stats")
    def api_ai_tts_stats():
        """Kept for backwards-compat; the unified /api/cache/stats is preferred."""
        return ctx.tts_cache.stats()

    @router.post("/api/ai/tts/clear")
    def api_ai_tts_clear():
        return ctx.tts_cache.clear()

    return router
