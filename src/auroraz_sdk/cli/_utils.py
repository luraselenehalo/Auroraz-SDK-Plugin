"""Shared helpers for CLI commands."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import click

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def slugify(name: str) -> str:
    """Convert plugin name to a safe id: lowercase, alnum + hyphens."""
    s = name.strip().lower()
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"[^a-z0-9-]", "", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "plugin"


def humanize(slug: str) -> str:
    """Turn 'my-awesome-plugin' into 'My Awesome Plugin'."""
    return " ".join(part.capitalize() for part in slug.split("-") if part)


def render_template(template_name: str, **context) -> str:
    """Render a Jinja2 template from the bundled templates dir."""
    from jinja2 import Environment, FileSystemLoader, StrictUndefined

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    template = env.get_template(template_name)
    return template.render(**context)


def find_plugin_dir(start: Optional[Path] = None) -> Path:
    """Return the directory containing plugin.yaml, walking up from start."""
    here = (start or Path.cwd()).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "plugin.yaml").exists():
            return candidate
    raise click.ClickException(
        f"plugin.yaml not found at {here} or any parent directory. "
        "Run this command inside a plugin project."
    )


def load_manifest(plugin_dir: Path) -> dict:
    """Load plugin.yaml as a dict (PyYAML required)."""
    import yaml

    manifest_path = plugin_dir / "plugin.yaml"
    with manifest_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise click.ClickException("plugin.yaml must be a mapping at the top level")
    return data


def echo_ok(msg: str):
    click.echo(click.style("\u2713 ", fg="green") + msg)


def echo_warn(msg: str):
    click.echo(click.style("\u26a0 ", fg="yellow") + msg)


def echo_err(msg: str):
    click.echo(click.style("\u2717 ", fg="red") + msg)
