from auroraz_sdk.exceptions import (
    IPCError,
    PermissionDeniedError,
    PluginTimeoutError,
    RateLimitError,
    RecursionLimitError,
)
from auroraz_sdk.ipc import IPCClient
from auroraz_sdk.permissions import PermissionChecker

_VALID_REASONING_LEVELS = {"K0", "K1", "K2", "K3"}


class _MemoryClient:
    def __init__(self, ipc: IPCClient, perms: PermissionChecker):
        self._ipc = ipc
        self._perms = perms

    async def store(self, key: str, value) -> None:
        self._perms.require("memory:write")
        await self._ipc.call("memory.store", {"key": key, "value": value})

    async def get(self, key: str):
        self._perms.require("memory:read")
        return await self._ipc.call("memory.get", {"key": key})

    async def remember(self, text: str, *, metadata: dict | None = None) -> dict:
        """Store a long-term semantic memory in AURORAZ's ChromaDB store.

        ``metadata`` is optional — when present, the plugin's keys are
        merged with AURORAZ's canonical fields (``source``, ``plugin_id``,
        ``author``). The canonical fields always win on collision so a
        plugin cannot impersonate another origin or spoof authorship.

        Reserved-key prefixes (anything starting with ``_`` and the three
        canonical keys) are silently dropped from plugin metadata server-
        side; a WARNING is logged so authors can spot the drop.
        """
        self._perms.require("memory:write")
        payload: dict = {"text": text}
        if metadata is not None:
            if not isinstance(metadata, dict):
                raise TypeError("metadata must be a dict if provided")
            payload["metadata"] = metadata
        return await self._ipc.call("memory.remember", payload)

    async def search(self, query: str, k: int = 5) -> list[dict]:
        """Semantic-search the plugin's accessible memories.

        Returns up to ``k`` (clamped to ``[1, 50]``) hits, each shaped as::

            {"text": str, "score": float, "metadata": dict, "timestamp": str}

        ``score`` is in ``[0, 1]`` (higher = more relevant). ``timestamp``
        is ISO 8601. Empty/whitespace queries raise ``IPCError`` server-
        side. Per-plugin namespacing (so a plugin only sees memories it
        wrote) is a Phase 5 hardening item; today the search returns from
        the same shared semantic pool that ``aurora.memory.get()`` reads.
        """
        self._perms.require("memory:read")
        return await self._ipc.call("memory.search", {"query": query, "k": k})


class _ContextClient:
    def __init__(self, ipc: IPCClient, perms: PermissionChecker):
        self._ipc = ipc
        self._perms = perms

    async def get_emotion(self) -> str:
        self._perms.require("context:read")
        return await self._ipc.call("context.get_emotion")

    async def get_intent(self) -> str:
        self._perms.require("context:read")
        return await self._ipc.call("context.get_intent")

    async def get_window(self) -> dict:
        self._perms.require("context:read")
        return await self._ipc.call("context.get_window")


