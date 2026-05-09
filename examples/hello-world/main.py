"""hello-world — the simplest possible auroraz-sdk plugin.

Registers one tool that takes a name and returns a greeting. No
permissions, no AURORAZ APIs, no state. The point is to show the
minimum boilerplate to ship a working plugin.

Run inside AURORAZ desktop after installing — the agent gains a
``hello_world_greet`` tool. Or run standalone with ``python main.py``
to verify the plugin starts (it'll wait for an IPC connection that
never arrives — kill with Ctrl+C; that's expected).
"""

from __future__ import annotations

import logging

from auroraz_sdk import Plugin, hook, tool

logger = logging.getLogger("auroraz.plugin.hello-world")

plugin = Plugin(
    id="hello-world",
    name="Hello World",
    version="0.1.0",
    permissions=[],
)


@tool(
    name="hello_world_greet",
    description="Greet someone by name.",
    when="user asks for a greeting or to say hi",
)
async def greet(name: str = "world") -> str:
    return f"Hello, {name}!"


@hook("on_startup")
async def on_startup(_ctx) -> None:
    logger.info("[hello-world] started")


if __name__ == "__main__":
    plugin.run()
