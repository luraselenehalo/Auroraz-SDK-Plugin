import asyncio
import inspect
import json
import logging
import os
import signal
from typing import Any, Awaitable, Callable, Optional

from auroraz_sdk.aurora_client import AuroraClient
from auroraz_sdk.decorators import _hooks, _panels, _tools
from auroraz_sdk.ipc import IPCClient
from auroraz_sdk.permissions import PermissionChecker

logger = logging.getLogger("auroraz.sdk.plugin")


class Plugin:
    """Base class for all AURORAZ plugins.

    Usage:
        plugin = Plugin(id="my-plugin", name="My Plugin", version="1.0.0",
                        permissions=["network:api.spotify.com"])

        @tool(name="do_thing", description="does thing")
        async def do_thing(query: str): ...

        plugin.run()
    """

    def __init__(
        self,
        id: str,
        name: str,
        version: str = "1.0.0",
        permissions: list = None,
    ):
        self.id = id
        self.name = name
        self.version = version
        self.permissions = permissions or []

        self._ipc_addr = os.environ.get("AURORAZ_IPC_ADDR", "")

        config_raw = os.environ.get("AURORAZ_PLUGIN_CONFIG", "{}")
        try:
            self.config: dict = json.loads(config_raw)
        except json.JSONDecodeError:
            logger.warning("[Plugin] AURORAZ_PLUGIN_CONFIG is not valid JSON; defaulting to {}")
            self.config = {}

        self._ipc: Optional[IPCClient] = None
        self._perms: Optional[PermissionChecker] = None
        self.aurora: Optional[AuroraClient] = None
        # Set to True after `_startup()` finishes its `plugin.register` IPC
        # call. `register_tool()` uses this to decide between (a) appending
        # to the local _tools list and letting startup pick it up, or (b)
        # pushing a `plugin.register_tool` delta over the live IPC channel.
        self._started: bool = False

    async def _startup(self):
        """Connect IPC and set up aurora client."""
        self._ipc = IPCClient(self.id, self._ipc_addr)
        await self._ipc.connect()

        self._perms = PermissionChecker(self.id, self.permissions)
        self.aurora = AuroraClient(self._ipc, self._perms)

        # Route server-initiated calls to our dispatcher
        self._ipc.set_event_handler(self._handle_server_message)

        # Expose aurora via the package-level proxy
        from . import _set_aurora_instance
        _set_aurora_instance(self.aurora)

        await self._ipc.call("plugin.register", {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "permissions": self.permissions,
            "tools": [
                # `parameters` carries the JSON-schema / OpenAI-style param
                # description registered via @tool(parameters=...) or
                # plugin.register_tool(parameters=...). Empty {} when the
                # author didn't supply one — agent_service falls back to a
                # generic `["query"]` shape in that case.
                {
                    "name": t["name"],
                    "description": t["description"],
                    "when": t["when"],
                    "parameters": t.get("parameters") or {},
                }
                for t in _tools
            ],
            "hooks": list(_hooks.keys()),
            "panels": [p["slot"] for p in _panels],
        })

        # Mark startup complete so register_tool() knows it can push deltas.
        self._started = True

        logger.info("[Plugin] %s v%s registered with core", self.name, self.version)

        await self._dispatch_hook("on_startup", {})

    async def _handle_server_message(self, msg: dict):
        """Route server-initiated messages to hook dispatch or tool handlers."""
        method = msg.get("method", "")
        params = msg.get("params", {}) or {}
        request_id = msg.get("request_id")

        try:
            if method == "hook.dispatch":
                event_type = params.get("event_type", "")
                data = params.get("data", {})
                await self._dispatch_hook(event_type, data)
                if request_id:
                    await self._ipc.reply(request_id, result=None)
            elif method == "tool.call":
                tool_name = params.get("name", "")
                tool_params = params.get("params", {}) or {}
                result = await self._handle_tool_call(tool_name, tool_params)
                if request_id:
                    await self._ipc.reply(request_id, result=result)
            else:
                if request_id:
                    await self._ipc.reply(request_id, error=f"Unknown method: {method}")
        except Exception as e:
            logger.error("[Plugin] Error handling %s: %s", method, e)
            if request_id:
                await self._ipc.reply(request_id, error=str(e))

    async def _dispatch_hook(self, event_type: str, data: dict):
        """Called by IPC when core fires an event."""
        from auroraz_sdk.context import HookContext

        ctx = HookContext(
            text=data.get("text", ""),
            emotion=data.get("emotion", ""),
            intent=data.get("intent", ""),
            window=data.get("window", {}),
            session_id=data.get("session_id", ""),
            _plugin_id=self.id,
            _event_type=event_type,
        )
        handlers = _hooks.get(event_type, [])
        for handler in handlers:
            try:
                await handler(ctx)
            except Exception as e:
                logger.error("[Plugin] Hook %s error: %s", event_type, e)

    async def register_tool(
        self,
        name: str,
        description: str,
        handler: Callable[..., Awaitable[Any]],
        *,
        parameters: Optional[dict] = None,
        when: Optional[str] = None,
    ) -> None:
        """Register a tool at runtime, after Plugin.run() has connected.

        Companion to the @tool decorator. The decorator path runs at module
        import time and is preferred when tools are static. This runtime path
        is needed by plugins whose tool catalog is discovered dynamically —
        e.g. a bridge that mirrors another framework's registry on connect.

        Idempotent on `name`: a second call with the same name overwrites
        the previous entry rather than producing a duplicate. The overwrite
        is logged so duplicate registrations are easy to spot.

        Pre-startup safety: if called before `_startup()` finishes, the
        new tool is appended to the shared `_tools` list and the startup
        snapshot picks it up. Post-startup, a `plugin.register_tool` IPC
        delta is sent to the core so the agent's tool catalog stays in
        sync without re-registering every other tool.
        """
        # ── input validation ──────────────────────────────────────
        if not isinstance(name, str) or not name.strip():
            raise ValueError("register_tool: name must be a non-empty string")
        if any(ch.isspace() for ch in name):
            raise ValueError(
                f"register_tool: name {name!r} must not contain whitespace "
                "(use underscores e.g. 'hermes_read_file')"
            )
        if not isinstance(description, str):
            raise ValueError("register_tool: description must be a string")
        if not callable(handler):
            raise ValueError("register_tool: handler must be callable")
        if parameters is not None and not isinstance(parameters, dict):
            raise ValueError("register_tool: parameters must be a dict or None")

        # Wrap sync handlers transparently — the dispatch path always
        # awaits, so a sync `def` would otherwise raise.
        if not inspect.iscoroutinefunction(handler):
            _sync_handler = handler

            async def _wrapped(**kwargs):
                return _sync_handler(**kwargs)

            handler = _wrapped

        entry = {
            "name": name,
            "description": description,
            "when": when or "",
            "handler": handler,
            "parameters": parameters or {},
        }

        # ── idempotent local registration ─────────────────────────
        replaced = False
        for i, existing in enumerate(_tools):
            if existing.get("name") == name:
                _tools[i] = entry
                replaced = True
                break
        if not replaced:
            _tools.append(entry)

        if replaced:
            logger.info("[Plugin] register_tool: overwrote existing '%s' (idempotent)", name)
        else:
            logger.debug("[Plugin] register_tool: added '%s'", name)

        # ── push delta if live ────────────────────────────────────
        if not self._started:
            # Pre-startup. The startup `plugin.register` snapshot will
            # include this tool — nothing more to do.
            return

        if self._ipc is None:
            # Defensive: started but IPC went away. Fall through silently.
            logger.debug(
                "[Plugin] register_tool: _started=True but IPC is None — "
                "delta NOT sent for '%s'", name,
            )
            return

        try:
            await self._ipc.call("plugin.register_tool", {
                "name": entry["name"],
                "description": entry["description"],
                "when": entry["when"],
                "parameters": entry["parameters"],
            })
        except Exception as e:
            # Don't crash the plugin on a delta-send failure — the tool is
            # still registered locally and the next reconnect's full
            # `plugin.register` payload will sync the catalog.
            logger.warning(
                "[Plugin] register_tool: IPC delta failed for '%s': %s "
                "(local registration intact)", name, e,
            )

    async def _handle_tool_call(self, tool_name: str, params: dict) -> str:
        """Called by IPC when core wants to use a tool."""
        for t in _tools:
            if t["name"] == tool_name:
                try:
                    result = await t["handler"](**params)
                    return str(result) if result is not None else ""
                except Exception as e:
                    logger.error("[Plugin] Tool %s error: %s", tool_name, e)
                    return f"Error: {e}"
        return f"Tool '{tool_name}' not found"

    def run(self):
        """Start the plugin. Blocks until shutdown."""

        async def _main():
            await self._startup()

            loop = asyncio.get_event_loop()
            stop = loop.create_future()

            def _shutdown(*_):
                if not stop.done():
                    stop.set_result(None)

            # signal.signal is only valid in main thread; guard for safety
            try:
                signal.signal(signal.SIGTERM, _shutdown)
                signal.signal(signal.SIGINT, _shutdown)
            except (ValueError, AttributeError):
                pass

            try:
                await stop
            finally:
                try:
                    await self._dispatch_hook("on_shutdown", {})
                except Exception as e:
                    logger.error("[Plugin] on_shutdown error: %s", e)
                await self._ipc.disconnect()

        asyncio.run(_main())
