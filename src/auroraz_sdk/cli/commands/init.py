"""auroraz-sdk init <plugin-name> — scaffold a new plugin project."""

from __future__ import annotations

from pathlib import Path

import click

from .._utils import echo_ok, humanize, render_template, slugify


@click.command(help="Scaffold a new plugin project from a template.")
@click.argument("plugin_name")
@click.option("--ui", "with_ui", is_flag=True, default=False, help="Also create frontend/Panel.jsx")
@click.option(
    "--integration",
    "is_integration",
    is_flag=True,
    default=False,
    help="Shortcut for --type integration",
)
@click.option(
    "--type",
    "plugin_type",
    type=click.Choice(["tool", "ui", "integration"]),
    default="tool",
    show_default=True,
)
@click.option(
    "--dir",
    "target_dir",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help="Parent directory for the new plugin (default: cwd).",
)
def init_command(
    plugin_name: str,
    with_ui: bool,
    is_integration: bool,
    plugin_type: str,
    target_dir: Path | None,
):
    """Create ./<plugin-name>/ with manifest, backend stub, requirements files."""
    if is_integration:
        plugin_type = "integration"
    if plugin_type == "ui":
        with_ui = True

    plugin_id = slugify(plugin_name)
    display_name = humanize(plugin_id)
    plugin_id_py = plugin_id.replace("-", "_")
    parent = (target_dir or Path.cwd()).resolve()
    project_dir = parent / plugin_id

    if project_dir.exists():
        raise click.ClickException(f"Directory already exists: {project_dir}")

    permissions_literal = (
        '["network:api.example.com"]' if plugin_type == "integration" else "[]"
    )
    env_prefix = plugin_id_py.upper()

    ctx = {
        "plugin_id": plugin_id,
        "plugin_id_py": plugin_id_py,
        "plugin_name": display_name,
        "plugin_type": plugin_type,
        "with_ui": with_ui,
        "permissions_literal": permissions_literal,
        "env_prefix": env_prefix,
    }

    click.echo(f"Creating plugin: {plugin_id}")

    project_dir.mkdir(parents=True)
    (project_dir / "backend").mkdir()

    _write(project_dir / "plugin.yaml", render_template("plugin.yaml.j2", **ctx))
    echo_ok("plugin.yaml")

    _write(project_dir / "backend" / "__init__.py", render_template("backend_init.py.j2", **ctx))
    echo_ok("backend/__init__.py")

    _write(project_dir / "backend" / "main.py", render_template("main.py.j2", **ctx))
    echo_ok("backend/main.py")

    _write(project_dir / "requirements.txt", render_template("requirements.txt.j2", **ctx))
    echo_ok("requirements.txt")

    _write(project_dir / "requirements.lock", "")
    echo_ok("requirements.lock (empty)")

    _write(project_dir / "README.md", render_template("README.md.j2", **ctx))
    echo_ok("README.md")

    if plugin_type == "integration":
        _write(project_dir / "backend" / "auth.py", render_template("auth.py.j2", **ctx))
        echo_ok("backend/auth.py")

    if with_ui:
        (project_dir / "frontend").mkdir()
        _write(project_dir / "frontend" / "Panel.jsx", render_template("Panel.jsx.j2", **ctx))
        echo_ok("frontend/Panel.jsx")

    click.echo("")
    click.echo(f"Plugin created at: ./{project_dir.relative_to(Path.cwd()) if project_dir.is_relative_to(Path.cwd()) else project_dir}/")
    click.echo("")
    click.echo("Next steps:")
    click.echo(f"  cd {plugin_id}")
    click.echo("  auroraz-sdk validate    # check for errors")
    click.echo("  auroraz-sdk dev         # run locally")
    click.echo("  auroraz-sdk pack        # build .azpkg")


def _write(path: Path, content: str):
    path.write_text(content, encoding="utf-8")
