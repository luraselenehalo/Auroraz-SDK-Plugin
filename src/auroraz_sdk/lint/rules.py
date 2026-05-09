"""Lint rules — pure-Python `ast` analysis (no `exec`, no `eval`).

Each rule takes ``(manifest, code_index)`` and returns ``list[Diagnostic]``.
Rule ids follow a fixed taxonomy:

* MAN xxx  — manifest issues
* DOC xxx  — documentation / metadata quality
* PERM xxx — permission issues
* API xxx  — aurora.* API contract issues
* TOOL xxx — tool declaration issues
* SYN xxx  — syntax / parse issues (raised by CodeIndex)
* LINT xxx — internal linter errors
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Callable

from auroraz_sdk.lint.diagnostics import Diagnostic
from auroraz_sdk.permission_vocab import (
    PERMISSION_ALIASES,
    is_known_permission,
    normalize_permission,
)


# ── Code index ────────────────────────────────────────────────────


class CodeIndex:
    """Pre-parsed AST + extracted facts about a plugin's Python files.

    Walks every ``.py`` under the plugin folder once, collecting:

    * ``aurora_calls`` — dotted ``aurora.X.Y`` invocations + lineno
    * ``declared_tools`` — names from ``@tool``/``@tool(name=)``/
      ``Plugin.register_tool('name', ...)`` and similar shapes
    * ``parse_errors`` — Diagnostics for files that don't parse
    """

    def __init__(self, plugin_dir: Path):
        self.plugin_dir = plugin_dir
        self.files: dict[str, ast.AST] = {}
        self.aurora_calls: list[tuple[str, str, int]] = []
        self.declared_tools: set[str] = set()
        self.parse_errors: list[Diagnostic] = []

    @classmethod
    def build(cls, plugin_dir: Path) -> "CodeIndex":
        idx = cls(plugin_dir)
        for py in sorted(plugin_dir.rglob("*.py")):
            # Skip dotfile/dunder cache directories (`__pycache__`, `.venv`).
            rel_parts = py.relative_to(plugin_dir).parts
            if any(p.startswith(".") or p == "__pycache__" for p in rel_parts):
                continue
            rel = py.relative_to(plugin_dir).as_posix()
            try:
                source = py.read_text(encoding="utf-8")
            except OSError as e:
                idx.parse_errors.append(Diagnostic(
                    severity="error", code="SYN002",
                    message=f"Could not read file: {e}",
                    file=rel,
                ))
                continue
            try:
                tree = ast.parse(source, filename=rel)
            except SyntaxError as e:
                idx.parse_errors.append(Diagnostic(
                    severity="error", code="SYN001",
                    message=f"Python syntax error: {e.msg}",
                    file=rel,
                    line=e.lineno,
                    column=e.offset,
                ))
                continue
            idx.files[rel] = tree
            idx._scan(tree, rel)
        return idx

    def _scan(self, tree: ast.AST, file: str) -> None:
        for node in ast.walk(tree):
            # aurora.X.Y(...) detection
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                dotted = self._dotted(node.func)
                if dotted and dotted.startswith("aurora."):
                    self.aurora_calls.append((file, dotted, node.lineno))
            # Tool declarations: @tool, @tool(name=...), Plugin.register_tool(...)
            if isinstance(node, ast.FunctionDef):
                for dec in node.decorator_list:
                    # @tool — bare decorator → name defaults to function name
                    if isinstance(dec, ast.Name) and dec.id == "tool":
                        self.declared_tools.add(node.name)
                    # @tool(name="x", ...) — parse keyword `name`
                    if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name) and dec.func.id == "tool":
                        explicit = self._kwarg_str(dec, "name")
                        if explicit:
                            self.declared_tools.add(explicit)
                        else:
                            self.declared_tools.add(node.name)
            # plugin.register_tool('name', ...) / register_tool(name='x', ...)
            if isinstance(node, ast.Call):
                func = node.func
                attr_name = None
                if isinstance(func, ast.Attribute):
                    attr_name = func.attr
                elif isinstance(func, ast.Name):
                    attr_name = func.id
                if attr_name == "register_tool":
                    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                        self.declared_tools.add(node.args[0].value)
                    explicit = self._kwarg_str(node, "name")
                    if explicit:
                        self.declared_tools.add(explicit)

    @staticmethod
    def _dotted(node: ast.AST) -> str | None:
        """Walk an Attribute chain and return ``a.b.c`` or None."""
        parts: list[str] = []
        cur = node
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
            return ".".join(reversed(parts))
        return None

    @staticmethod
    def _kwarg_str(call: ast.Call, name: str) -> str | None:
        for kw in call.keywords:
            if kw.arg == name and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                return kw.value.value
        return None


# ── aurora.* permission contract ──────────────────────────────────
# Source of truth — must mirror sdk/aurora_client.py + ipc_server._METHOD_PERMS.
# `aurora.say` is intentionally absent: the IPC layer marks it ALWAYS_ALLOWED.

AURORA_API_PERMISSIONS: dict[str, str] = {
    "aurora.memory.store":      "memory:write",
    "aurora.memory.get":        "memory:read",
    "aurora.memory.remember":   "memory:write",
    "aurora.memory.search":     "memory:read",
    "aurora.context.get_emotion": "context:read",
    "aurora.context.get_intent":  "context:read",
    "aurora.context.get_window":  "context:read",
    "aurora.notify":            "notifications:show",
    "aurora.inject":            "context:inject",
    "aurora.get_last_message":  "context:read",
}

# Names a plugin should not steal from the host catalog.
BUILTIN_TOOLS = {
    "web_search", "web_fetch",
    "memory_search", "memory_recall",
    "code_execute", "image_generate",
    "say", "inject", "notify",
}


# ── Manifest rules ────────────────────────────────────────────────


def rule_manifest_required_fields(manifest, code_index) -> list[Diagnostic]:
    """MAN001/002/003 — id/name/version are required."""
    out: list[Diagnostic] = []
    if not getattr(manifest, "id", None):
        out.append(Diagnostic(
            severity="error", code="MAN001",
            message="Manifest missing required field 'id'",
            field="id",
        ))
    if not getattr(manifest, "name", None):
        out.append(Diagnostic(
            severity="error", code="MAN002",
            message="Manifest missing required field 'name'",
            field="name",
        ))
    if not getattr(manifest, "version", None):
        out.append(Diagnostic(
            severity="error", code="MAN003",
            message="Manifest missing required field 'version'",
            field="version",
        ))
    return out


def rule_manifest_id_format(manifest, code_index) -> list[Diagnostic]:
    """MAN004 — id must match the safe regex used by the scaffolder."""
    if not manifest.id:
        return []
    if not re.match(r"^[a-z][a-z0-9_-]{1,49}$", manifest.id):
        return [Diagnostic(
            severity="error", code="MAN004",
            message=(
                f"Plugin id {manifest.id!r} must be lowercase, start with a "
                "letter, contain only [a-z0-9_-], 2-50 chars"
            ),
            field="id",
            suggestion="Examples: 'my-plugin', 'spotify_pro', 'discord-bot'",
        )]
    return []


def rule_manifest_version_format(manifest, code_index) -> list[Diagnostic]:
    """MAN005 — version should look like semver."""
    if not manifest.version:
        return []
    if not re.match(r"^\d+\.\d+\.\d+([-+].+)?$", manifest.version):
        return [Diagnostic(
            severity="warn", code="MAN005",
            message=f"Version {manifest.version!r} doesn't look like semver (X.Y.Z)",
            field="version",
            suggestion="Use X.Y.Z, e.g. '1.0.0' or '0.1.0-beta'",
        )]
    return []


def rule_manifest_description_quality(manifest, code_index) -> list[Diagnostic]:
    """DOC001/002 — encourage useful descriptions."""
    desc = (getattr(manifest, "description", "") or "").strip()
    if not desc:
        return [Diagnostic(
            severity="warn", code="DOC001",
            message="No description provided",
            field="description",
            suggestion="Add a 1-sentence description of what your plugin does",
        )]
    if len(desc) < 10:
        return [Diagnostic(
            severity="info", code="DOC002",
            message="Description is very short",
            field="description",
        )]
    return []


# ── Permission rules ──────────────────────────────────────────────


def rule_perm_unknown(manifest, code_index) -> list[Diagnostic]:
    """PERM001 — declared permission isn't recognized as canonical."""
    out: list[Diagnostic] = []
    raw_perms = list(getattr(manifest, "raw_permissions", None) or manifest.permissions or [])
    for i, raw in enumerate(raw_perms):
        canonical, _ = normalize_permission(raw)
        if not is_known_permission(canonical):
            out.append(Diagnostic(
                severity="warn", code="PERM001",
                message=f"Permission {raw!r} is not recognized",
                field=f"permissions[{i}]",
                suggestion=(
                    f"Check spelling. If {raw!r} is a custom permission "
                    "your plugin defines, you can ignore this."
                ),
            ))
    return out


