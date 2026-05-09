"""Plugin type definitions and service containers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional


# ── Plugin Manifest (parsed from plugin.yaml) ─────────────────────


@dataclass
class PluginManifest:
    """Parsed and validated plugin manifest."""

    id: str
    name: str
    version: str
    author: str = ""
    description: str = ""
    category: str = "tools"
    icon: str = ""
    tags: list[str] = field(default_factory=list)
    min_auroraz_version: str = "0.1.0"
    permissions: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)

    # Entry points
    entry_points: dict[str, Any] = field(default_factory=dict)
    lifecycle: dict[str, str] = field(default_factory=dict)
    settings_schema: dict[str, Any] = field(default_factory=dict)
    data: dict[str, Any] = field(default_factory=dict)

    # Resolved at load time
    plugin_dir: Optional[Path] = None
    built_in: bool = False

    # Display info (from old system compatibility)
    price: int = 0
    verified: bool = False
    core: bool = False
    screenshots: list[str] = field(default_factory=list)
    changelog: str = ""

    # Stage 2 — Plugin UI page surface. None when the plugin doesn't ship
    # a sandboxed iframe UI (back-compat: existing in-process plugins
    # mount via entry_points.frontend.panel and stay unaffected).
    frontend: dict[str, Any] = field(default_factory=dict)

    # Stage 3 — sidecar copy of the YAML's permission list as authored,
    # before alias normalization. Used by the API to surface deprecation
    # badges in the UI; runtime checks always use `permissions` (canonical).
    raw_permissions: list[str] = field(default_factory=list)


# ── Plugin Services (dependency injection) ─────────────────────────


@dataclass
class PluginServices:
    """Sandboxed service accessors provided to each plugin instance."""

    memory: Any = None          # NamespacedMemoryAccess
    llm: Any = None             # LLMService reference
    embeddings: Any = None      # EmbeddingService reference
    event_bus: Any = None       # PluginEventBus reference
    settings: Any = None        # PluginSettingsStore (per-plugin)
    data_path: Path = None      # Plugin's writable data directory
    working_memory: Any = None  # WorkingMemory reference (if permitted)
    sdk_token: Optional[str] = None  # SDK proxy token (if anthropic_sdk permitted)


# ── Context Hook ───────────────────────────────────────────────────


@dataclass
class ContextHook:
    """A registered context injection hook for the chat pipeline."""

    plugin_id: str
    name: str
    function: Callable  # async def hook(message, k_level, context) -> str
    priority: int = 100  # Lower = earlier execution
    k_levels: list[int] = field(default_factory=lambda: [0, 1, 2, 3])


@dataclass
class WorkingMemoryHook:
    """Hook to enrich working memory metadata on each message."""

    plugin_id: str
    name: str
    function: Callable  # def hook(role, message) -> dict | None


# ── Loaded Plugin Reference ────────────────────────────────────────


@dataclass
class LoadedPlugin:
    """Runtime reference to a loaded and active plugin."""

    manifest: PluginManifest
    instance: Any = None        # AURORAZPlugin subclass instance
    router: Any = None          # FastAPI APIRouter (if any)
    tools: list[Any] = field(default_factory=list)
    context_hooks: list[ContextHook] = field(default_factory=list)
    wm_hooks: list[WorkingMemoryHook] = field(default_factory=list)
