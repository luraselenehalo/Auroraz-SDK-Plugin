"""research-bot — uses ``aurora.reasoning.ask()`` to answer questions.

Demonstrates the Stage 7 reasoning API. Two tools:

* ``research_bot_quick_research(question)`` — K1 (general / single pass)
* ``research_bot_deep_research(question)``  — K3 (draft + verify + refine)

K3 requires ``reasoning:k3`` declared in plugin.yaml. The additive
hierarchy means that holding k3 also satisfies k1, so a single
``reasoning:k3`` declaration unlocks both tools below.
"""

from __future__ import annotations

import logging

from auroraz_sdk import Plugin, aurora, hook, tool

logger = logging.getLogger("auroraz.plugin.research-bot")

plugin = Plugin(
    id="research-bot",
    name="Research Bot",
    version="0.1.0",
    permissions=["reasoning:k3", "notifications:show"],
)


@tool(
    name="research_bot_quick_research",
    description="Use AURORAZ's standard reasoning to answer a general question.",
    when="user asks a general question that needs a single-pass answer",
)
async def quick_research(question: str) -> str:
    """K1-level reasoning — one LLM pass, faster, broader."""
    if not question or not question.strip():
        return "Pass a non-empty question."
    return await aurora.reasoning.ask(question.strip(), level="K1")


@tool(
    name="research_bot_deep_research",
    description="Use AURORAZ's deep reasoning (K3 — draft + verify + refine) to answer a complex question.",
    when="user asks for in-depth analysis, comparison, or research",
)
async def deep_research(question: str) -> str:
    """K3-level reasoning — most expensive, most thorough."""
    if not question or not question.strip():
        return "Pass a non-empty question."
    return await aurora.reasoning.ask(question.strip(), level="K3")


@hook("on_startup")
async def on_startup(_ctx) -> None:
    logger.info("[research-bot] started — reasoning:k3 granted")
    try:
        await aurora.notify(
            "Research Bot ready. Use `research_bot_deep_research` for K3 analysis.",
            via="app",
        )
    except Exception as e:  # pragma: no cover — notify is best-effort
        logger.debug("[research-bot] notify on startup failed: %s", e)


if __name__ == "__main__":
    plugin.run()
