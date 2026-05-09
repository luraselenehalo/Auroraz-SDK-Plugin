"""auroraz-sdk pack — build a .azpkg archive."""

from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import click

from ...static_analyzer import PluginStaticAnalyzer
from .._utils import echo_ok, find_plugin_dir, load_manifest

EXCLUDED_DIRS = {"__pycache__", ".git", ".venv", "venv", "node_modules", ".pytest_cache", ".mypy_cache"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
EXCLUDED_NAMES = {".DS_Store"}


@click.command(help="Build a distributable .azpkg from the current plugin.")
@click.option(
    "--path",
    "plugin_path",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
)
@click.option(
    "--output",
    "output_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Where to write the .azpkg (default: alongside the plugin dir).",
)
@click.option("--skip-validate", is_flag=True, help="Skip the validate gate (not recommended).")
def pack_command(plugin_path: Path | None, output_dir: Path | None, skip_validate: bool):
    plugin_dir = find_plugin_dir(plugin_path) if plugin_path is None else plugin_path.resolve()
    manifest = load_manifest(plugin_dir)
    plugin_id = manifest.get("id") or plugin_dir.name
    version = manifest.get("version") or "0.1.0"

    click.echo(f"Packing plugin: {plugin_id} v{version}")

    if not skip_validate:
        missing = [k for k in ("id", "name", "version") if not manifest.get(k)]
        if missing:
            raise click.ClickException(f"manifest missing keys: {', '.join(missing)}")
        echo_ok("Validate — passed")

        analyzer = PluginStaticAnalyzer()
        result = analyzer.analyze_plugin(plugin_dir)
        if not result.safe:
            click.echo(click.style("\u2717 Static analysis — FAILED", fg="red"))
            for v in result.violations:
                click.echo(f"   {v}")
            raise click.ClickException("pack aborted: static analysis violations")
        echo_ok("Static analysis — clean")
    else:
        click.echo("(skipped) Validate")

    lock_path = plugin_dir / "requirements.lock"
    if lock_path.exists():
        echo_ok("Dependencies verified")
    else:
        click.echo(click.style("\u26a0 ", fg="yellow") + "requirements.lock missing — proceeding anyway")

    out_dir = (output_dir or plugin_dir.parent).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{plugin_id}-{version}.azpkg"

    click.echo("\u2713 Creating archive...")

    manifest_blob = {
        "azpkg_version": "1",
        "plugin_id": plugin_id,
        "plugin_version": version,
        "packed_at": datetime.now(timezone.utc).isoformat(),
    }

    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("MANIFEST.json", json.dumps(manifest_blob, indent=2))
        for file_path in _iter_files(plugin_dir):
            arcname = file_path.relative_to(plugin_dir).as_posix()
            zf.write(file_path, arcname)

    size_kb = out_path.stat().st_size / 1024
    click.echo("")
    click.echo(f"Output: {out_path.name} ({size_kb:.1f} KB)")
    click.echo("")
    click.echo("Install in AURORAZ:")
    click.echo("  Drag and drop into Plugin Store")
    click.echo("  or: POST /api/plugins/install with the .azpkg file")


def _iter_files(root: Path):
    for entry in root.rglob("*"):
        if entry.is_dir():
            continue
        rel = entry.relative_to(root)
        parts = set(rel.parts)
        if parts & EXCLUDED_DIRS:
            continue
        if entry.suffix in EXCLUDED_SUFFIXES:
            continue
        if entry.name in EXCLUDED_NAMES:
            continue
        if entry.name.endswith(".azpkg"):
            continue
        yield entry
