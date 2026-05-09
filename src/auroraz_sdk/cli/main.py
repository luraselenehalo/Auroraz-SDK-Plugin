"""AURORAZ Plugin SDK CLI entry point."""

from __future__ import annotations

import click

from .commands.dev import dev_command
from .commands.init import init_command
from .commands.lock import lock_command
from .commands.pack import pack_command
from .commands.validate import validate_command


@click.group()
@click.version_option(version="1.0.0", prog_name="auroraz-sdk")
def cli():
    """AURORAZ Plugin SDK — Developer CLI."""


cli.add_command(init_command, name="init")
cli.add_command(validate_command, name="validate")
cli.add_command(lock_command, name="lock")
cli.add_command(pack_command, name="pack")
cli.add_command(dev_command, name="dev")


def main():
    cli()


if __name__ == "__main__":
    main()
