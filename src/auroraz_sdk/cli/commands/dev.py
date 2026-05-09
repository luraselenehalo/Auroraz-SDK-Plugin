"""auroraz-sdk dev — run plugin locally, attached to a running AURORAZ core."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path

import click

from .._utils import find_plugin_dir, load_manifest


@click.command(help="Run the plugin attached to a local AURORAZ core (auto-reload on file changes).")
@click.option(
    "--path",
    "plugin_path",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
)
@click.option(
    "--core-url",
    default="http://localhost:8741",
    show_default=True,
    help="AURORAZ core HTTP URL — used to fetch the IPC address.",
)
@click.option("--no-reload", is_flag=True, help="Disable auto-reload on file changes.")
def dev_command(plugin_path: Path | None, core_url: str, no_reload: bool):
    plugin_dir = find_plugin_dir(plugin_path) if plugin_path is None else plugin_path.resolve()
    manifest = load_manifest(plugin_dir)
    plugin_id = manifest.get("id") or plugin_dir.name
    entry = plugin_dir / (manifest.get("sdk_entry") or "backend/main.py")
    if not entry.exists():
        raise click.ClickException(f"entry not found: {entry}")

    click.echo(f"Starting plugin in dev mode: {plugin_id}")
    click.echo(f"Connecting to AURORAZ core at {core_url}...")

    ipc_addr = _fetch_ipc_address(core_url)
    if not ipc_addr:
        raise click.ClickException(
            f"Could not reach core at {core_url}/api/sdk/ipc-address. "
            "Is AURORAZ running? Start it before `auroraz-sdk dev`."
        )
    click.echo("\u2713 Connected")
    click.echo(f"\u2713 Plugin registered (IPC: {ipc_addr})")
    click.echo(f"[{plugin_id}] Ready — watching for file changes...")

    runner = _PluginRunner(entry, plugin_id, ipc_addr)
    runner.start()

    if no_reload:
        try:
            runner.wait()
        except KeyboardInterrupt:
            runner.stop()
        return

    try:
        _watch(plugin_dir / "backend", runner)
    except KeyboardInterrupt:
        click.echo("")
        click.echo(f"[{plugin_id}] Stopping...")
        runner.stop()


def _fetch_ipc_address(core_url: str) -> str | None:
    try:
        import httpx
    except ImportError:
        click.echo("httpx not installed — cannot fetch IPC address.")
        return None
    try:
        r = httpx.get(f"{core_url.rstrip('/')}/api/sdk/ipc-address", timeout=3.0)
        r.raise_for_status()
        data = r.json()
        return data.get("address") or None
    except Exception as e:
        click.echo(f"  ! {e}")
        return None


class _PluginRunner:
    def __init__(self, entry: Path, plugin_id: str, ipc_addr: str):
        self.entry = entry
        self.plugin_id = plugin_id
        self.ipc_addr = ipc_addr
        self.proc: subprocess.Popen | None = None

    def start(self):
        env = os.environ.copy()
        env["AURORAZ_IPC_ADDR"] = self.ipc_addr
        env["AURORAZ_PLUGIN_ID"] = self.plugin_id
        self.proc = subprocess.Popen(
            [sys.executable, str(self.entry)],
            env=env,
            cwd=str(self.entry.parent.parent),
        )

    def restart(self):
        click.echo(f"[{self.plugin_id}] file changed — restarting")
        self.stop()
        self.start()

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                if os.name == "nt":
                    self.proc.send_signal(signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
                else:
                    self.proc.terminate()
                self.proc.wait(timeout=5)
            except Exception:
                self.proc.kill()
        self.proc = None

    def wait(self):
        if self.proc:
            self.proc.wait()


def _watch(path: Path, runner: _PluginRunner):
    try:
        from watchfiles import watch
    except ImportError:
        click.echo("watchfiles not installed — running without auto-reload (Ctrl+C to stop).")
        runner.wait()
        return

    for _changes in watch(str(path), stop_event=None):
        runner.restart()
