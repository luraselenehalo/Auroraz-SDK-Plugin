# Tutorial 1: Build your first plugin (45 minutes)

You'll build **GreetingBot** — a plugin that registers a `greet` tool. By the end:

- AURORAZ knows your plugin exists
- Luna can call `greet` from chat
- You understand the full plugin lifecycle

This walkthrough mirrors `examples/hello-world/` exactly. If you get
stuck, the working code is right there.

## Prerequisites

- Python 3.10+
- AURORAZ desktop installed locally (or just `pip install auroraz-sdk`
  if you only want to lint and run the plugin standalone)
- Any code editor

## Step 1: Set up the plugin folder (5 min)

A subprocess plugin is just a folder with two files:

```
greeting-bot/
  plugin.yaml      # the manifest
  main.py          # the entry point
```

Make the folder anywhere you like:

```bash
mkdir greeting-bot
cd greeting-bot
```

That's the entire scaffold. AURORAZ doesn't care where the folder
lives until you copy it into `backend/plugins/<id>/`. For development,
keep it wherever your other code lives.

## Step 2: Write `plugin.yaml` (5 min)

Create `plugin.yaml`:

```yaml
id: greeting-bot
name: "Greeting Bot"
version: "0.1.0"
description: "A plugin that greets people."
author: "Your Name"
category: "tools"
icon: "👋"
tags: [example, beginner]

# This plugin needs no permissions — its tool has no side effects.
permissions: []

# Entry point. Relative path from this folder. AURORAZ will spawn
# `python main.py` and connect to it via IPC.
sdk_entry: main.py
```

Field-by-field:

| Field | Required | Notes |
|---|---|---|
| `id` | yes | kebab-case, `^[a-z][a-z0-9_-]{1,49}$`. Identifier AURORAZ uses everywhere |
| `name` | yes | Human-readable display name |
| `version` | yes | Semver `X.Y.Z` |
| `description` | no | One-sentence summary; shows in marketplace |
| `author` | no | Your name, GitHub handle, anything |
| `category` | no | One of `ai`, `creative`, `gaming`, `productivity`, `tools`, `developer` |
| `icon` | no | Emoji or short string. Shows in marketplace + sidebar |
| `tags` | no | List of strings for search |
| `permissions` | yes | List of canonical permission strings (see [permissions reference](../reference/permissions.md)). Declare `[]` even if empty |
| `sdk_entry` | yes (subprocess) | Path to entry point relative to plugin root |

## Step 3: Write `main.py` (10 min)

Create `main.py`:

```python
"""GreetingBot — auroraz-sdk tutorial plugin."""

from __future__ import annotations

import logging

from auroraz_sdk import Plugin, hook, tool

logger = logging.getLogger("auroraz.plugin.greeting-bot")

plugin = Plugin(
    id="greeting-bot",
    name="Greeting Bot",
    version="0.1.0",
    permissions=[],
)


@tool(
    name="greeting_bot_greet",
    description="Greet someone by name.",
    when="user asks for a greeting or to say hi",
)
async def greet(name: str = "world") -> str:
    return f"Hello, {name}!"


@hook("on_startup")
async def on_startup(_ctx) -> None:
    logger.info("[greeting-bot] started")


if __name__ == "__main__":
    plugin.run()
```

Three things you just wrote:

### 3.1: The `Plugin` instance

```python
plugin = Plugin(
    id="greeting-bot",
    name="Greeting Bot",
    version="0.1.0",
    permissions=[],
)
```

This is the runtime handle. Construct it once at module scope. The
constructor parameters MUST match the manifest. AURORAZ cross-checks
them at registration time.

### 3.2: The `@tool` decorator

```python
@tool(
    name="greeting_bot_greet",
    description="Greet someone by name.",
    when="user asks for a greeting or to say hi",
)
async def greet(name: str = "world") -> str:
    return f"Hello, {name}!"
```

`@tool` registers the function as something Luna can call:

- `name` — what Luna sees in its tool catalog. Convention: prefix with
  your plugin id (snake_cased) to avoid collisions. The linter (`MAN/TOOL` rules)
  flags un-prefixed names at info severity.
- `description` — one-line summary. Luna's planner uses this when
  deciding which tool to call.
- `when` — natural-language hint. "When should this tool be used?"
  Critical for tool selection.

The function is an `async def`. It can `await` anything, but for a
basic tool, just return a string.

### 3.3: The `@hook` decorator

```python
@hook("on_startup")
async def on_startup(_ctx) -> None:
    logger.info("[greeting-bot] started")
```

Lifecycle hooks run at well-defined moments:

- `on_startup` — after the plugin connects to AURORAZ
- `on_shutdown` — before the plugin terminates

For a basic plugin you usually don't need these. They're useful for
init work (open a database, spawn a background task) and cleanup.

