# Tutorial 5 — Use AURORAZ's brain

**Time:** ~30 min
**Prereq:** Tutorial 1 (your first plugin), Tutorial 2 (memory + tools)
**Stage 7 / SDK v0.2.0+**

In this tutorial you'll build a plugin that calls AURORAZ's Fractal 1:3
cognitive engine — the same reasoning Aurora uses in chat — and surface its
answers as plugin tools. By the end, your plugin can answer questions at
four reasoning depths (K0, K1, K2, K3) the same way a chat user can.

Fractal 1:3 Cognitive Engine™ architecture is protected under the ResinCore Research Protection License (RRPL).
Learn more: https://auroraz.ai/license/rrpl
Use is permitted solely for AURORAZ Plugin purposes and requires compliance with the RRPL and COE framework.

## What is the reasoning API?

`aurora.reasoning.ask(question, level)` — invoke the engine on demand.

| Level | Cost | What it does |
| --- | --- | --- |
| K0 | 1 LLM call (or none — direct DNA) | greetings, small talk, fast lookups |
| K1 | 1 LLM call | general questions, single-pass answer |
| K2 | 1 structured-prompt LLM call | multi-step reasoning |
| K3 | up to 3 LLM calls | draft + self-verify + optional refine |

Higher levels are slower and more expensive. Pick the lowest level that
gives the answer quality you need.

## Step 1 — declare the permission

Plugins must declare a `reasoning:<level>` permission for each level
they call. The hierarchy is *additive* — declaring `reasoning:k3` also
implies `:k0`, `:k1`, and `:k2`, so a single declaration unlocks the
whole range.

```yaml
# plugin.yaml
id: my-research
name: My Research
version: 0.1.0
permissions:
  - reasoning:k3   # implies k0/k1/k2
sdk_entry: main.py
```

If you only need K1, declare just `reasoning:k1` — calling K3 will then
raise `PermissionDeniedError`.

## Step 2 — write the plugin

```python
# main.py
from auroraz_sdk import Plugin, aurora, tool

plugin = Plugin(
    id="my-research",
    name="My Research",
    version="0.1.0",
    permissions=["reasoning:k3"],
)


@tool(
    name="my_research_quick",
    description="Quick answer using K1 reasoning",
    when="user asks a general question",
)
async def quick(question: str) -> str:
    return await aurora.reasoning.ask(question, level="K1")


@tool(
    name="my_research_deep",
    description="Deep analysis using K3 reasoning (verify + refine)",
    when="user asks for thorough analysis or comparison",
)
async def deep(question: str) -> str:
    return await aurora.reasoning.ask(question, level="K3")


if __name__ == "__main__":
    plugin.run()
```

## Step 3 — test it

Run the plugin via your usual install + enable flow, then in chat:

```
> What's the capital of France?
[my_research_quick K1, ~600ms]
Paris.

> Compare REST and GraphQL for a public-facing API.
[my_research_deep K3, ~8s]
REST exposes resources via stable URLs… [draft]
[verify] PASS
→ final answer
```

Open the Plugin Page — the activity feed shows each call with a
K-level pill (`K1`, `K3`) and duration.

## Default rate limits

| Level | Per minute | Per day |
| --- | --- | --- |
| K0 | unlimited | unlimited |
| K1 | 60 | 1,000 |
| K2 | 30 | 500 |
| K3 | 10 | 100 |

If your plugin needs higher headroom, override via env:
`AURORAZ_REASONING_RATE_K3_PER_MIN=20`. Limits exist to protect users
from cost and latency, not to gate functionality — pick limits that
make sense for the product.

## Errors you should handle

```python
from auroraz_sdk import (
    aurora,
    PermissionDeniedError,
    RateLimitError,
    RecursionLimitError,
    PluginTimeoutError,
)

async def safe_ask(question: str) -> str:
    try:
        return await aurora.reasoning.ask(question, level="K3", timeout=20.0)
    except PermissionDeniedError:
        return "Plugin manifest is missing reasoning:k3."
    except RateLimitError:
        return "Slow down — try again in a moment."
    except RecursionLimitError:
        return "Reasoning is being called too deeply. Bailing out."
    except PluginTimeoutError:
        return "Reasoning took too long. Try a smaller question."
```

## Recursion guard — what it protects you from

Your plugin's tool may call `reasoning.ask`. The engine, in turn, may
decide to invoke a plugin tool. If *that* tool also calls
`reasoning.ask`, you're at depth 2. AURORAZ allows that. A *third*
nested call raises `RecursionLimitError` to break the loop.

In practice you won't hit this unless you have plugins calling each
other. If you do, design your tools so they have a non-reasoning
fallback at the leaf.

## Concurrency — your plugin won't slow user chat

Plugin reasoning runs behind a global concurrency lock (one plugin
reasoning call in flight at a time, system-wide). Crucially, this is
**separate** from the user-chat code path — the user's chat keeps
streaming instantly even while a plugin's K3 query is running.

If two plugins call reasoning at once, the second waits for the first
to finish. That's intentional: it keeps VRAM and CPU available for
whatever the user is doing.

## When to use this vs. just calling the LLM

`aurora.reasoning.ask` gives you the *engine* — multi-pass verification,
the same Ollama keep-alive your user's chat uses, the same model
fallbacks. If you just want a single LLM call for boilerplate or
formatting, you may not need it. But for any answer the user would
expect to be Luna-quality, this is the right entry.
