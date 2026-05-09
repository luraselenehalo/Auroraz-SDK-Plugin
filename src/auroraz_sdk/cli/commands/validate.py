"""auroraz-sdk validate — manifest + static analysis pre-flight."""

from __future__ import annotations

from pathlib import Path

import click

from ...static_analyzer import PluginStaticAnalyzer
from .._utils import echo_err, echo_ok, echo_warn, find_plugin_dir, load_manifest


@click.command(help="Validate manifest and run static analysis on backend/.")
@click.option(
    "--path",
    "plugin_path",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Plugin directory (default: search upward from cwd).",
)
def validate_command(plugin_path: Path | None):
    plugin_dir = find_plugin_dir(plugin_path) if plugin_path is None else plugin_path.resolve()
    click.echo(f"Validating plugin at: {plugin_dir}")

    warnings = 0
    errors = 0

    # ── manifest ──────────────────────────────────────────────
    try:
        manifest = load_manifest(plugin_dir)
    except Exception as e:
        echo_err(f"plugin.yaml — invalid: {e}")
        raise click.exceptions.Exit(1)

    missing = [k for k in ("id", "name", "version") if not manifest.get(k)]
    if missing:
        echo_err(f"plugin.yaml — missing required keys: {', '.join(missing)}")
        errors += 1
    else:
        echo_ok("plugin.yaml — valid")

    # ── backend entry ────────────────────────────────────────
    entry_rel = manifest.get("sdk_entry") or "backend/main.py"
    entry_path = plugin_dir / entry_rel
    if not entry_path.exists():
        echo_err(f"{entry_rel} — not found")
        errors += 1
    else:
        echo_ok(f"{entry_rel} — found")

    # ── static analysis ──────────────────────────────────────
    analyzer = PluginStaticAnalyzer()
    result = analyzer.analyze_plugin(plugin_dir)
    backend_dir = plugin_dir / "backend"
    file_count = len(list(backend_dir.rglob("*.py"))) if backend_dir.exists() else 0

    if result.safe:
        echo_ok(f"Static analysis — {file_count} files scanned, 0 violations")
        for w in result.warnings:
            echo_warn(f"static: {w}")
            warnings += 1
    else:
        echo_err(f"Static analysis — FAILED ({len(result.violations)} violations)")
        for v in result.violations:
            click.echo(f"   {v}")
        errors += 1

    # ── lockfile ────────────────────────────────────────────
    lock_path = plugin_dir / "requirements.lock"
    req_path = plugin_dir / "requirements.txt"
    has_real_deps = req_path.exists() and any(
        line.strip() and not line.strip().startswith("#")
        for line in req_path.read_text(encoding="utf-8").splitlines()
    )
    if has_real_deps and (not lock_path.exists() or not lock_path.read_text(encoding="utf-8").strip()):
        echo_warn("requirements.lock — missing (run: auroraz-sdk lock)")
        warnings += 1

    perms = manifest.get("permissions") or []
    echo_ok(f"Permissions declared: {perms}")

    click.echo("")
    if errors:
        click.echo(click.style(f"Result: FAILED — fix violations before packing", fg="red", bold=True))
        raise click.exceptions.Exit(1)
    if warnings:
        click.echo(click.style(f"Result: READY ({warnings} warning{'s' if warnings != 1 else ''})", fg="yellow", bold=True))
    else:
        click.echo(click.style("Result: READY", fg="green", bold=True))
