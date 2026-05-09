"""Plugin manifest parser — reads and validates plugin.yaml files."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from auroraz_sdk.plugin_exceptions import PluginManifestError
from auroraz_sdk.permission_vocab import normalize_permissions
from auroraz_sdk.types import PluginManifest

log = logging.getLogger(__name__)

REQUIRED_FIELDS = {"id", "name", "version"}


def parse_manifest(plugin_dir: Path) -> PluginManifest:
    """Parse plugin.yaml from a plugin directory.

    Falls back to plugin.json if YAML is unavailable.
    Raises PluginManifestError on missing/invalid manifest.
    """
    yaml_path = plugin_dir / "plugin.yaml"
    json_path = plugin_dir / "plugin.json"

    raw: dict[str, Any] = {}

    if yaml_path.exists():
        raw = _load_yaml(yaml_path)
    elif json_path.exists():
        raw = _load_json(json_path)
    else:
        raise PluginManifestError(
            plugin_dir.name,
            f"No plugin.yaml or plugin.json found in {plugin_dir}",
        )

    return _validate_and_build(raw, plugin_dir)


def _load_yaml(path: Path) -> dict:
    """Load YAML manifest. Falls back to simple parser if PyYAML not installed."""
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        # Fallback: try loading as JSON (some YAML is valid JSON)
        return _load_json(path)
    except Exception as e:
        raise PluginManifestError(path.parent.name, f"Failed to parse YAML: {e}")


def _load_json(path: Path) -> dict:
    """Load JSON manifest."""
    import json
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise PluginManifestError(path.parent.name, f"Failed to parse JSON: {e}")


def _validate_and_build(raw: dict, plugin_dir: Path) -> PluginManifest:
    """Validate required fields and build PluginManifest."""
    plugin_id = raw.get("id", plugin_dir.name)

    missing = REQUIRED_FIELDS - set(raw.keys())
    if missing:
        raise PluginManifestError(
            plugin_id,
            f"Missing required fields: {', '.join(sorted(missing))}",
        )

    entry_points = raw.get("entry_points", {})
    frontend = entry_points.get("frontend", {})

    # Build nav_items from frontend config
    nav_items = frontend.get("nav_items", [])
    if not nav_items and frontend.get("panel"):
        # Auto-generate a single nav item from plugin metadata
        nav_items = [{
            "id": plugin_id,
            "label": raw.get("name", plugin_id),
            "icon": raw.get("icon", ""),
        }]

    # Stage 2 — top-level `frontend:` block declares the sandboxed iframe
    # UI surface. Distinct from `entry_points.frontend.panel` (used by
    # in-process plugins to mount a React component). Optional —
    # plugins without a UI page just omit this block.
    frontend_block = raw.get("frontend") or {}
    if not isinstance(frontend_block, dict):
        raise PluginManifestError(plugin_id, "`frontend` block must be a mapping")
    ui_entry = frontend_block.get("ui_entry")
    if ui_entry is not None:
        if not isinstance(ui_entry, str) or not ui_entry.strip():
            raise PluginManifestError(plugin_id, "`frontend.ui_entry` must be a non-empty string")
        # Path-traversal + absolute-path guard. The static-file route
        # later resolves under <plugin_dir>/<ui_entry>; reject anything
        # that could escape that subtree.
        from pathlib import PurePosixPath
        norm = PurePosixPath(ui_entry.replace("\\", "/"))
        if norm.is_absolute() or any(part == ".." for part in norm.parts):
            raise PluginManifestError(plugin_id, "`frontend.ui_entry` must be a relative path inside the plugin folder")
    icon = frontend_block.get("icon")
    if icon is not None:
        if not isinstance(icon, str):
            raise PluginManifestError(plugin_id, "`frontend.icon` must be a string")
        # Length > 4 implies a path to a PNG/SVG file rather than an
        # emoji glyph. We don't enforce existence here (the static
        # serving route will 404 on miss), just shape.
    display_name = frontend_block.get("display_name")
    if display_name is not None and not isinstance(display_name, str):
        raise PluginManifestError(plugin_id, "`frontend.display_name` must be a string")
    status_strip = frontend_block.get("status_strip", [])
    if status_strip and not isinstance(status_strip, list):
        raise PluginManifestError(plugin_id, "`frontend.status_strip` must be a list")

    # Stage 3 — normalize permissions to canonical colon form. Underscore
    # and dot aliases get warning logs + canonical mapping. Strict mode
    # (AURORAZ_STRICT_PERM_VOCAB=1) raises here, blocking startup for
    # any plugin still on the old vocabulary. Raw form is preserved on
    # the manifest for the API + UI deprecation badges.
    raw_perms = list(raw.get("permissions") or [])
    canonical_perms = normalize_permissions(raw_perms, plugin_id=plugin_id)

    manifest = PluginManifest(
        id=plugin_id,
        name=raw["name"],
        version=raw["version"],
        author=raw.get("author", ""),
        description=raw.get("description", ""),
        category=raw.get("category", "tools"),
        icon=raw.get("icon", ""),
        tags=raw.get("tags", []),
        min_auroraz_version=raw.get("min_auroraz_version", "0.1.0"),
        permissions=canonical_perms,
        dependencies=raw.get("dependencies", []),
        entry_points=entry_points,
        lifecycle=raw.get("lifecycle", {}),
        settings_schema=raw.get("settings", {}),
        data=raw.get("data", {}),
        plugin_dir=plugin_dir,
        built_in=raw.get("built_in", False),
        price=raw.get("price", 0),
        verified=raw.get("verified", False),
        core=raw.get("core", False),
        screenshots=raw.get("screenshots", []),
        changelog=raw.get("changelog", ""),
        frontend=frontend_block,
        raw_permissions=raw_perms,
    )

    log.debug("[Manifest] Parsed: %s v%s from %s", manifest.id, manifest.version, plugin_dir)
    return manifest