class _ReasoningClient:
    """``aurora.reasoning.*`` — invoke AURORAZ's Fractal 1:3 engine.

    Requires permission ``reasoning:k0`` / ``:k1`` / ``:k2`` / ``:k3``
    declared in the plugin manifest. Higher levels imply lower
    (k3 ⊇ k2 ⊇ k1 ⊇ k0), so a plugin with ``reasoning:k3`` may also
    call ``ask(level="K1")``.

    Default rate limits (per plugin per level)::

        K0  → unlimited (no LLM cost)
        K1  → 60 / min, 1000 / day
        K2  → 30 / min,  500 / day
        K3  → 10 / min,  100 / day

    Recursion guard: a plugin's reasoning call that triggers a tool that
    calls reasoning again is allowed once (depth=1 → depth=2). A third
    nesting raises :class:`RecursionLimitError`.

    Server-side errors come back as :class:`IPCError` over the wire;
    this client re-classifies them into :class:`PermissionDeniedError`
    / :class:`RateLimitError` / :class:`RecursionLimitError` so plugin
    authors can ``except`` precisely.
    """

    def __init__(self, ipc: IPCClient, perms: PermissionChecker):
        self._ipc = ipc
        self._perms = perms

    async def ask(
        self,
        question: str,
        level: str = "K1",
        *,
        timeout: float = 30.0,
    ) -> str:
        """Invoke the Fractal 1:3 engine. Returns the answer string.

        ``level`` is one of ``"K0"``, ``"K1"``, ``"K2"``, ``"K3"`` (default
        ``"K1"``). Higher levels are slower and more expensive but produce
        deeper reasoning. K3 runs draft + self-verify + optional refine.

        Raises:
            ValueError: ``level`` is not one of K0/K1/K2/K3.
            PermissionDeniedError: plugin manifest lacks ``reasoning:<level>``.
            RateLimitError: per-plugin per-level rate limit exceeded.
            RecursionLimitError: reasoning depth limit (2) exceeded.
            PluginTimeoutError: response took longer than ``timeout``.
            IPCError: any other transport / engine failure.
        """
        if level not in _VALID_REASONING_LEVELS:
            raise ValueError(
                f"level must be one of K0/K1/K2/K3, got {level!r}"
            )
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must be a non-empty string")

        # Client-side permission check — fast-fail before paying for the
        # IPC round-trip when the plugin clearly didn't declare the perm.
        # Server still re-checks (defense-in-depth + hierarchy traversal).
        self._perms.require(f"reasoning:{level.lower()}")

        try:
            result = await self._ipc.call(
                "reasoning.ask",
                {"question": question, "level": level},
                timeout=timeout,
            )
        except PluginTimeoutError:
            raise
        except IPCError as e:
            raise _classify_reasoning_error(e) from e

        if not isinstance(result, dict) or "answer" not in result:
            raise IPCError(f"reasoning.ask: malformed response {result!r}")
        return str(result.get("answer") or "")

    async def ask_simple(self, question: str) -> str:
        """Convenience: ``ask(question, level="K1")``."""
        return await self.ask(question, level="K1")

    async def ask_deep(self, question: str) -> str:
        """Convenience: ``ask(question, level="K3")``.

        Requires ``reasoning:k3`` in the manifest. Most expensive level —
        runs draft + self-verify + optional refine (up to 3 LLM calls).
        """
        return await self.ask(question, level="K3")


def _classify_reasoning_error(e: IPCError) -> Exception:
    """Map a server-side error string back to the most specific exception.

    The IPC layer flattens server-raised exceptions into ``IPCError(str(e))``,
    so we sniff the message to restore the type. Keeps the exception
    contract documented on :class:`_ReasoningClient.ask` honest from the
    plugin's perspective.
    """
    msg = str(e)
    low = msg.lower()
    if "rate limit" in low or "ratelimiterror" in low:
        return RateLimitError("?", "?", (None, None))
    if "depth limit" in low or "recursionlimiterror" in low:
        return RecursionLimitError("?", -1)
    if "requires permission" in msg or "permissiondeniederror" in low:
        # Try to extract the perm name from the canonical message format.
        perm = ""
        try:
            if "permission '" in msg:
                perm = msg.split("permission '", 1)[1].split("'", 1)[0]
        except Exception:
            pass
        return PermissionDeniedError(perm or "reasoning:?", "?")
    return e


class AuroraClient:
    """aurora.* API available to plugins. All methods are async and go through IPC."""

    def __init__(self, ipc: IPCClient, perms: PermissionChecker):
        self._ipc = ipc
        self._perms = perms
        self.memory = _MemoryClient(ipc, perms)
        self.context = _ContextClient(ipc, perms)
        # Stage 7 — aurora.reasoning surface. The sub-client itself is
        # cheap; permission and rate-limit enforcement happens on each
        # ask() call, not on instantiation.
        self.reasoning = _ReasoningClient(ipc, perms)

    async def say(self, text: str) -> None:
        """Aurora speaks in chat."""
        await self._ipc.call("aurora.say", {"text": text})

    async def inject(self, context: str) -> None:
        """Add context to next system prompt."""
        # Stage 3 — canonical permission name. Subprocess plugins still
        # declaring `prompt:inject` get normalized at register time so
        # the require() call here matches what was stored.
        self._perms.require("context:inject")
        sanitized = context[:500].replace("[INST]", "").replace("</s>", "")
        await self._ipc.call("aurora.inject", {"context": sanitized})

    async def get_last_message(self) -> str:
        self._perms.require("context:read")
        return await self._ipc.call("aurora.get_last_message")

    async def notify(self, text: str, via: str = "app") -> None:
        self._perms.require("notifications:show")
        await self._ipc.call("aurora.notify", {"text": text, "via": via})
