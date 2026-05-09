# Tutorial 2: Memory + custom tools (30 minutes)

Building on [Tutorial 1](01-first-plugin.md), we'll add:

- `remember(text)` — store a fact in AURORAZ's long-term memory
- `recall(query, k)` — semantic-search the memory pool
- Permission declarations (`memory:read`, `memory:write`)
- A second tool, exercising tool descriptions in the manifest

This tutorial mirrors `examples/memory-bot/`. Working code is one
folder away if you get stuck.

## Step 1: Add permissions to the manifest (3 min)

Edit `plugin.yaml`:

```yaml
id: memory-bot
name: "Memory Bot"
version: "0.1.0"
description: "Two tools: remember a fact for later, then recall it via semantic search."
author: "Your Name"
category: "tools"
icon: "🧠"
tags: [example, memory]

permissions:
  - memory:read
  - memory:write

sdk_entry: main.py
```

Why two permissions? AURORAZ enforces them per-API-call:

- `aurora.memory.remember(text)` → requires `memory:write`
- `aurora.memory.search(query)` → requires `memory:read`

`memory:write` implies `memory:read` (write-then-read pattern is
common), so declaring just `memory:write` would technically suffice.
We declare both for clarity — the permission list doubles as
documentation for users.

See [permissions reference](../reference/permissions.md) for the full
canonical map.

## Step 2: Add `memory_bot_remember` tool (5 min)

Replace `main.py`:

```python
"""memory-bot — uses aurora.memory to persist + recall facts."""

from __future__ import annotations

import json
import logging

from auroraz_sdk import Plugin, aurora, hook, tool

logger = logging.getLogger("auroraz.plugin.memory-bot")

plugin = Plugin(
    id="memory-bot",
    name="Memory Bot",
    version="0.1.0",
    permissions=["memory:read", "memory:write"],
)


@tool(
    name="memory_bot_remember",
    description="Store a fact in AURORAZ's long-term memory.",
    when="user asks to remember, save, or note something for later",
)
async def remember(text: str) -> str:
    if not text or not text.strip():
        return "Nothing to remember — pass a non-empty text."
    await aurora.memory.remember(text.strip())
    return f"Got it. I will remember: {text.strip()}"
```

Two things changed:

1. We import `aurora` from `auroraz_sdk`. It's a lazy proxy that
   resolves to the IPC client after `plugin.run()` connects. Calling
   `await aurora.memory.remember(...)` from module-load time would
   fail; calling from inside a tool handler always works.

2. The tool function is `async` — we `await` the IPC roundtrip.

## Step 3: Add `memory_bot_recall` tool (5 min)

Append to `main.py`:

```python
@tool(
    name="memory_bot_recall",
    description="Search AURORAZ's long-term memory and return up to k matches.",
    when="user asks what they told you about a topic, or to recall a memory",
)
async def recall(query: str, k: int = 3) -> str:
    hits = await aurora.memory.search(query, k=max(1, min(k, 10)))
    if not hits:
        return f"No memories matched {query!r}."
    return json.dumps(
        [{"text": h.get("text"), "score": h.get("score")} for h in hits],
        ensure_ascii=False,
    )


@hook("on_startup")
async def on_startup(_ctx) -> None:
    logger.info("[memory-bot] started — memory:read+memory:write granted")


if __name__ == "__main__":
    plugin.run()
```

Note:

- `aurora.memory.search` returns a list of dicts: `{text, score, metadata, timestamp}`.
- We clamp `k` to `[1, 10]` defensively — Luna's planner sometimes
  passes wild values.
- We serialize the result as JSON because tools return strings to the
  agent.

## Step 4: Tool descriptions matter (5 min)

The chat agent picks tools based on:

1. **`description`** — what the tool does
2. **`when`** — when to use it
3. **Parameter names + types** — what the tool needs

If two tools sound similar, Luna picks one (sometimes the wrong one).
Best practices:

- Be specific in `when`: "user wants to **store** something" vs "user wants to **search** stored items"
- Don't paraphrase: if your tool searches, say "search" — not "find" or "lookup"
- Keep `description` to one sentence
- Cover edge cases in the function code, not the description

Bad:

```python
@tool(name="bot_do_thing", description="Does the thing.", when="when you want to.")
```

Good:

```python
@tool(
    name="memory_bot_remember",
    description="Store a fact in AURORAZ's long-term memory.",
    when="user asks to remember, save, or note something for later",
)
```

## Step 5: Test the round-trip (10 min)

Reinstall the plugin (or just restart AURORAZ if you've been editing
in `backend/plugins/memory-bot/`):

```bash
curl -X POST http://localhost:8741/api/plugins/memory-bot/disable
curl -X POST http://localhost:8741/api/plugins/memory-bot/enable
```

In chat:

> **You:** Remember this for me: my favorite tea is matcha.

Luna calls `memory_bot_remember(text="my favorite tea is matcha")`:

> **Luna:** Got it. I will remember: my favorite tea is matcha.

Then later:

> **You:** What did I tell you I like?

Luna calls `memory_bot_recall(query="what user likes")`:

> **Luna:** *(reads JSON, paraphrases)* You mentioned matcha tea is your favorite.

You can verify the stored memory in AURORAZ's Memory tab — your text
appears tagged with `plugin:memory-bot`.

## Concepts

### Permission declaration vs enforcement

Declaring `memory:write` in your manifest doesn't grant the
permission — it tells AURORAZ "this plugin needs the ability to
write." When the plugin actually calls `aurora.memory.remember`,
AURORAZ's IPC server checks the manifest list and either dispatches
or raises `PermissionDeniedError`.

The plugin can't lie about its permissions: AURORAZ controls the IPC
server, the plugin can only ask. See
[reference/permissions.md](../reference/permissions.md).

### Memory namespacing

Every memory you write via `aurora.memory.remember` is automatically
tagged with your plugin id. When you search, AURORAZ scopes results
to your plugin's namespace — you only see memories your plugin wrote.

The exception is the global semantic pool used by AURORAZ itself for
chat: read-only on shared memories with no plugin tag.

### ArcadeDB backing store

Behind the scenes, memories live in AURORAZ's ArcadeDB Embedded
graph + vector store. Embeddings come from the local Ollama model
(`qwen3-embedding:0.6b` by default). Search is HNSW-indexed; cosine
similarity. None of this matters for plugin authoring — you just
call `remember` and `search`.

## Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| `PermissionDeniedError: memory:write` | Forgot to declare in manifest | Add to `permissions:` list |
| `remember` succeeds but `recall` returns nothing | Ollama not running locally | Start Ollama; embeddings need it |
| Tool runs but agent doesn't pick it | Vague `when` / `description` | Rewrite to mention concrete trigger words |
| `aurora not initialized` error | Calling aurora at module load | Move call inside the tool function (post `plugin.run()`) |
| Memory shows up tagged with another plugin | Old data from a previous plugin id | Memory pool is shared but namespaced by tag — your queries should still be filtered |

## What you learned

- Declaring + using permissions
- `aurora.memory.remember` and `aurora.memory.search`
- Tool descriptions and the chat agent's tool-selection logic
- Memory namespacing and the ArcadeDB backing store

## Next steps

→ [Tutorial 3: Plugin with UI](03-plugin-with-ui.md) — add a sandboxed iframe page so users can interact with your plugin visually.