def rule_perm_deprecated(manifest, code_index) -> list[Diagnostic]:
    """PERM002 — declared permission uses a deprecated alias."""
    out: list[Diagnostic] = []
    raw_perms = list(getattr(manifest, "raw_permissions", None) or manifest.permissions or [])
    for i, raw in enumerate(raw_perms):
        if raw in PERMISSION_ALIASES:
            canonical = PERMISSION_ALIASES[raw]
            out.append(Diagnostic(
                severity="info", code="PERM002",
                message=f"Permission {raw!r} is a deprecated alias",
                field=f"permissions[{i}]",
                suggestion=f"Replace with canonical form: {canonical!r}",
            ))
    return out


def rule_perm_unused(manifest, code_index) -> list[Diagnostic]:
    """PERM003 — declared permission is never used in code.

    network and network:<host> are exempted (HTTP usage isn't routed
    through aurora.*, so AST analysis can't see it). In-process-only
    permissions (process:scan, anthropic:proxy, working_memory:*) are
    similarly not exercised through aurora.*.
    """
    declared = set(manifest.permissions or [])
    used: set[str] = set()
    for _, dotted, _ in code_index.aurora_calls:
        req = AURORA_API_PERMISSIONS.get(dotted)
        if req:
            used.add(req)
    used.add("network")
    used.update(p for p in declared if p.startswith("network:"))
    INPROCESS_ONLY = {"process:scan", "anthropic:proxy",
                      "working_memory:read", "working_memory:write"}
    out: list[Diagnostic] = []
    for perm in sorted(declared - used):
        if perm in INPROCESS_ONLY:
            continue
        out.append(Diagnostic(
            severity="info", code="PERM003",
            message=f"Permission {perm!r} declared but never used in code",
            field="permissions",
            suggestion="Remove from manifest if not needed",
        ))
    return out


