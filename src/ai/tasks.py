"""High-level AI tasks built on top of LLMProvider primitives.

Each task takes an already-constructed provider and the relevant context. The
HTTP layer (server.py) is responsible for resolving the provider and the
document text — these functions remain framework-agnostic.
"""
from __future__ import annotations

import logging
from typing import AsyncIterator

from .base import LLMProvider, Message

log = logging.getLogger("ai.tasks")

SYSTEM_DEFAULT = (
    "你是一名资料学习助手，根据提供的文档内容如实回答问题。"
    "若文档中找不到答案，请直接说『文档中未提及』，不要编造。"
    "回答尽量结构化、引用关键原文。"
)

SYSTEM_SUMMARIZE = (
    "你是一名资料学习助手。请阅读下面的文档全文，输出结构化的中文摘要：\n"
    "1) 一句话概括 (≤40 字)\n"
    "2) 3-7 条核心要点 (每条 ≤80 字)\n"
    "3) 适用场景 / 应试关键词\n"
    "请只基于文档内容，不要发挥。"
)


def _doc_context_message(doc_name: str, doc_text: str) -> Message:
    return Message(
        role="user",
        content=(
            f"以下是文档《{doc_name}》的内容，请阅读后回答后续问题。\n"
            f"<<<DOC_START>>>\n{doc_text}\n<<<DOC_END>>>"
        ),
    )


async def summarize_document(
    provider: LLMProvider,
    doc_name: str,
    doc_text: str,
    *,
    stream: bool = True,
) -> AsyncIterator[str]:
    """Stream a structured summary of one document."""
    messages = [
        Message(role="system", content=SYSTEM_SUMMARIZE),
        _doc_context_message(doc_name, doc_text),
        Message(role="user", content="请按上面要求输出摘要。"),
    ]
    async for delta in provider.chat(messages, stream=stream, max_tokens=1200, temperature=0.3):
        yield delta


async def chat_about_document(
    provider: LLMProvider,
    doc_name: str,
    doc_text: str,
    history: list[Message],
    user_question: str,
    *,
    stream: bool = True,
) -> AsyncIterator[str]:
    """Stream an answer to ``user_question`` given the document and prior turns."""
    messages: list[Message] = [Message(role="system", content=SYSTEM_DEFAULT)]
    messages.append(_doc_context_message(doc_name, doc_text))
    for h in history:
        messages.append(h)
    messages.append(Message(role="user", content=user_question))
    async for delta in provider.chat(messages, stream=stream, max_tokens=1600, temperature=0.4):
        yield delta
