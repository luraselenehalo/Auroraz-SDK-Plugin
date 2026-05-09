# Migration: prototype plugins → published SDK

If you have an existing AURORAZ plugin (built before `auroraz-sdk`
was published), here's how to bring it forward.

## Prototype → SDK conventions

| | Prototype era | Published SDK era |
|---|---|---|
| Import | `from sdk import …` (in-tree) | `from auroraz_sdk import …` |
| Permission vocabulary | mixed (underscore, dot, colon) | canonical colon (`memory:read`) |
| Manifest entry | `entry_points.backend: "main:Plugin"` (in-process) | `sdk_entry: main.py` (subprocess) |
| Entry file location | `backend/main.py` | Either `main.py` (root) or `backend/main.py` |
| Distribution | Drop folder into AURORAZ source | Same for now; `.azpkg` in Stage 6b |
| Settings access | varied | `Plugin.config[key]` (subprocess) |

## Step 1: Migrate imports

Find:

```python
from sdk import Plugin, aurora, hook, tool
```

Replace with:

```python
from auroraz_sdk import Plugin, aurora, hook, tool
```

If the plugin lives outside AURORAZ's source tree, install
`auroraz-sdk` in the env where the plugin runs:

```bash
pip install auroraz-sdk
```

For development against your local source:

```bash
pip install -e /path/to/dist/auroraz-sdk
```

## Step 2: Canonicalize permissions

Run the migration script (in AURORAZ's source tree):

```bash
cd /path/to/AURORAZ
backend/.venv312/Scripts/python.exe backend/scripts/migrate_plugin_perms.py <plugin-id> --apply
```

This rewrites `permissions:` in `plugin.yaml`:

```yaml
# Before
permissions:
  - memory_read
  - memory_write
  - prompt:inject
  - notifications
  - chat.inject

# After
permissions:
  - memory:read
  - memory:write
  - context:inject
  - notifications:show
  # (chat.inject mapped to context:inject — duplicates removed)
```

A `.bak` backup of the original manifest is saved next to it.

If you don't want to run the script, edit by hand using the alias
table in [permissions.md](permissions.md).

The deprecated aliases STILL WORK — they just produce a warning at
load. So this migration step is recommended but not strictly
required.

## Step 3: Update the manifest entry style

If your plugin runs as a subprocess (most third-party plugins),
prefer:

```yaml
sdk_entry: main.py        # OR backend/main.py
```

over the in-process style:

```yaml
entry_points:
  backend: "__init__:MyPlugin"
```

The `sdk_entry` field is the Stage 6a recommended style for
subprocess plugins. It's more explicit than the convention-driven
`backend/main.py` lookup.

If your plugin is in-process (subclasses `AURORAZPlugin`), keep the
`entry_points.backend` style.

## Step 4: Add `min_auroraz_version`

```yaml
min_auroraz_version: "0.1.0"
```

Set this to the lowest AURORAZ version you've tested against. Stage 5
enforces it — incompatible plugins skip-load with a clear message.

## Step 5: Lint

```bash
auroraz-sdk lint .
```

Common findings on prototype plugins:

| Code | What it means | Fix |
|---|---|---|
| `MAN004` | Plugin id format invalid | Rename to lowercase kebab/snake |
| `MAN005` | Version not semver | Use `X.Y.Z` |
| `PERM001` | Unknown permission | Check spelling |
| `PERM002` | Deprecated alias | Run migration script (Step 2) |
| `PERM003` | Declared but unused | Remove from manifest |
| `API001` | Used but undeclared | Add to manifest |
| `TOOL001` | Tool name collides with built-in | Rename with plugin id prefix |
| `TOOL002` | Tool name not prefixed | Rename to `<plugin_id_snake>_<old_name>` |

Get to 0 errors before publishing.

## Step 6: Test against current AURORAZ

Drop the migrated folder into `backend/plugins/<id>/`, install + enable.
Test:

- All tools register (check via `/api/plugins/<id>` response)
- Tool dispatch works (use the tool from chat or via API)
- Hooks fire on startup/shutdown (check `<DATA_PATH>/logs/plugin-<id>.log`)
- UI loads if `frontend.ui_entry` is declared
- Permissions enforce correctly (try a tool that calls `aurora.memory.*`
  with the permission missing — should raise `PermissionDeniedError`)

## Step 7 (optional): Settings encryption

If your plugin has secret-bearing settings (API tokens, OAuth refresh
tokens, etc.), mark them `type: password` or `secret: true`:

```yaml
settings:
  api_token:
    type: password           # encrypted at rest, redacted in API
    label: "API token"
```

When AURORAZ stores the value, it encrypts with the master key. Your
subprocess plugin reads decrypted plaintext via `plugin.config["api_token"]`.

Existing plain-text settings continue to work — the decrypt layer
passes them through. So this is a soft migration; you can flip
`secret: true` when you're ready.

## Common pitfalls

- **Don't change tool names without bumping major version.** Changing
  `my_tool` to `my_plugin_my_tool` is a breaking change for any
  prompt that referenced the old name. Bump version `1.x.x → 2.0.0`.
- **`anthropic_sdk` permission renamed**. The new canonical is
  `anthropic:proxy`. Old code that imports the SDK token via the
  alias will get a deprecation warning but still work.
- **`prompt:inject` is now `context:inject`**. Plugins calling
  `aurora.inject` should declare `context:inject`. The aliased
  `prompt:inject` still works server-side.

## Verify migration with the linter

After all changes, lint should pass cleanly:

```bash
auroraz-sdk lint .
# 0 errors, 0 warnings (some info-level diagnostics are fine)
```

## Going forward

Once migrated, you can:

- Pack the plugin as `.azpkg` (Stage 5+ — `auroraz-sdk pack`, coming in
  Stage 6a.2 followup)
- Publish to the marketplace remote (Stage 6b)
- Distribute the `.azpkg` directly to users for now (manual install
  via `POST /api/plugins/install-azpkg`)

See [reference/publishing.md](publishing.md) for the publishing path.
