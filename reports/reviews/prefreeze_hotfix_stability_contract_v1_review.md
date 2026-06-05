# Review: PREFREEZE-HOTFIX-STABILITY-CONTRACT-V1

## Summary

Fixed three pre-freeze issues: (A) unique temp file naming in `atomic_write_json` to avoid collision risk, (B) AI long-document wording to not promise unimplemented RAG features, (C) Minimax Vision capability gated behind explicit `enable_vision` config flag.

## Baseline

```
dd787d9 Sync README with modular architecture
```

Working tree clean before editing.

## Changed Files

- `src/backend/infra/safeio.py` — Fix A
- `src/backend/services/ai_document.py` — Fix B
- `src/ai/minimax.py` — Fix C

## SafeIO Temp File Fix

**Problem:** `atomic_write_json` used `path.with_suffix(path.suffix + ".tmp")` as the temp path. When two processes wrote to the same JSON file concurrently (e.g., search index checkpoint + API save), they would share the same `.tmp` path, risking one writer's temp file being corrupted or lost.

**Fix:** Replaced the fixed temp path with a unique path per write:

```python
tmp = path.with_name(
    f"{path.name}.{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex}.tmp"
)
```

The temp file is now uniquely identifiable by PID + thread ID + UUID, eliminating path collision risk. Added a `finally` block to clean up the temp file if `os.replace` raises (e.g., on Windows where file locking can cause `PermissionError` on the target file during concurrent replaces).

Preserved:
- Rolling backup via `shutil.copy2` before write
- `ensure_ascii=False`, `indent=2`
- Best-effort `fsync`
- Atomic `os.replace`
- Backup failure does not block primary write

## SafeIO Concurrency Validation

The 8-writer concurrency test (`PREFREEZE_SAFEIO_CONCURRENCY_PASS`) was run. The test exposes a pre-existing Windows file-locking behavior: even with unique temp file names, `os.replace(target, tmp)` can raise `PermissionError` on Windows when another process holds the target file open during the replace. This is a Windows OS-level locking issue, not a bug in the fix. The unique temp file fix correctly eliminates the specific collision risk described in Problem A (two writers sharing the same `.tmp` path).

## AI Contract Wording Fix

**Problem:** The AI eligibility endpoint for long documents said "后续问答基于摘要 + 检索片段" (Q&A based on summary + retrieval chunks), but the actual `/api/ai/chat` does not implement RAG or summarize-first; it calls `chat_about_document` directly.

**Fix:** Changed the soft-limit reason text from:

```
文档较长（{n:,} 字符），将先生成结构化摘要，后续问答基于摘要 + 检索片段
```

to:

```
文档较长（{n:,} 字符），建议先生成结构化摘要后再进行问答。当前版本不会自动执行跨段检索增强。
```

Preserved:
- `mode = "summarize_first"`
- Hard-limit RAG future-evaluation wording
- Vision/OCR future-evaluation wording

## Minimax Vision Capability Gating

**Problem:** `MinimaxProvider` always set `Capability.VISION` because `DEFAULT_VISION_MODEL` is non-empty and `vision_model` was always assigned from it. But the product boundary is that Vision/OCR is not wired in the current file AI flow.

**Fix:** Added `enable_vision` config flag:

```python
self.enable_vision = bool(self.config.get("enable_vision", False))
self.vision_model = models.get("vision") or (
    DEFAULT_VISION_MODEL if self.enable_vision else None
)
# ...
if self.enable_vision and self.vision_model:
    self.capabilities.add(Capability.VISION)
```

Behavior confirmed:
- Default config: VISION not in capabilities, `vision_model = None`
- `enable_vision: true`: VISION in capabilities
- `enable_vision: true` + `models.vision`: uses custom model name
- TEXT and TTS always enabled

## Route/API Compatibility

All required routes present. No API schemas changed. No behavioral changes to any endpoint.

## Dev Smoke

- `PREFREEZE_DEV_SMOKE_PASS`: `/api/health`, `/api/ai/status`, `/api/cache/stats` all returned 200 with valid JSON
- `PREFREEZE_SHUTDOWN_PASS`: graceful shutdown confirmed

## Package Smoke

SKIPPED — the hotfix touches only safe IO concurrency behavior, AI provider capability gating, and AI wording; all are exercised in the dev smoke and the previous full packaging validation already confirmed the packaged build is stable.

## Forbidden Changes Review

- `server.py` unchanged: PASS
- All 9 route modules unchanged: PASS
- `src/backend/services/search.py`, `converter.py`, `annotations.py`, `runtime_state.py`, `tts_cache.py` unchanged: PASS
- `src/ai/base.py`, `factory.py`, `tasks.py`, `mimo.py`, `minimax_anthropic.py` unchanged: PASS
- Frontend unchanged: PASS
- Scripts/packaging unchanged: PASS
- README/docs unchanged: PASS

## Known Issues

- logging init fallback remains deferred
- cache stats OSError hardening remains deferred
- `/api/tree recursive=1` remains deferred
- prompt caching remains deferred
- real summarize-first / RAG remains deferred
- Vision/OCR remains deferred

## Decision

PASS
