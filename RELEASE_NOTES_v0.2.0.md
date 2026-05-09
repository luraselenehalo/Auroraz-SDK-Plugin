# auroraz-sdk v0.2.0

## What's new

### Reasoning API 🧠

Plugins can now invoke AURORAZ's Fractal 1:3 cognitive engine — the
same reasoning Luna uses in chat — at four depths:

```python
from auroraz_sdk import aurora, tool

@tool(name="my_research")
async def research(question: str) -> str:
    return await aurora.reasoning.ask(question, level="K3")
```

Available levels:

- **K0** — fast, no LLM (greetings, simple lookups)
- **K1** — general questions (default)
- **K2** — deep analysis
- **K3** — draft + verify + optional refine

Permission required is the level being requested
(`reasoning:k0` … `reasoning:k3`). Higher levels imply lower
(k3 ⊇ k2 ⊇ k1 ⊇ k0), so a single `reasoning:k3` declaration unlocks
the whole range.

### New permissions

- `reasoning:k0`
- `reasoning:k1`
- `reasoning:k2`
- `reasoning:k3`

All four are canonical and recognized by the linter, manifest parser,
and Plugin Page descriptions.

### Default rate limits (per plugin per level)

| Level | Per minute | Per day |
| --- | --- | --- |
| K0 | unlimited | unlimited |
| K1 | 60 | 1,000 |
| K2 | 30 | 500 |
| K3 | 10 | 100 |

Override via env (`AURORAZ_REASONING_RATE_K3_PER_MIN=20`, etc.).

Exceeding a limit raises `RateLimitError`.

### Recursion guard

Plugin reasoning depth is capped at 2. A third nested call raises
`RecursionLimitError`, breaking pathological loops where plugin →
reasoning → plugin → reasoning → … would otherwise spiral.

### Concurrency safety

A global lock keeps at most one plugin reasoning call in flight system-
wide, queued in arrival order. The user-chat code path is **separate**
and is not gated by this lock — the user's chat keeps responding
instantly even while a plugin's K3 query runs.

### Activity feed transparency

Every reasoning call appears in the Plugin Page's activity feed with a
K-level pill (K0 / K1 / K2 / K3), question preview, duration, and
token estimate. Chat-side `ToolUseCard` accepts optional reasoning
metadata so a chat-triggered tool that internally called
`reasoning.ask` shows a "🧠 used K3 reasoning (8.2s)" sub-line.

### New example

- [`research-bot/`](examples/research-bot/) — demonstrates K1 + K3
  reasoning use, including the on_startup notify and per-level
  permission gating

### New tutorial

- [Tutorial 5: Use Luna's brain](docs/tutorials/05-luna-brain.md) —
  30-min walkthrough of the reasoning API, including error handling,
  rate limits, recursion guard, and concurrency notes.

### New exceptions exported

- `RateLimitError`
- `RecursionLimitError`
- `PluginTimeoutError` (was internal in v0.1.0)

## Breaking changes

None. v0.2.0 is fully backward compatible with v0.1.0 — plugins built
against the older release work unchanged.

## Upgrading

```bash
pip install --upgrade auroraz-sdk
```

To use the new reasoning API in an existing plugin, declare the
permission in your manifest:

```yaml
permissions:
  - reasoning:k1   # or :k2, :k3
```

…and call from any tool/hook handler:

```python
answer = await aurora.reasoning.ask("…", level="K1")
```

## Errors you may see

| Error | When |
| --- | --- |
| `PermissionDeniedError` | manifest doesn't declare the requested level |
| `RateLimitError` | per-plugin per-level rate limit exceeded |
| `RecursionLimitError` | reasoning is being re-entered past depth 2 |
| `PluginTimeoutError` | response took longer than `timeout` (default 30s) |
| `ValueError` | bad level, empty question — caller-side guard |

## See also

- [API reference](docs/reference/api.md) — `aurora.reasoning` section
- [Permissions reference](docs/reference/permissions.md) — reasoning entries + hierarchy
- [Tutorial 5](docs/tutorials/05-luna-brain.md)
