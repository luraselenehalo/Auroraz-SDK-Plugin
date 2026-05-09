"""Plugin-specific exceptions."""


class PluginError(Exception):
    """Base exception for all plugin errors."""

    def __init__(self, plugin_id: str = "", message: str = ""):
        self.plugin_id = plugin_id
        super().__init__(f"[{plugin_id}] {message}" if plugin_id else message)


class PluginNotFoundError(PluginError):
    """Plugin ID does not exist in registry or filesystem."""


class PluginManifestError(PluginError):
    """Manifest is missing, malformed, or fails validation."""


class PluginLoadError(PluginError):
    """Plugin module could not be imported or instantiated."""


class PluginPermissionError(PluginError):
    """Plugin attempted an action it lacks permission for."""


class PluginDependencyError(PluginError):
    """A required dependency plugin is missing or disabled."""


class PluginVersionError(PluginError):
    """Plugin requires a newer AURORAZ version."""
