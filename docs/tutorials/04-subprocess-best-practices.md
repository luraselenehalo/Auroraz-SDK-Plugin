# Tutorial 4: Subprocess best practices (30 minutes)

Production patterns for plugins running as subprocesses (the
recommended path for any third-party AURORAZ plugin).

## Why subprocess (not in-process)?

A subprocess plugin runs in its own Python process, connected to
AURORAZ via IPC. Compared to in-process (where the plugin lives in
AURORAZ's address space), subprocess gives you:

| | In-process | Subprocess |
|---|---|---|
| Crash isolation | None — panics crash AURORAZ | Full — your plugin can die without affecting Aurora |
| Permission isolation | Process-level shared memory | IPC-gated (AURORAZ checks every call) |
| Lifecycle independence | Tied to AURORAZ's | Independent — you can restart without rebooting AURORAZ |
| Dependencies | Shared with AURORAZ's pip env | Your own (via requirements.txt) |
| Memory cost | Zero overhead | ~30 MB per plugin |

Use subprocess unless you have a specific reason for in-process
(e.g. you need shared state with AURORAZ's services and you control
both sides). For third-party publishing, always subprocess.

## Pattern 1: Long-running background work

If your plugin watches an external service (Discord events, RSS
feeds, a webhook), you need a background task that lives between
tool calls.

The right place is `@hook("on_startup")`:

```python
import asyncio
from auroraz_sdk import Plugin, hook, tool

plugin = Plugin(id="watcher", name="Watcher", version="0.1.0",
                permissions=["network"])

_watcher_task = None


@hook("on_startup")
async def on_startup(_ctx):
    global _watcher_task
    _watcher_task = asyncio.create_task(_watch_loop())


@hook("on_shutdown")
async def on_shutdown(_ctx):
    global _watcher_task
    if _watcher_task and not _watcher_task.done():
        _watcher_task.cancel()
        try:
            await _watcher_task
        except asyncio.CancelledError:
            pass


async def _watch_loop():
    while True:
        try:
            await _check_external_service()
        except Exception:
            logger.exception("[watcher] check failed; retrying in 60s")
        await asyncio.sleep(60)
```

Key points:

- Use `asyncio.create_task` to launch background work
- Always handle `CancelledError` cleanly in `on_shutdown`
- Wrap the loop body in `try/except` so one bad iteration doesn't
  kill the watcher

## Pattern 2: External API integrations

Network calls go through standard HTTP libraries (`httpx` is a fine
choice and is already in AURORAZ's deps). Permissions:

```yaml
permissions:
  - network:api.example.com
  - network:auth.example.com
```

Host-scoped permissions are precise: AURORAZ enforces that your
plugin only talks to the declared hosts. Use them for any
public API integration.

For OAuth-style flows, store the access token in encrypted settings:

```yaml
settings:
  api_token:
    type: password
    label: "API token"
    description: "Stored encrypted at rest."
```

The plugin reads it via `plugin.config["api_token"]` — AURORAZ
decrypts before handing it over.

```python
import httpx

async def _api_call(path: str):
    token = plugin.config.get("api_token", "")
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"https://api.example.com{path}",
                             headers={"Authorization": f"Bearer {token}"})
        r.raise_for_status()
        return r.json()
```

Retry + backoff for flaky APIs:

```python
async def _api_call_with_retry(path: str, max_retries: int = 3):
    delay = 1.0
    for attempt in range(max_retries):
        try:
            return await _api_call(path)
        except httpx.HTTPStatusError as e:
            if e.response.status_code < 500:
                raise  # don't retry 4xx
            if attempt == max_retries - 1:
                raise
        except (httpx.TimeoutException, httpx.NetworkError):
            if attempt == max_retries - 1:
                raise
        await asyncio.sleep(delay)
        delay *= 2
```

## Pattern 3: Caching

AURORAZ doesn't auto-cache anything for your plugin — that's intentional.
If your plugin makes expensive calls, cache them yourself:

```python
import time

_cache: dict[str, tuple[float, object]] = {}
CACHE_TTL_SEC = 300  # 5 min

async def cached_lookup(key: str):
    now = time.time()
    cached = _cache.get(key)
    if cached and now - cached[0] < CACHE_TTL_SEC:
        return cached[1]
    value = await _expensive_call(key)
    _cache[key] = (now, value)
    return value
```

For more sophisticated caching, `functools.lru_cache` with a
TTL wrapper works well. Don't pull in Redis or memcached unless you
actually need cross-process caching — which is rare for plugins.

## Pattern 4: Dependencies

Subprocess plugins can ship their own `requirements.txt`:

```
# requirements.txt
httpx>=0.27,<0.30
beautifulsoup4>=4.12
```

When AURORAZ installs your plugin, it runs `pip install -r requirements.txt`
into the plugin's isolated venv (or, in dev, into AURORAZ's venv if
you're dropping the folder manually).

Best practices:

- **Pin major versions** — `httpx>=0.27,<0.30` not `httpx`. Saves you
  from breaking changes upstream.
- **Minimize deps** — every dep adds boot time and disk
- **Avoid C extensions if possible** — they need wheels for the
  user's platform; pure-Python deps install faster

## Pattern 5: Logging

Use Python's stdlib `logging` module. AURORAZ captures stdout and
stderr from subprocess plugins and routes them to the desktop log:

```python
import logging

logger = logging.getLogger("auroraz.plugin.my-plugin")

# In a tool:
@tool(name="my_tool", ...)
async def my_tool(query: str):
    logger.info("[my-plugin] processing %r", query)
    try:
        result = await _process(query)
        logger.debug("[my-plugin] got %d items", len(result))
        return str(result)
    except Exception:
        logger.exception("[my-plugin] processing failed")
        return "Internal error; see plugin logs."
```

Log levels:

- `DEBUG` — verbose tracing, only when something's wrong
- `INFO` — meaningful state transitions ("plugin started", "API call ok")
- `WARNING` — recoverable issues
- `ERROR` — unrecoverable; tool returns an error to user
- Use `logger.exception` (not `logger.error`) inside `except` blocks
  to capture the traceback

## Pattern 6: Testing locally

For unit-level confidence without AURORAZ running:

```python
# test_my_plugin.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from auroraz_sdk import Plugin
import main  # your plugin module


@pytest.mark.asyncio
async def test_greet():
    # Mock the aurora client
    main.aurora = MagicMock()
    main.aurora.memory = MagicMock()
    main.aurora.memory.remember = AsyncMock(return_value={"id": "mem_123"})
    
    result = await main.remember(text="test fact")
    main.aurora.memory.remember.assert_called_once_with("test fact")
    assert "test fact" in result
```

The `auroraz` proxy is a module-level variable, so mocking it
works. Don't try to integration-test against a running AURORAZ from
unit tests — that's a separate concern (call it E2E and run it less
often).

## Pitfalls

### Blocking I/O on the IPC thread

If a tool handler does sync I/O (`requests.get`, `time.sleep`,
`open()` of a 500MB file), it blocks the entire IPC loop. Other
tool calls queue up and time out.

Fix: use async libraries (`httpx`, `aiofiles`) or push work to a
thread pool:

```python
import asyncio

@tool(name="heavy_compute")
async def heavy_compute(data: str) -> str:
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, _sync_heavy, data)
    return result
```

### Too-frequent `aurora.notify`

Each toast is a real desktop notification. Calling notify in a tight
loop floods the user. Rate-limit yourself:

```python
import time

_last_notify = 0
NOTIFY_RATE_LIMIT = 5.0  # seconds


async def notify_once(message: str):
    global _last_notify
    now = time.time()
    if now - _last_notify < NOTIFY_RATE_LIMIT:
        return
    _last_notify = now
    await aurora.notify(message)
```

### Memory leaks in long-running hooks

If your `on_startup` task accumulates state without bound (queue
that never drains, dict that never evicts), you'll leak across
hours of use. Audit your hooks: any unbounded collection should have
an eviction policy (TTL, max size, etc.).

### Permission scope creep

Don't declare `network` (any host) when you only need
`network:api.example.com`. The Plugin Page shows your declared
permissions to users — minimal lists build trust.

If you're not sure which permission you need, the linter (`PERM003`)
flags declared-but-unused permissions. Run `auroraz-sdk lint .` and
trim.

## Checklist for production

Before you publish:

- [ ] All `@tool` names prefixed with plugin id
- [ ] Permissions declared minimally; lint passes 0 errors
- [ ] No sync I/O in tool handlers
- [ ] All async tasks have `try/except` + logging
- [ ] `on_startup` work is fast (< 2s) — heavy init goes to a
      background task
- [ ] `on_shutdown` cancels background tasks cleanly
- [ ] External API tokens stored in encrypted settings (`type: password`)
- [ ] Notifications are rate-limited
- [ ] `requirements.txt` pins major versions
- [ ] README explains what the plugin does + lists permissions

## Where to go from here

- → [reference/connection.md](../reference/connection.md) — deep dive on
  the IPC + lifecycle
- → [reference/troubleshooting.md](../reference/troubleshooting.md) —
  common runtime issues
- → [reference/publishing.md](../reference/publishing.md) — when you're
  ready to share
