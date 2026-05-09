"""Plugin scaffolder — Stage 4 wizard backend.

Security model:
  * ``plugin_id`` must match a strict regex (the same one MAN004 lints).
  * Target path is resolved with ``Path.resolve()`` and confirmed to live
    inside ``settings.PLUGINS_DIR`` before any write — defeats `..`/abs.
  * Existing plugin folders are NEVER overwritten.
  * Files are written via temp-file + ``Path.replace()`` so a half-written
    file can't be observed by the registry.
  * On any failure mid-walk the partially-created folder is removed.

The substitution model is intentionally simple: every template uses
``__TOKEN__`` placeholders and we ``str.replace()`` each one. No format
strings — that lets templates contain Python f-strings and `{}` syntax
without escaping headaches.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Iterable, Literal

from auroraz_sdk.permission_vocab import normalize_permissions

PluginType = Literal["in-process", "subprocess"]

_PLUGIN_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{1,49}$")
_TEMPLATES_ROOT = Path(__file__).parent / "templates"


class ScaffoldError(Exception):
    """Raised when scaffolding fails for a recoverable reason (validation,
    pre-existing folder, path traversal, etc.). The API maps this to 400.
    """


def scaffold_plugin(
    *,
    plugin_id: str,
    name: str,
    version: str,
    description: str,
    author: str,
    category: str,
    icon: str,
    plugin_type: PluginType,
    permissions: Iterable[str],
    include_ui: bool,
    target_root: Path | None = None,
) -> Path:
    """Create a new plugin folder. Returns the path.

    ``target_root`` overrides the default ``settings.PLUGINS_DIR`` (used by
    tests). Caller-provided permissions are normalized to canonical form
    via Stage 3's ``normalize_permissions``.
    """
    if not _PLUGIN_ID_RE.match(plugin_id):
        raise ScaffoldError(
            f"Invalid plugin_id {plugin_id!r}. Must be lowercase, "
            "start with a letter, contain only [a-z0-9_-], 2-50 chars."
        )

    if not name or not name.strip():
        raise ScaffoldError("'name' is required and must be non-empty")
    if not version or not version.strip():
        raise ScaffoldError("'version' is required and must be non-empty")

    if plugin_type not in ("in-process", "subprocess"):
        raise ScaffoldError(f"Unknown plugin_type: {plugin_type!r}")

    if target_root is None:
        from auroraz_sdk._stub_config import settings as _settings
        target_root = _settings.PLUGINS_DIR
    root = target_root.resolve()

    target = (root / plugin_id).resolve()
    # Path-traversal guard. plugin_id matched the safe regex above, so
    # this is belt-and-braces; the resolved path must still live under
    # the resolved plugins root.
    try:
        target.relative_to(root)
    except ValueError:
        raise ScaffoldError(f"Resolved target path escapes plugins dir: {target}")

    if target.exists():
        raise ScaffoldError(f"Plugin folder already exists: {plugin_id}")

    canonical_perms = normalize_permissions(list(permissions or []), plugin_id=plugin_id)

    plugin_id_snake = plugin_id.replace("-", "_")
    class_name = _to_class_name(plugin_id) + "Plugin"
    permissions_yaml = _format_perms_yaml(canonical_perms)
    permissions_python = repr(canonical_perms)
    subs = {
        "__PLUGIN_ID__": plugin_id,
        "__PLUGIN_ID_SNAKE__": plugin_id_snake,
        "__CLASS_NAME__": class_name,
        "__NAME__": name,
        "__VERSION__": version,
        "__DESCRIPTION__": description or "",
        "__AUTHOR__": author or "Anonymous",
        "__CATEGORY__": category or "tools",
        "__ICON__": icon or "🧩",
        "__PERMISSIONS_YAML__": permissions_yaml,
        "__PERMISSIONS_PYTHON__": permissions_python,
    }

    if plugin_type == "in-process":
        template_dir = _TEMPLATES_ROOT / "in_process"
    else:
        template_dir = _TEMPLATES_ROOT / "subprocess"
    common_dir = _TEMPLATES_ROOT / "common"

    target.mkdir(parents=True, exist_ok=False)
    try:
        _walk_template(template_dir, target, subs)
        # README is rendered for both types. Drop the .tmpl suffix.
        _render_one(common_dir / "README.md.tmpl", target / "README.md", subs)

        if include_ui:
            ui_target = target / "ui"
            ui_target.mkdir(exist_ok=False)
            for fname in ("index.html.tmpl", "app.css.tmpl", "app.js.tmpl"):
                _render_one(common_dir / "ui" / fname,
                            ui_target / fname.removesuffix(".tmpl"),
                            subs)
            _add_frontend_block_to_manifest(target / "plugin.yaml")
    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        raise

    return target


# ── Internals ─────────────────────────────────────────────────────


def _walk_template(src: Path, dst_root: Path, subs: dict[str, str]) -> None:
    """Walk ``src`` (a template directory) and render each ``*.tmpl`` to
    its corresponding location under ``dst_root`` (with ``.tmpl`` stripped).
    Non-template files are copied verbatim.
    """
    if not src.is_dir():
        raise ScaffoldError(f"Template path not a directory: {src}")
    dst_root.mkdir(parents=True, exist_ok=True)
    for child in src.iterdir():
        rel_name = child.name.removesuffix(".tmpl") if child.name.endswith(".tmpl") else child.name
        dst = dst_root / rel_name
        if child.is_dir():
            _walk_template(child, dst, subs)
        elif child.is_file():
            _render_one(child, dst, subs)


def _render_one(src: Path, dst: Path, subs: dict[str, str]) -> None:
    """Render a single template file with placeholder substitution.

    Atomic write via a sibling .tmp file + ``Path.replace()``.
    """
    if not src.is_file():
        raise ScaffoldError(f"Template file not found: {src}")
    text = src.read_text(encoding="utf-8")
    for token, value in subs.items():
        text = text.replace(token, str(value))
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(dst)


def _format_perms_yaml(perms: list[str]) -> str:
    if not perms:
        return "  []"
    return "\n".join(f"  - {p}" for p in perms)


def _to_class_name(plugin_id: str) -> str:
    """`my-cool-plugin` → `MyCoolPlugin` minus the trailing 'Plugin'."""
    parts = re.split(r"[-_]+", plugin_id)
    return "".join(p[:1].upper() + p[1:] for p in parts if p)


def _add_frontend_block_to_manifest(manifest_path: Path) -> None:
    """Append a ``frontend:`` block to the rendered plugin.yaml when the
    user opted into a UI. Idempotent — no-op if the block exists.
    """
    text = manifest_path.read_text(encoding="utf-8")
    if "\nfrontend:" in text or text.startswith("frontend:"):
        return
    addition = (
        "\nfrontend:\n"
        "  ui_entry: ui/index.html\n"
        "  icon: \U0001F3A8\n"
    )
    manifest_path.write_text(text + addition, encoding="utf-8")