### 3.4: The bottom of the file

```python
if __name__ == "__main__":
    plugin.run()
```

`plugin.run()` enters the IPC event loop. It waits for AURORAZ to send
tool calls, dispatches them, sends results back, and handles
shutdown signals.

You can run this file standalone (`python main.py`) — it'll start, look
for `AURORAZ_IPC_ADDR` in the environment, find none, and just hang
waiting. That's expected. To actually do anything, AURORAZ has to
spawn the process with `AURORAZ_IPC_ADDR` set.

## Step 4: Connect to AURORAZ (15 min)

For development, the simplest path is to drop the folder into AURORAZ's
plugins directory.

### 4.1: Install `auroraz-sdk` into AURORAZ's venv

The plugin imports `auroraz_sdk`. AURORAZ will spawn the plugin using
its own Python — so that Python needs the package installed:

```bash
# From the AURORAZ repo root
backend/.venv312/Scripts/pip install auroraz-sdk
```

(In production, this happens automatically when the user installs your
plugin from the marketplace — AURORAZ handles dependencies.)

### 4.2: Copy the folder

```bash
cp -r greeting-bot/ <path-to-AURORAZ>/backend/plugins/greeting-bot/
```

The folder name should match the manifest's `id`.

### 4.3: Boot AURORAZ

Run AURORAZ in dev mode. The boot logs should show:

```
[Registry] Discovered 7 plugins
[Registry] Loaded state for 6 plugin(s); enabled=['discord', 'gametraverse']
[PluginLoader] Skipping 'greeting-bot': not in enabled_ids (enabled=false in plugins.json)
```

The plugin is discovered but not yet enabled. That's expected — you
have to opt in via the API or the UI.

### 4.4: Install + enable via API

```bash
curl -X POST http://localhost:8741/api/plugins/greeting-bot/install
curl -X POST http://localhost:8741/api/plugins/greeting-bot/enable
```

Or, in the dashboard:

1. Open the **Plugins** tab (🧩 in the sidebar)
2. Find "Greeting Bot" in the marketplace grid
3. Click **Install**
4. Click **Enable**

After enable, AURORAZ spawns the subprocess. Boot logs say:

```
[SDKPluginManager] start_plugin('greeting-bot') ok
[IPCServer] Registered plugin 'greeting-bot' v0.1.0 (tools=1, hooks=0)
```

Your tool is live in Luna's catalog.

## Step 5: Test from chat (10 min)

Open the chat tab in AURORAZ. Ask Luna something that should trigger
your tool:

> **You:** Hi, can you say hello to "Mrgunshi"?

Luna's planner sees `greeting_bot_greet` in its catalog, sees the
`when` hint says "user asks for a greeting", and dispatches:

> **Luna:** *(calls `greeting_bot_greet(name="Mrgunshi")`)*  
> Hello, Mrgunshi!

Behind the scenes:

1. Chat agent decides to call `greeting_bot_greet`
2. AURORAZ's `agent_service.execute_tool` sends a `tool.call` IPC message to your plugin
3. `plugin.run()`'s loop receives the message, calls `greet("Mrgunshi")`
4. The result is sent back over IPC
5. The chat agent stitches it into the reply

You can also call the tool directly via the API for testing:

```bash
curl -X POST http://localhost:8741/api/plugins/greeting-bot/tools/greeting_bot_greet \
  -H "Content-Type: application/json" \
  -d '{"name": "Mrgunshi"}'
```

## What you learned

- **Plugin folder structure** (manifest + entry point)
- **Manifest fields** (id, version, permissions, sdk_entry)
- **`@tool` decorator** (name, description, when)
- **`@hook` decorator** (lifecycle events)
- **How AURORAZ launches subprocess plugins** (spawn + IPC handshake)
- **Connecting your plugin to AURORAZ** (folder copy + install/enable)

## Troubleshooting

| Problem | Likely cause | Fix |
|---|---|---|
| "Plugin not discovered" | Folder name doesn't match `id` field | Rename folder to match `plugin.yaml`'s `id` |
| `auroraz-sdk` not found at boot | Not installed in AURORAZ's venv | `backend/.venv312/Scripts/pip install auroraz-sdk` |
| Plugin starts but no tools registered | `@tool` decorator import error | Make sure `from auroraz_sdk import Plugin, tool` is at the top |
| "Permission denied for memory:read" | Tool calls `aurora.memory.*` but `permissions: []` | Declare needed permissions; see [Tutorial 2](02-memory-and-tools.md) |
| Tool runs but Luna ignores it | `description` or `when` too vague | Be explicit: "user asks ABC", "use when XYZ"; planner uses these |

## Next steps

→ [Tutorial 2: Add memory + more tools](02-memory-and-tools.md) — make the plugin remember things across conversations.
