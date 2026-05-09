"""with-ui — plugin that ships a sandboxed iframe UI.

The ``frontend.ui_entry`` block in plugin.yaml tells AURORAZ desktop to
serve ``ui/index.html`` and mount it as the plugin's Plugin Page.

The plugin's Python side here registers one tool that triggers an
in-app toast (via ``aurora.notify``); the iframe UI demonstrates the
postMessage protocol (init / settings-changed / notify) and prints
init payloads to the page for inspection.
"""

from __future__ import annotations

import logging

from auroraz_sdk import Plugin, aurora, hook, tool

logger = logging.getLogger("auroraz.plugin.with-ui")

plugin = Plugin(
    id="with-ui",
    name="With UI",
    version="0.1.0",
    permissions=["notifications:show"],
)


@tool(
    name="with_ui_toast",
    description="Show a toast inside AURORAZ.",
    when="user asks the plugin to ping or show a notification",
)
async def toast(message: str = "Hello from with-ui") -> str:
    await aurora.notify(message)
    return f"Toasted: {message!r}"


@hook("on_startup")
async def on_startup(_ctx) -> None:
    logger.info("[with-ui] started — UI served from /api/plugins/with-ui/ui/...")


if __name__ == "__main__":
    plugin.run()
