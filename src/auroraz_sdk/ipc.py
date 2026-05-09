"""IPC transport between plugin subprocess and AURORAZ core.

Uses asyncio streams over a Unix socket (Linux/Mac) or a TCP loopback
connection on Windows (newline-delimited JSON framing either way).
"""

import asyncio
import json
import logging
import uuid
from typing import Any, Optional

from auroraz_sdk.exceptions import IPCError, PluginTimeoutError

logger = logging.getLogger("auroraz.sdk.ipc")

IPC_TIMEOUT = 10.0


class IPCClient:
    """Plugin-side client. Connects to AURORAZ core's IPC server."""

    def __init__(self, plugin_id: str, ipc_addr: str):
        self._plugin_id = plugin_id
        self._ipc_addr = ipc_addr
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._pending: dict = {}
        self._event_handler = None  # set by Plugin for server-initiated calls

    def set_event_handler(self, handler):
        """Handler called for inbound messages that are NOT responses to our calls.

        Signature: async def handler(msg: dict) -> None
        """
        self._event_handler = handler

    async def connect(self):
        if self._ipc_addr.startswith("unix:"):
            path = self._ipc_addr[5:]
            self._reader, self._writer = await asyncio.open_unix_connection(path)
        elif self._ipc_addr.startswith("tcp:"):
            _, addr = self._ipc_addr.split(":", 1)
            host, port = addr.rsplit(":", 1)
            self._reader, self._writer = await asyncio.open_connection(host, int(port))
        else:
            raise IPCError(f"Unsupported IPC address scheme: {self._ipc_addr!r}")

        asyncio.create_task(self._read_loop())
        logger.info("[IPC] Plugin %s connected to core at %s", self._plugin_id, self._ipc_addr)

    async def _read_loop(self):
        try:
            while True:
                line = await self._reader.readline()
                if not line:
                    break
                try:
                    msg = json.loads(line.decode())
                except json.JSONDecodeError as e:
                    logger.warning("[IPC] Malformed message dropped: %s", e)
                    continue

                req_id = msg.get("request_id")
                # If this request_id matches one we sent, it's a response.
                if req_id and req_id in self._pending:
                    fut = self._pending.pop(req_id)
                    if not fut.done():
                        err = msg.get("error")
                        if err:
                            fut.set_exception(IPCError(err))
                        else:
                            fut.set_result(msg.get("result"))
                else:
                    # Server-initiated call (hook dispatch / tool invocation)
                    if self._event_handler:
                        asyncio.create_task(self._event_handler(msg))
        except Exception as e:
            logger.error("[IPC] Read loop error: %s", e)

    async def call(self, method: str, params: dict = None, timeout: float = IPC_TIMEOUT) -> Any:
        """Send a request and await a response.

        Wire format (newline-delimited JSON):
            {"request_id": "...", "plugin_id": "...", "method": "...", "params": {...}}
        Response:
            {"request_id": "...", "result": ..., "error": null}
        """
        if not self._writer:
            raise IPCError("Not connected to AURORAZ core")

        request_id = str(uuid.uuid4())[:8]
        msg = {
            "request_id": request_id,
            "plugin_id": self._plugin_id,
            "method": method,
            "params": params or {},
        }

        fut = asyncio.get_event_loop().create_future()
        self._pending[request_id] = fut

        self._writer.write((json.dumps(msg) + "\n").encode())
        await self._writer.drain()

        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(request_id, None)
            raise PluginTimeoutError(f"IPC call '{method}' timed out after {timeout}s")

    async def reply(self, request_id: str, result: Any = None, error: str = None):
        """Send a response back to core (for server-initiated calls)."""
        if not self._writer:
            raise IPCError("Not connected to AURORAZ core")
        msg = {"request_id": request_id, "result": result, "error": error}
        self._writer.write((json.dumps(msg) + "\n").encode())
        await self._writer.drain()

    async def disconnect(self):
        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass
