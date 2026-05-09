# SDK Public API Audit (Stage 6a Phase A)

This document is the source-of-truth for what ships in `auroraz-sdk` vs.
what stays AURORAZ-internal. The build script (`tools/build_sdk.py`)
keys off this list. Any module not listed here is excluded from the
published package.

## PUBLIC (plugin authors `from auroraz_sdk import …`)

| Symbol | Source | Notes |
|---|---|---|
| `Plugin` | `backend/sdk/plugin.py` | Subprocess plugin entry — `Plugin(id, name, version, permissions)` + `plugin.run()` |
| `aurora` | `backend/sdk/__init__.py` | Lazy proxy → `AuroraClient` after `plugin.run()` |
| `AuroraClient` | `backend/sdk/aurora_client.py` | Raw client class for advanced cases |
| `tool` | `backend/sdk/decorators.py` | `@tool(name, description, when, parameters)` |
| `hook` | `backend/sdk/decorators.py` | `@hook("on_startup" \| "on_shutdown" \| …)` |
| `panel` | `backend/sdk/decorators.py` | `@panel(name)` (UI panel registration) |
| `HookContext` | `backend/sdk/context.py` | Type passed to `@hook` handlers |
| `PluginError` / `PermissionDeniedError` / `IPCError` | `backend/sdk/exceptions.py` | Error hierarchy |
| `AURORAZPlugin` | `backend/auroraz/plugin/base.py` | Optional in-process subclass base |

## PUBLIC-helper (transitively shipped — authors don't import directly)

| Module | Source | Notes |
|---|---|---|
| `auroraz_sdk.permissions` | `backend/sdk/permissions.py` | `PermissionChecker`, `PERMISSION_HIERARCHY` |
| `auroraz_sdk.ipc` | `backend/sdk/ipc.py` | `IPCClient` — used by `Plugin._startup()` |
| `auroraz_sdk.permission_vocab` | `backend/auroraz/plugin/permission_vocab.py` | Stage 3 canonical + alias map + `normalize_permissions` |
| `auroraz_sdk.types` | `backend/auroraz/plugin/types.py` | `PluginManifest`, `PluginServices`, `ContextHook` dataclasses |
| `auroraz_sdk.manifest` | `backend/auroraz/plugin/manifest.py` | YAML→`PluginManifest` parser |
| `auroraz_sdk.exceptions` | `backend/auroraz/plugin/exceptions.py` | Plugin-side error types (distinct from sdk/exceptions.py) |
| `auroraz_sdk.lint` | `backend/auroraz/plugin/lint/` | Stage 4 linter — runs locally for authors |
| `auroraz_sdk.scaffold` | `backend/auroraz/plugin/scaffold/` | Stage 4 scaffolder — runs locally for `auroraz-sdk init` |
| `auroraz_sdk.cli` | `backend/sdk/cli/` | Author-facing CLI (`init`, `lint`, `pack`, `validate`) |

## INTERNAL (NOT shipped — stays in AURORAZ desktop)

| Module | Source | Why |
|---|---|---|
| `ipc_server` | `backend/sdk/ipc_server.py` | AURORAZ-side IPC server. Plugins don't host an IPC server. |
| `plugin_manager` | `backend/sdk/plugin_manager.py` | AURORAZ-side spawn/lifecycle/event publish. |
| `plugin_event_bus` | `backend/sdk/plugin_event_bus.py` | AURORAZ-side activity bus. |
| `launcher` | `backend/sdk/launcher.py` | AURORAZ-side subprocess launcher. |
| `resource_monitor` | `backend/sdk/resource_monitor.py` | AURORAZ-side resource accounting. |
| `static_analyzer` | `backend/sdk/static_analyzer.py` | AURORAZ-side install-time security scan. |
| `dependency_verifier` | `backend/sdk/dependency_verifier.py` | AURORAZ-side install-time dep hash check. |
| `auroraz.plugin.base` | (kept locally) | Re-shipped as `auroraz_sdk.base` for in-process authors. |
| `auroraz.plugin.loader` | `backend/auroraz/plugin/loader.py` | AURORAZ-side load orchestration. |
| `auroraz.plugin.registry` | `backend/auroraz/plugin/registry.py` | AURORAZ-side state. |
| `auroraz.plugin.sandbox` | `backend/auroraz/plugin/sandbox.py` | AURORAZ-side memory sandbox + secrets decrypt. |
| `auroraz.plugin.event_bus` | `backend/auroraz/plugin/event_bus.py` | AURORAZ-side in-process event bus. |
| `auroraz.plugin.context_hooks` | `backend/auroraz/plugin/context_hooks.py` | AURORAZ-side context-hook registry. |
| `auroraz.plugin.azpkg` | `backend/auroraz/plugin/azpkg/` | AURORAZ-side install-time signature verify. (Stage 6a.2 may ship a `pack` CLI that uses it.) |
| `auroraz.security.*` | `backend/auroraz/security/` | AURORAZ-side keychain, encryption, version compat. |

## Cross-imports requiring rewrite or stub

| Source | Old import | Treatment |
|---|---|---|
| `auroraz_sdk.manifest` | `from auroraz.plugin.exceptions` | Rewrite → `from auroraz_sdk.exceptions` |
| `auroraz_sdk.manifest` | `from auroraz.plugin.permission_vocab` | Rewrite → `from auroraz_sdk.permission_vocab` |
| `auroraz_sdk.manifest` | `from auroraz.plugin.types` | Rewrite → `from auroraz_sdk.types` |
| `auroraz_sdk.lint.lint` | `from auroraz.plugin.manifest` | Rewrite → `from auroraz_sdk.manifest` |
| `auroraz_sdk.lint.lint` | `from auroraz.plugin.lint.{diagnostics,rules}` | Rewrite → `from auroraz_sdk.lint.{...}` |
| `auroraz_sdk.lint.rules` | `from auroraz.plugin.permission_vocab` | Rewrite → `from auroraz_sdk.permission_vocab` |
| `auroraz_sdk.lint.rules` | `from auroraz.plugin.lint.diagnostics` | Rewrite → `from auroraz_sdk.lint.diagnostics` |
| `auroraz_sdk.lint.__init__` | `from auroraz.plugin.lint.{diagnostics,lint}` | Rewrite → `from auroraz_sdk.lint.{...}` |
| `auroraz_sdk.scaffold.scaffold` | `from auroraz.plugin.permission_vocab` | Rewrite → `from auroraz_sdk.permission_vocab` |
| `auroraz_sdk.scaffold.scaffold` | `from config import settings as _settings` (default plugins_dir) | **STUB** — `from auroraz_sdk._stub_config import settings` |
| `auroraz_sdk.scaffold.__init__` | `from auroraz.plugin.scaffold.scaffold` | Rewrite → `from auroraz_sdk.scaffold.scaffold` |
| `auroraz_sdk.base` | `from auroraz.plugin.types` (TYPE_CHECKING only) | Rewrite → `from auroraz_sdk.types` |
| `auroraz_sdk.base` | `from auroraz.plugin.exceptions` (if any) | Rewrite |
| `auroraz_sdk.scaffold.templates.in_process.__init__.py.tmpl` | `from auroraz.plugin.{base,types}` | **Templates stay as-is** — they generate code that runs INSIDE AURORAZ desktop, not in the SDK package. The SDK ships templates literally. |

## Stub modules created in dist

| Stub | Purpose |
|---|---|
| `auroraz_sdk._stub_config` | `settings` namespace (PLUGINS_DIR, DATA_PATH) backed by env vars; default cwd-relative |
| `auroraz_sdk._stub_keystore` | Raises `NotImplementedError` if any public module incidentally tries to read the master key. The SDK doesn't decrypt — AURORAZ desktop does, on load. |

## Public API surface size

13 PUBLIC top-level names + 9 PUBLIC-helper modules (all under `auroraz_sdk.*`).
Within budget — well under the 20-name red flag.

## Notes / risks

- **`base.AURORAZPlugin` ships in the SDK** so in-process plugin authors get the abstract base. Subclassing it inside their `__init__.py` is the same code path AURORAZ desktop will instantiate, so the base must use the same import path the desktop sees. Templates handle the desktop-side path; the SDK exposes the symbol so authors can import-check + IDE-complete locally.
- **`sandbox.PluginSettingsStore` / `NamespacedMemoryAccess` are NOT shipped.** Authors who need to test settings access locally can stub their own; in production, AURORAZ desktop instantiates the real ones. Documented in `docs/architecture.md`.
- **`cli/` ships intact** — the four sub-commands (`init`, `lint`, `pack`, `validate`) form the author CLI. Wired as a `[project.scripts]` entry in `pyproject.toml`.
- **Templates inside `scaffold/templates/`** ship untouched. They use `__TOKEN__` placeholders and reference `auroraz.plugin.base` etc. — the generated code runs inside AURORAZ desktop, where those imports resolve. The SDK package is the *generator*, not the *runner* of the generated code.
