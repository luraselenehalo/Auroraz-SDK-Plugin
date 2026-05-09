"""AURORAZPlugin — Base class for all AURORAZ plugins.

Every plugin must subclass this. The PluginLoader instantiates the plugin
class after validating the manifest, injecting sandboxed services.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from auroraz_sdk.types import PluginManifest, PluginServices


class AURORAZPlugin:
    """Base class every plugin must extend."""

    def __init__(self, manifest: PluginManifest, services: PluginServices) -> None:
        self.manifest = manifest
        self.id = manifest.id
        self.name = manifest.name
        self.version = manifest.version

        # Sandboxed service accessors (injected by loader)
        self.services = services
        self.memory = services.memory
        self.llm = services.llm
        self.embeddings = services.embeddings
        self.event_bus = services.event_bus
        self.settings = services.settings
        self.data_path = services.data_path

    # ── Lifecycle hooks (override as needed) ───────────────────

    async def on_install(self) -> None:
        """Called once when the plugin is first installed."""

    async def on_enable(self) -> None:
        """Called when the plugin is enabled (including on startup)."""

    async def on_disable(self) -> None:
        """Called when the plugin is disabled by the user."""

    async def on_uninstall(self) -> None:
        """Called before the plugin is removed. Clean up data here."""

    # ── Optional overrides ─────────────────────────────────────

    def get_router(self) -> Any:
        """Return a FastAPI APIRouter for this plugin's HTTP endpoints.

        Default: None (loader uses manifest entry_points.router instead).
        """
        return None

    def get_tools(self) -> list:
        """Return a list of agent tool callables.

        Default: empty (loader uses manifest entry_points.tools instead).
        """
        return []

    def get_context_hooks(self) -> list:
        """Return ContextHook objects for chat pipeline injection.

        Default: empty (loader uses manifest entry_points.context_hooks instead).
        """
        return []

    def get_working_memory_hooks(self) -> list:
        """Return WorkingMemoryHook objects.

        Default: empty.
        """
        return []