def rule_api_perm_missing(manifest, code_index) -> list[Diagnostic]:
    """API001 — code calls aurora.X.Y but the gating permission isn't declared."""
    out: list[Diagnostic] = []
    declared = set(manifest.permissions or [])
    seen: set[tuple[str, str]] = set()
    for file, dotted, lineno in code_index.aurora_calls:
        key = (file, dotted)
        if key in seen:
            continue
        seen.add(key)
        required = AURORA_API_PERMISSIONS.get(dotted)
        if required and required not in declared:
            out.append(Diagnostic(
                severity="error", code="API001",
                message=f"Code calls {dotted}() but permission {required!r} is not declared",
                file=file, line=lineno,
                suggestion=f"Add '{required}' to manifest 'permissions:'",
            ))
    return out


# ── Tool rules ────────────────────────────────────────────────────


def rule_tool_collision_builtin(manifest, code_index) -> list[Diagnostic]:
    """TOOL001 — tool name collides with a built-in."""
    out: list[Diagnostic] = []
    pid = manifest.id or "your_plugin"
    pid_snake = pid.replace("-", "_")
    for name in sorted(code_index.declared_tools):
        if name in BUILTIN_TOOLS:
            out.append(Diagnostic(
                severity="error", code="TOOL001",
                message=f"Tool name {name!r} collides with a built-in tool",
                suggestion=f"Prefix with your plugin id, e.g. {pid_snake}_{name}",
            ))
    return out


def rule_tool_naming_convention(manifest, code_index) -> list[Diagnostic]:
    """TOOL002 — encourage tool names to be prefixed with the plugin id.

    Reduces collisions across plugins and makes it obvious in the agent's
    catalog where a tool came from. info-level, not error.
    """
    if not manifest.id:
        return []
    pid_snake = manifest.id.replace("-", "_") + "_"
    out: list[Diagnostic] = []
    for name in sorted(code_index.declared_tools):
        if name in BUILTIN_TOOLS:
            continue  # already flagged by TOOL001 — don't double-warn
        if not name.startswith(pid_snake):
            out.append(Diagnostic(
                severity="info", code="TOOL002",
                message=f"Tool {name!r} is not prefixed with the plugin id",
                suggestion=f"Consider renaming to '{pid_snake}{name}' to avoid collisions",
            ))
    return out


# ── Registry — ordered ────────────────────────────────────────────

ALL_RULES: list[tuple[str, Callable]] = [
    ("MAN001-003", rule_manifest_required_fields),
    ("MAN004", rule_manifest_id_format),
    ("MAN005", rule_manifest_version_format),
    ("DOC001-002", rule_manifest_description_quality),
    ("PERM001", rule_perm_unknown),
    ("PERM002", rule_perm_deprecated),
    ("PERM003", rule_perm_unused),
    ("API001", rule_api_perm_missing),
    ("TOOL001", rule_tool_collision_builtin),
    ("TOOL002", rule_tool_naming_convention),
]
