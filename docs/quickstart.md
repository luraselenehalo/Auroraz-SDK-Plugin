# Quickstart — Build your first AURORAZ plugin in 10 minutes

This guide walks through creating, installing, and testing a working
plugin from scratch. Goal: by the end, AURORAZ desktop has a new tool
Luna can call.

## Prerequisites

- Python 3.10+
- AURORAZ desktop running locally (or you can build offline and install
  the plugin once AURORAZ is available)

## 1. Install the SDK

```bash
pip install auroraz-sdk
```

Verify:

```bash
python -c "from auroraz_sdk import Plugin; print('ok')"
```

## 2. Scaffold a new plugin

The SDK ships a CLI for common author tasks:

```bash
auroraz-sdk init my-first-plugin --type subprocess
```

This creates `my-first-plugin/` with:

```
my-first-plugin/
  plugin.yaml          # manifest
  backend/main.py      # entry point
  README.md
  requirements.txt
```

If you'd rather write things by hand, copy from
[examples/hello-world](../examples/hello-world).

## 3. Edit the manifest

Open `plugin.yaml`. The fields you'll edit:

```yaml
id: my-first-plugin
name: "My First Plugin"
version: "0.1.0"
description: "A plugin that does X"
permissions:
  - memory:read           # only what your plugin needs
sdk_entry: backend/main.py
```

Permission names must match the canonical AURORAZ vocabulary — see
[permissions.md](permissions.md). Authoring the wrong permission name
gets caught by `auroraz-sdk lint`.

## 4. Write a tool

Open `backend/main.py`:

```python
from auroraz_sdk import Plugin, aurora, hook, tool

plugin = Plugin(
    id="my-first-plugin",
    name="My First Plugin",
    version="0.1.0",
    permissions=["memory:read"],
)


@tool(
    name="my_first_plugin_search",
    description="Look something up in long-term memory",
    when="user asks what they previously told you about a topic",
)
async def search(query: str, k: int = 3) -> str:
    hits = await aurora.memory.search(query, k=k)
    if not hits:
        return f"No memories matched {query!r}."
    return "\n".join(f"- {h['text']}" for h in hits)


if __name__ == "__main__":
    plugin.run()
```

Tool name conventions:
- prefix with the plugin id (snake-cased) so the agent's catalog
  doesn't collide
- `description` and `when` are read by the agent's planner

## 5. Lint locally

```bash
auroraz-sdk lint .
```

Fix anything the linter complains about. Common issues:
- Permission name typos (`memory.read` → `memory:read`)
- Tool not prefixed with plugin id
- `aurora.memory.search` called without declaring `memory:read`

## 6. Install into AURORAZ

For development, the easiest path is to drop the folder into AURORAZ's
plugins dir:

```bash
# AURORAZ desktop's plugin source-of-truth lives here
cp -r my-first-plugin/ <path-to-AURORAZ>/backend/plugins/
```

Then in AURORAZ:
- Open the Marketplace tab
- Find "My First Plugin"
- Click **Install** and then **Enable**

In a future release the marketplace will support remote install of
signed `.azpkg` files; for now, manual copy is the standard.

## 7. Try it

In AURORAZ chat, ask Luna something that triggers your tool:

> "What did I tell you about pizza last week?"

Luna's planner will pick `my_first_plugin_search` if its `when` clause
matches, call it via IPC, and weave the result into the reply.

## Where to go from here

- See [examples/](../examples/) for memory writes, UI iframes, etc.
- Read [api.md](api.md) for the full surface
- Read [architecture.md](architecture.md) for IPC, in-process vs
  subprocess, and the permission model
- Read [publishing.md](publishing.md) when you're ready to share
