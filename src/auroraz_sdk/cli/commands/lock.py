"""auroraz-sdk lock — generate requirements.lock with sha256 hashes."""

from __future__ import annotations

from pathlib import Path

import click

from ...dependency_verifier import DependencyVerifier
from .._utils import find_plugin_dir


@click.command(help="Generate requirements.lock from requirements.txt.")
@click.option(
    "--path",
    "plugin_path",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
)
def lock_command(plugin_path: Path | None):
    plugin_dir = find_plugin_dir(plugin_path) if plugin_path is None else plugin_path.resolve()
    req_path = plugin_dir / "requirements.txt"
    if not req_path.exists():
        raise click.ClickException("requirements.txt not found")

    click.echo("Generating requirements.lock...")
    verifier = DependencyVerifier()
    content = verifier.generate_lock(plugin_dir)

    for line in content.splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            click.echo(f"  {line}")

    lock_path = plugin_dir / "requirements.lock"
    lock_path.write_text(content + ("\n" if content and not content.endswith("\n") else ""), encoding="utf-8")
    click.echo("")
    click.echo(f"Written: {lock_path.relative_to(plugin_dir.parent) if lock_path.is_relative_to(plugin_dir.parent) else lock_path}")
