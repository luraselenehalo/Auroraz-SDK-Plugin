"""auroraz-sdk - official Plugin SDK for AURORAZ.

Build plugins for AURORAZ Personal AI OS.

Quickstart::

    from auroraz_sdk import Plugin, aurora, hook, tool

    plugin = Plugin(
        id="my-plugin",
        name="My Plugin",
        version="0.1.0",
        permissions=["memory:read"],
    )

    @tool(name="my_plugin_hello")
    async def hello(name: str = "world") -> str:
        return f"Hello, {name}!"

    if __name__ == "__main__":
        plugin.run()
"""

__version__ = "0.2.0"

from auroraz_sdk.aurora_client import AuroraClient
from auroraz_sdk.context import HookContext
from auroraz_sdk.decorators import hook, panel, tool
from auroraz_sdk.exceptions import (
    IPCError,
    PermissionDeniedError,
    PluginError,
    PluginTimeoutError,
    RateLimitError,
    RecursionLimitError,
)
from auroraz_sdk.plugin import Plugin

# Module-level aurora singleton - set by Plugin._startup() after IPC connects.
_aurora_instance = None


def _set_aurora_instance(instance):
    global _aurora_instance
    _aurora_instance = instance


class _AuroraProxy:
    """Lazy proxy to the aurora client - resolves after plugin.run() connects."""

    def __getattr__(self, name):
        if _aurora_instance is None:
            raise RuntimeError("aurora not initialized - call plugin.run() first")
        return getattr(_aurora_instance, name)


aurora = _AuroraProxy()


__all__ = [
    "Plugin", "tool", "hook", "panel",
    "aurora", "HookContext", "AuroraClient",
    "PluginError", "PermissionDeniedError", "IPCError",
    "PluginTimeoutError", "RateLimitError", "RecursionLimitError",
    "__version__",
]
