# API Reference

The auroraz-sdk public surface. Anything not listed here is internal —
do not import.

## `Plugin`

```python
Plugin(
    id: str,
    name: str,
    version: str = "1.0.0",
    permissions: list[str] | None = None,
)
```

Subprocess plugin entry. Construct one in module scope, register tools
via `@tool` / `register_tool`, then call `plugin.run()` to enter the
event loop.

### Parameters

- **id** — kebab-case identifier matching `^[a-z][a-z0-9_-]{1,49}$`.
  Used as the plugin's namespace for memory tagging, file paths, IPC
  routing, and tool name prefixes.
- **name** — human-readable display name shown in the marketplace.
- **version** — semver `X.Y.Z`. Bumped per release.
- **permissions** — list of canonical permission strings (see
  [permissions.md](permissions.md)). Underscore/dot aliases are
  accepted with a deprecation warning.

### Methods

- **`run()`** — block on the IPC loop until the parent terminates.
- **`register_tool(name, description, handler, parameters=None, when=None)`** —
  runtime tool registration. Use this when the tool catalog is dynamic
  (e.g. a bridge to another framework's registry). Idempotent on `name`.

## `@tool`

```python
@tool(name: str, description: str, when: str | None = None,
      parameters: dict | None = None)
def handler(...): ...
```

Static tool registration. Decorated functions are appended to the
plugin's tool catalog at import time, snapshot-sent to AURORAZ during
`plugin.register`.

- **name** — the tool identifier the agent will call. Convention:
  prefix with the plugin id (lint rule TOOL002).
- **description** — one-line summary the agent sees in its catalog.
- **when** — natural-language hint the agent's planner uses to decide
  *when* to call this tool.
- **parameters** — JSON Schema describing the function's parameters.
  Auto-derived from type hints if omitted.

## `@hook`

```python
@hook(event: str)
async def handler(ctx): ...
```

Lifecycle / event hooks. Supported events:

- **`on_startup`** — plugin connected to AURORAZ; called once.
- **`on_shutdown`** — plugin about to terminate.
- **`on_message`** — every chat message (rate-limited; check `ctx`).

## `aurora.*` — runtime client

After `plugin.run()` connects, the `aurora` proxy resolves to a live
client. Each method requires a corresponding permission.

### `aurora.memory`

| Method | Permission | Returns |
|---|---|---|
| `await aurora.memory.remember(text, metadata=None)` | `memory:write` | `dict` confirmation |
| `await aurora.memory.search(query, k=5)` | `memory:read` | `list[dict]` of `{text, score, metadata, timestamp}` |
| `await aurora.memory.store(key, value)` | `memory:write` | `None` |
| `await aurora.memory.get(key)` | `memory:read` | the stored value or `None` |

`remember` is the high-level "write a memory to the shared semantic
pool" call — what plugins should reach for in 90% of cases. `store`/
`get` are key-value persistence scoped to the plugin.

### `aurora.context`

| Method | Permission | Returns |
|---|---|---|
| `await aurora.context.get_emotion()` | `context:read` | `str` |
| `await aurora.context.get_intent()` | `context:read` | `str` |
| `await aurora.context.get_window()` | `context:read` | `dict` (active OS window info) |

### Other

| Method | Permission |
|---|---|
| `await aurora.say(text)` | (always allowed) — Aurora speaks the text in chat |
| `await aurora.inject(context)` | `context:inject` — adds a line to the next system prompt |
| `await aurora.notify(message, via="app")` | `notifications:show` — show an in-app toast |
| `await aurora.get_last_message()` | `context:read` |

### `aurora.reasoning` (v0.2.0+)

Invoke AURORAZ's Fractal 1:3 cognitive engine. Permission required is
the level being requested (`reasoning:k0` … `reasoning:k3`); higher
levels imply lower (k3 ⊇ k2 ⊇ k1 ⊇ k0).

| Method | Permission | Returns |
|---|---|---|
| `await aurora.reasoning.ask(question, level="K1", *, timeout=30.0)` | `reasoning:<level>` | `str` (the answer) |
| `await aurora.reasoning.ask_simple(question)` | `reasoning:k1` | `str` (alias for `ask(level="K1")`) |
| `await aurora.reasoning.ask_deep(question)` | `reasoning:k3` | `str` (alias for `ask(level="K3")`) |

Levels:

- **K0** — direct character response, fast (no LLM in many paths). Use for greetings or trivial lookups.
- **K1** — single-pass LLM inference. The default — use for most questions.
- **K2** — structured multi-step prompt; deeper analysis.
- **K3** — draft + self-verify + optional refine; up to 3 LLM calls. Use for complex questions where accuracy matters.

Default rate limits (per plugin per level):

| Level | Per minute | Per day |
| --- | --- | --- |
| K0 | unlimited | unlimited |
| K1 | 60 | 1,000 |
| K2 | 30 | 500 |
| K3 | 10 | 100 |

Override via env: `AURORAZ_REASONING_RATE_K3_PER_MIN=20`, etc.

Concurrency: at most one plugin reasoning call is in flight at a time
(global lock). User chat is on a separate code path and is **not**
gated by this lock — your plugin's K3 call won't slow down chat.

Recursion: max depth 2. A third nested call raises
`RecursionLimitError`.

## Manifest schema

Authored in `plugin.yaml`. See [examples/](../examples/) for working
manifests. Required keys:

- `id`, `name`, `version`
- `permissions: []` (declared even when empty)
- `sdk_entry: backend/main.py` (subprocess) OR
  `entry_points.backend: "__init__:MyPlugin"` (in-process)

Optional:

- `description`, `author`, `category`, `icon`, `tags`
- `min_auroraz_version: "0.1.0"` — refuse to load on older AURORAZ
- `frontend.ui_entry: ui/index.html` — sandboxed iframe UI
- `settings:` — schema for user-configurable plugin settings (renders
  a form in the Plugin Page)

## Errors

- **`PluginError`** — base class
- **`PermissionDeniedError`** — code called an aurora API without the
  required permission declared in the manifest
- **`IPCError`** — IPC layer failure (rare; usually transient)
- **`PluginTimeoutError`** — IPC call exceeded the requested timeout
- **`RateLimitError`** *(v0.2.0+)* — per-plugin per-level reasoning
  rate limit exceeded
- **`RecursionLimitError`** *(v0.2.0+)* — plugin reasoning is being
  re-entered past depth 2

All raised across the IPC boundary; catch in your handler if you want
to recover, otherwise the calling tool returns an error string to the
agent and the agent surfaces it in chat.
