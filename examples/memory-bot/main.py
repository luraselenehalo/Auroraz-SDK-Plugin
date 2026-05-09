"""memory-bot — uses ``aurora.memory`` to persist + recall facts.

Two tools:

* ``memory_bot_remember(text)`` — store a fact in long-term memory
* ``memory_bot_recall(query, k=3)`` — semantic-search and return matches

Both tools route through ``aurora.memory.*`` so they reach AURORAZ's
shared ChromaDB-backed semantic store. The ``memory:read`` and
``memory:write`` permissions are gated on the manifest declaration —
calling without them raises :class:`PermissionDeniedError` server-side.
"""

from __future__ import annotations

import json
import logging

from auroraz_sdk import Plugin, aurora, hook, tool

logger = logging.getLogger("auroraz.plugin.memory-bot")

plugin = Plugin(
    id="memory-bot",
    name="Memory Bot",
    version="0.1.0",
    permissions=["memory:read", "memory:write"],
)


@tool(
    name="memory_bot_remember",
    description="Store a fact in AURORAZ's long-term memory.",
    when="user asks to remember, save, or note something for later",
)
async def remember(text: str) -> str:
    if not text or not text.strip():
        return "Nothing to remember — pass a non-empty text."
    await aurora.memory.remember(text.strip())
    return f"Got it. I will remember: {text.strip()}"


@tool(
    name="memory_bot_recall",
    description="Search AURORAZ's long-term memory and return up to k matches.",
    when="user asks what they told you about a topic, or to recall a memory",
)
async def recall(query: str, k: int = 3) -> str:
    hits = await aurora.memory.search(query, k=max(1, min(k, 10)))
    if not hits:
        return f"No memories matched {query!r}."
    return json.dumps(
        [{"text": h.get("text"), "score": h.get("score")} for h in hits],
        ensure_ascii=False,
    )


@hook("on_startup")
async def on_startup(_ctx) -> None:
    logger.info("[memory-bot] started — memory:read+memory:write granted")


if __name__ == "__main__":
    plugin.run()
