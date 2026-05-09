"""Stub for AURORAZ's ``config.settings`` when running outside the desktop app.

Plugin authors using the SDK don't have AURORAZ's real config; the desktop
sets up paths from its own settings module on load. This stub provides
just enough surface (``PLUGINS_DIR``, ``DATA_PATH``) for SDK code that
incidentally references the namespace not to crash. Override via env vars.
"""

import os
from pathlib import Path
from types import SimpleNamespace

_data_path = Path(os.environ.get("AURORAZ_DATA_PATH", Path.cwd() / ".aurorazdata"))
_plugins_dir = Path(os.environ.get("AURORAZ_PLUGINS_DIR", Path.cwd() / "plugins"))

settings = SimpleNamespace(
    DATA_PATH=_data_path,
    PLUGINS_DIR=_plugins_dir,
    PLUGINS_DATA_ROOT=_data_path / "plugins",
    PLUGINS_STATE_FILE=_data_path / "plugins" / "plugins.json",
    BACKUPS_PATH=_data_path / "backups",
    AURORAZ_CORE_URL=os.environ.get("AURORAZ_CORE_URL", "http://localhost:8741"),
)
