from auroraz_sdk.exceptions import PermissionDeniedError

# `granted_perm: [implies_perm, …]` — when a plugin holds the key, it
# transitively also satisfies any permission in the value list. The list
# is read by PermissionChecker.require() below.
#
# Stage 3 — entries are canonical (colon-namespaced). Legacy `prompt:inject`
# is left here as a self-implication so subprocess plugins that haven't
# yet been migrated keep working when their manifest still declares
# `prompt:inject` directly without going through the manifest parser
# (e.g. a unit test stubbing PermissionChecker with a raw list). The
# manifest parser normalizes to `context:inject` for first-class use.
PERMISSION_HIERARCHY = {
    "network": ["network"],
    "network:*": ["network"],
    "memory:read": ["memory:read"],
    "memory:write": ["memory:write", "memory:read"],
    "context:read": ["context:read"],
    "context:inject": ["context:inject"],
    "working_memory:read": ["working_memory:read"],
    # write implies read (Stage 3 — orthogonal to context:inject)
    "working_memory:write": ["working_memory:write", "working_memory:read"],
    "notifications:show": ["notifications:show"],
    "process:scan": ["process:scan"],
    "anthropic:proxy": ["anthropic:proxy"],
    # Legacy (deprecated alias): still self-implies so any not-yet-migrated
    # call site that does PermissionChecker(plugin, ['prompt:inject'])
    # without manifest normalization keeps working.
    "prompt:inject": ["prompt:inject"],
    "notifications": ["notifications"],
    # Stage 7 — Reasoning permissions are additive: a higher level implies
    # all lower levels, mirroring how memory:write implies memory:read. A
    # plugin holding reasoning:k3 may legitimately call ask(level="K1").
    "reasoning:k0": ["reasoning:k0"],
    "reasoning:k1": ["reasoning:k1", "reasoning:k0"],
    "reasoning:k2": ["reasoning:k2", "reasoning:k1", "reasoning:k0"],
    "reasoning:k3": ["reasoning:k3", "reasoning:k2", "reasoning:k1", "reasoning:k0"],
    # Untouched by Stage 3 — kept for forward-compat with future scopes.
    "file:read": ["file:read"],
    "audio": ["audio"],
    "clipboard": ["clipboard"],
}


class PermissionChecker:
    def __init__(self, plugin_id: str, granted_permissions: list):
        self._plugin_id = plugin_id
        self._granted = set(granted_permissions)

    def require(self, permission: str):
        """Raise PermissionDeniedError if permission not granted."""
        if permission in self._granted:
            return

        if permission.startswith("network:"):
            if "network" in self._granted:
                return
            if permission in self._granted:
                return

        for granted in self._granted:
            implied = PERMISSION_HIERARCHY.get(granted, [granted])
            if permission in implied:
                return

        raise PermissionDeniedError(permission, self._plugin_id)

    def has(self, permission: str) -> bool:
        try:
            self.require(permission)
            return True
        except PermissionDeniedError:
            return False
