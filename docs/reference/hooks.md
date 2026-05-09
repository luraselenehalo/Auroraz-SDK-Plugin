# Hooks reference

Lifecycle event handlers your plugin can register with `@hook`.

## Decorator syntax

```python
from auroraz_sdk import hook

@hook("on_startup")
async def startup_handler(ctx):
    ...
```

The argument to `@hook` is the event name. The decorated function is
async and receives a single `ctx` parameter (currently a thin
namespace; richer context types coming in future stages).

## Supported events

| Event | When | Use cases |
|---|---|---|
| `on_startup` | Plugin connected to AURORAZ; registration complete | Init external services, spawn background tasks, load state |
| `on_shutdown` | Plugin received termination signal; AURORAZ is about to disconnect | Cleanup background tasks, persist state, close sockets |

Future events (planned, not yet wired):

| Event | When |
|---|---|
| `on_message` | Every chat message (rate-limited) |
| `on_tool_call` | Before/after each tool dispatch on this plugin |
| `on_settings_changed` | User updated the plugin's settings |

If you need an event that's not yet wired, file an issue — we add
hooks based on real plugin needs, not speculation.

## `on_startup`

Called once after the plugin's IPC connection is established and the
register message has been ack'd. By this point:

- `aurora.*` is callable (the proxy has resolved)
- `plugin.config` is populated from the encrypted-decrypted settings
- Tools are visible in AURORAZ's catalog

Signature:

```python
@hook("on_startup")
async def on_startup(ctx) -> None:
    ...
```

`ctx` currently exposes:

- `ctx.plugin_id: str`
- `ctx.now: datetime` (timestamp at hook fire)

Best practices:

- **Keep it fast.** Slow startup blocks plugin registration; AURORAZ
  considers anything > 5s a hung plugin. If you have heavy init,
  spawn a background task:

  ```python
  @hook("on_startup")
  async def on_startup(ctx):
      asyncio.create_task(_heavy_init())
  
  async def _heavy_init():
      # do the slow thing here, plugin is already registered
      ...
  ```

- **Don't call tools from `on_startup`.** Tools are dispatched
  by the chat agent; calling your own tool from a hook is rarely
  what you want.

- **Logging here is captured.** Use `logger.info` for startup events;
  they'll show up in `<DATA_PATH>/logs/plugin-<id>.log`.

## `on_shutdown`

Called when AURORAZ is about to terminate the plugin (user disabled,
AURORAZ shutting down, etc.). The plugin has up to 5 seconds to
clean up before SIGTERM/SIGKILL.

Signature:

```python
@hook("on_shutdown")
async def on_shutdown(ctx) -> None:
    ...
```

Best practices:

- **Cancel background tasks cleanly.** If you spawned tasks in
  `on_startup`, cancel them here:

  ```python
  _bg_task = None
  
  @hook("on_startup")
  async def on_startup(ctx):
      global _bg_task
      _bg_task = asyncio.create_task(_loop())
  
  @hook("on_shutdown")
  async def on_shutdown(ctx):
      if _bg_task:
          _bg_task.cancel()
          try:
              await _bg_task
          except asyncio.CancelledError:
              pass
  ```

- **Persist state.** If your plugin keeps state in memory that should
  survive restarts, write it now (use `aurora.memory` for
  long-lived state; `plugin.config` updates aren't supported yet).

- **Don't make external API calls.** They might not finish in the
  shutdown window. Drain queues, then exit.

## Multiple handlers per event

You can register multiple handlers for the same event — they're all
called in registration order:

```python
@hook("on_startup")
async def init_db(ctx):
    ...

@hook("on_startup")
async def init_cache(ctx):
    ...
```

Useful for organizing init across files.

## Hooks vs tools

| | `@hook` | `@tool` |
|---|---|---|
| Triggered by | AURORAZ lifecycle | Chat agent dispatch |
| Returns | None | String (sent to agent) |
| Frequency | Once-ish | Many times during a session |
| Visible to user | No (internal) | Yes (Luna calls it) |

Don't put functionality in hooks that should be tools. Hooks are
for setup/teardown.

## Examples

### Background watcher

```python
from auroraz_sdk import Plugin, aurora, hook
import asyncio

plugin = Plugin(id="watcher", name="Watcher", version="0.1.0",
                permissions=["network:api.example.com", "notifications:show"])

_task = None


@hook("on_startup")
async def on_startup(ctx):
    global _task
    _task = asyncio.create_task(_watch_loop())


@hook("on_shutdown")
async def on_shutdown(ctx):
    if _task and not _task.done():
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass


async def _watch_loop():
    while True:
        try:
            new_event = await _check_external_service()
            if new_event:
                await aurora.notify(f"New event: {new_event['title']}")
        except Exception:
            pass
        await asyncio.sleep(60)
```

### Stateful plugin

```python
_state = {"counter": 0}


@hook("on_startup")
async def load_state(ctx):
    # Restore counter from memory
    hits = await aurora.memory.search("watcher:counter", k=1)
    if hits:
        try:
            _state["counter"] = int(hits[0]["text"].split("=")[1])
        except Exception:
            pass


@hook("on_shutdown")
async def save_state(ctx):
    await aurora.memory.remember(f"watcher:counter={_state['counter']}")
```

## See also

- [Tutorial 4: Subprocess best practices](../tutorials/04-subprocess-best-practices.md) — long-running patterns with hooks
- [reference/connection.md](connection.md) — how the lifecycle fits the IPC handshake
