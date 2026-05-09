"""Permission vocabulary — single source of truth.

Canonical form is colon-namespaced: ``scope:action[:qualifier]``.

Three legacy forms exist on disk and remain back-compat-aliased here:
  - underscore (in-process):   ``memory_read``, ``context_injection``
  - dot         (discord pre-Stage-3): ``memory.read``, ``chat.inject``
  - colon-old   (subprocess):  ``prompt:inject`` (now ``context:inject``)

All three normalize to the canonical colon form at parse time. The
``[PermissionAlias]`` warning logs the deprecation so authors can see
exactly what to update via the migration script.

Strict mode (env ``AURORAZ_STRICT_PERM_VOCAB=1``) rejects aliases entirely
so CI / future strict-by-default flips can be tested early.
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger("auroraz.plugin.permissions")


# Authoritative canonical permissions, grouped by scope.
# Permissions discovered via plugin manifests but not appearing here pass
# through unchanged — the permission checker decides whether to grant
# access; future stages may extend this set.
CANONICAL_PERMISSIONS: set[str] = {
    # Memory
    "memory:read",
    "memory:write",
    # Working memory / context
    "context:read",         # current emotion, intent, active window
    "working_memory:read",
    "working_memory:write",
    "context:inject",       # inject lines into the system prompt
    # Notifications & UI
    "notifications:show",
    # Network — `network` (any host) and `network:<host>` (specific) are both canonical
    "network",
    # Process / OS
    "process:scan",         # detect running OS processes
    # SDK proxies
    "anthropic:proxy",
    # Stage 7 — Reasoning levels (additive; k3 implies k2 implies k1 implies k0).
    # The IPC handler verifies the requested level against the plugin's
    # declared permissions using the hierarchy in sdk.permissions.
    "reasoning:k0",
    "reasoning:k1",
    "reasoning:k2",
    "reasoning:k3",
}


# Underscore/dot/old-colon → canonical alias map. Keys are deprecated forms;
# values are the canonical colon form they map to. Add aliases here without
# adding to CANONICAL_PERMISSIONS — they're not first-class.
PERMISSION_ALIASES: dict[str, str] = {
    # Underscore form (in-process plugins)
    "memory_read":          "memory:read",
    "memory_write":         "memory:write",
    # `working_memory` (no action) → :read. The in-process loader does not
    # actually inject a writable working_memory service today (it stays
    # None per loader._create_services). If a future loader change starts
    # injecting writes, switch this to working_memory:write — which under
    # the precedence rule below implies :read.
    "working_memory":       "working_memory:read",
    "context_injection":    "context:inject",
    "process_scan":         "process:scan",
    "anthropic_sdk":        "anthropic:proxy",
    "notifications":        "notifications:show",
    # Old subprocess colon form
    "prompt:inject":        "context:inject",
    # Dot form (discord-era)
    "memory.read":          "memory:read",
    "memory.write":         "memory:write",
    "chat.inject":          "context:inject",
    "network.outbound":     "network",
}


STRICT_VOCAB = os.environ.get("AURORAZ_STRICT_PERM_VOCAB") == "1"


def normalize_permission(raw: str) -> tuple[str, bool]:
    """Return ``(canonical_form, was_aliased)`` for one raw permission string.

    Network host scopes pass through unchanged: ``network:api.spotify.com``
    is already canonical (``network`` scope with a host qualifier).

    Unknown permissions pass through unchanged with ``was_aliased=False``.
    The caller decides whether to reject them (strict mode does).
    """
    if raw in CANONICAL_PERMISSIONS:
        return raw, False
    # Network host qualifier — anything starting with `network:` and longer
    # than the bare scope is fine.
    if raw.startswith("network:") and len(raw) > len("network:"):
        return raw, False
    if raw in PERMISSION_ALIASES:
        return PERMISSION_ALIASES[raw], True
    # Unknown — pass through; permission checker decides.
    return raw, False


def normalize_permissions(raw_list: list[str], plugin_id: str = "?") -> list[str]:
    """Normalize a list of permission strings.

    - Logs a ``[PermissionAlias]`` WARNING per deprecated alias.
    - Raises ``ValueError`` in strict mode (``AURORAZ_STRICT_PERM_VOCAB=1``).
    - De-duplicates (preserving first-seen order) so a manifest declaring
      both ``memory_read`` and ``memory:read`` collapses cleanly.
    """
    out: list[str] = []
    for raw in raw_list:
        canonical, was_aliased = normalize_permission(raw)
        if was_aliased:
            log.warning(
                "[PermissionAlias] plugin %r uses deprecated permission %r → mapped to %r",
                plugin_id, raw, canonical,
            )
            if STRICT_VOCAB:
                raise ValueError(
                    f"Plugin '{plugin_id}': permission '{raw}' is a deprecated alias. "
                    f"Use '{canonical}' instead. (AURORAZ_STRICT_PERM_VOCAB is on.)"
                )
        out.append(canonical)
    seen: set[str] = set()
    deduped: list[str] = []
    for p in out:
        if p not in seen:
            seen.add(p)
            deduped.append(p)
    return deduped


def is_known_permission(canonical: str) -> bool:
    """For linters/UI: is this a recognized canonical permission?"""
    if canonical in CANONICAL_PERMISSIONS:
        return True
    if canonical.startswith("network:") and len(canonical) > len("network:"):
        return True
    return False
