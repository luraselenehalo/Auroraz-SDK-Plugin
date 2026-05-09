# `plugin.yaml` reference

Every field AURORAZ reads from a plugin's manifest, with type,
required/optional, validation, and example.

## Top-level fields

### Required

| Field | Type | Validation |
|---|---|---|
| `id` | string | `^[a-z][a-z0-9_-]{1,49}$`. Identifier used everywhere |
| `name` | string | Non-empty. Display name |
| `version` | string | Semver `X.Y.Z` (or `X.Y.Z-prerelease+build`) |
| `permissions` | list of strings | Declared explicitly even if `[]`. Canonical form preferred (see [permissions.md](permissions.md)) |

### Strongly recommended

| Field | Type | Default | Notes |
|---|---|---|---|
| `description` | string | "" | One-sentence summary. Marketplace shows it on the card |
| `author` | string | "Anonymous" | Your name/handle |
| `category` | string | "tools" | One of: `ai`, `creative`, `gaming`, `productivity`, `tools`, `developer` |
| `icon` | string | "🧩" | Emoji (≤4 chars) or path to an image |
| `tags` | list of strings | `[]` | Free-form search keywords |

### Compatibility

| Field | Type | Default | Notes |
|---|---|---|---|
| `min_auroraz_version` | string | "" | Semver. AURORAZ refuses to enable a plugin whose minimum exceeds the running version |

### Subprocess entry point

| Field | Type | Notes |
|---|---|---|
| `sdk_entry` | string | Relative path from plugin root to the entry script. Example: `main.py` or `backend/main.py` |

The SDK detector looks for `sdk_entry` first; if absent, falls back
to `backend/main.py` then `main.py`. Declaring `sdk_entry`
explicitly is the recommended Stage 6a pattern.

### In-process entry point (advanced)

For first-party plugins shipping inside AURORAZ itself:

```yaml
entry_points:
  backend: "__init__:MyPlugin"   # module:ClassName subclassing AURORAZPlugin
  router:
    module: router
    prefix: /api/plugins/<id>
  tools:
    module: tools
    functions:
      - my_tool_a
      - my_tool_b
  context_hooks:
    - module: context_hook
      function: inject_context
      priority: 100
      k_levels: [0, 1, 2, 3]
  working_memory_hooks:
    - on_message_add: "context_hook:enrich_metadata"
```

Most third-party authors won't need any of this — subprocess via
`sdk_entry` is the straightforward path.

## `frontend:` block (optional)

Declares a sandboxed iframe UI for the plugin:

```yaml
frontend:
  ui_entry: ui/index.html
  icon: "🎨"
  display_name: "ResinAI"
  status_strip:
    - { label: "VRAM",  source: "vram_used" }
    - { label: "Model", source: "model_name" }
```

| Field | Type | Notes |
|---|---|---|
| `ui_entry` | string | Required. Relative path to entry HTML. Path-traversal blocked at parse |
| `icon` | string | Optional override of the top-level `icon` |
| `display_name` | string | Optional override of the top-level `name` for the sidebar |
| `status_strip` | list of `{label, source}` | Strip rendered above the iframe; values come from settings |

When this block is present, `has_ui: true` is exposed via the API
and the plugin gets a sidebar icon.

## `settings:` block (optional)

Schema for user-configurable plugin settings. Renders as a form in
the Plugin Page:

```yaml
settings:
  default_style:
    type: select
    label: "Default Style"
    description: "Style Luna uses when not specified"
    options: ["Photorealistic", "Anime", "Oil Painting"]
    default: "Photorealistic"

  allow_luna_generate:
    type: boolean
    label: "Allow Luna to generate"
    default: true

  api_token:
    type: password
    label: "API token"
    description: "Stored encrypted at rest."
    secret: true                  # explicit; type:password is enough

  api_endpoint:
    type: text
    label: "API endpoint"
    placeholder: "http://localhost:7860"

  inference_steps:
    type: integer
    label: "Steps"
    default: 28
    min: 1
    max: 60

  cfg_scale:
    type: number
    label: "CFG scale"
    default: 7.0
    min: 1.0
    max: 30.0
```

Field types:

| `type` | Renders as | Stored as |
|---|---|---|
| `text` | text input | string |
| `password` | password input | encrypted string |
| `boolean` | toggle | bool |
| `select` | dropdown (use `options`) | string (must be one of options) |
| `number` | number input | float |
| `integer` | number input (step=1) | int |

Per-field options:

| Option | Applies to | Notes |
|---|---|---|
| `label` | all | Form label |
| `description` | all | Helper text |
| `default` | all | Initial value |
| `secret: true` | text | Forces encryption + redaction even without `type: password` |
| `placeholder` | text/password | HTML placeholder |
| `options: [...]` | select | Required for select |
| `min` / `max` | number/integer | Inclusive bounds |

Settings persist at `<DATA_PATH>/plugins/<id>/config.json`. Encrypted
values use the `azenc:v1:` prefix and the AURORAZ master key.

## `data:` block (optional, in-process)

```yaml
data:
  namespace: my_plugin
  persist_path: state.json
```

Used by in-process plugins for sandboxed file storage. Subprocess
plugins use `Plugin.config` and `aurora.memory.*` instead.

## Other top-level fields

| Field | Type | Notes |
|---|---|---|
| `dependencies` | list of plugin ids | Other plugins that must be loaded first |
| `built_in` | bool | Default `false`. Set to `true` for plugins shipped with AURORAZ |
| `verified` | bool | Default `false`. Marketplace badge |
| `core` | bool | Default `false`. Core plugins can't be uninstalled |
| `price` | int | Default `0`. Price in cents (informational) |
| `screenshots` | list of strings | URLs or relative paths shown on the marketplace card |
| `changelog` | string | Free-form changelog text |

## Full example

A complete subprocess plugin manifest with everything:

```yaml
id: my-plugin
name: "My Plugin"
version: "1.0.0"
description: "Does X for Y; useful when Z."
author: "Your Name"
category: "tools"
icon: "🧩"
tags: [productivity, automation]

min_auroraz_version: "0.1.0"

permissions:
  - memory:read
  - memory:write
  - network:api.example.com
  - notifications:show

sdk_entry: main.py

frontend:
  ui_entry: ui/index.html
  icon: "🧩"
  display_name: "MyPlugin"

settings:
  api_token:
    type: password
    label: "API token"
  default_count:
    type: integer
    default: 5
    min: 1
    max: 100

dependencies: []
```

## Validation

The manifest parser raises `PluginManifestError` for:

- Missing required fields
- Invalid `id` format
- Non-string fields where strings are required
- `frontend.ui_entry` with absolute path or `..` components
- `frontend` block that isn't a mapping
- Unknown `permissions:` entries (warning, not error — see permissions.md)

## Linting

Run `auroraz-sdk lint .` (or via API:
`GET /api/plugins/<id>/lint`) to catch:

- Required fields missing
- ID format invalid
- Non-semver version
- Permissions deprecated alias
- Permissions declared but unused
- Permissions used but not declared
- Tool names colliding with built-ins
- Tool names not prefixed with plugin id

See the [linter rules in api.md](api.md) for the full list.
