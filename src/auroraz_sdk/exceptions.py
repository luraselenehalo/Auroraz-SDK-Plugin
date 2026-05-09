class PluginError(Exception):
    pass


class PermissionDeniedError(PluginError):
    def __init__(self, permission: str, plugin_id: str):
        super().__init__(
            f"Plugin '{plugin_id}' requires permission '{permission}' "
            f"which was not declared in manifest."
        )
        self.permission = permission
        self.plugin_id = plugin_id


class IPCError(PluginError):
    pass


class PluginTimeoutError(PluginError):
    pass


class RateLimitError(PluginError):
    """Stage 7 — plugin exceeded a per-level reasoning rate limit."""

    def __init__(self, plugin_id: str, level: str, limit: tuple):
        per_min, per_day = limit if isinstance(limit, tuple) else (limit, None)
        msg = (
            f"Plugin '{plugin_id}' exceeded {level} reasoning rate limit "
            f"(per_min={per_min}, per_day={per_day})"
        )
        super().__init__(msg)
        self.plugin_id = plugin_id
        self.level = level
        self.limit = limit


class RecursionLimitError(PluginError):
    """Stage 7 — plugin reasoning is being called recursively past depth limit."""

    def __init__(self, plugin_id: str, depth: int):
        super().__init__(
            f"Plugin '{plugin_id}' reasoning depth limit exceeded "
            f"(current depth={depth}; max=2)"
        )
        self.plugin_id = plugin_id
        self.depth = depth
