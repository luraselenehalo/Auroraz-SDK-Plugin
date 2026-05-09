# Tutorial 3: Plugin with custom UI (60 minutes)

You'll build **PomodoroTimer** — a plugin with both AI-callable tools
and a sandboxed iframe UI. By the end:

- A 25-minute Pomodoro timer with start / pause / reset
- Tools `start_pomodoro`, `cancel_pomodoro` Luna can call from chat
- A custom UI page in the AURORAZ sidebar with a live countdown
- Real-time update from the plugin to the iframe via postMessage

This tutorial mirrors `examples/with-ui/` for the structure. Working
example code is right there.

## Step 1: Manifest with `frontend` block (5 min)

```yaml
id: pomodoro-timer
name: "Pomodoro Timer"
version: "0.1.0"
description: "25-minute focus timer with chat tools and a sidebar UI."
author: "Your Name"
category: "productivity"
icon: "🍅"
tags: [pomodoro, timer, focus]

permissions:
  - notifications:show

sdk_entry: main.py

frontend:
  ui_entry: ui/index.html
  icon: "🍅"
  display_name: "Pomodoro"
  status_strip:
    - { label: "State", source: "state" }
    - { label: "Remaining", source: "remaining_sec" }
```

The new fields:

- `frontend.ui_entry` — relative path to the iframe entry HTML.
  Required for plugins that have a UI.
- `frontend.icon` — sidebar icon (overrides the top-level `icon`).
- `frontend.display_name` — sidebar tooltip (overrides `name`).
- `frontend.status_strip` — strip above the iframe showing live values.
  Each entry has `label` (text) and `source` (key in the plugin's
  settings or in postMessage state).

When this manifest loads, AURORAZ:

1. Adds a 🍅 icon to the sidebar (Plugins section)
2. Clicking it routes to a Plugin Page that loads the iframe
3. Status strip renders above the iframe with values from settings

## Step 2: Plugin Python code (10 min)

Create `main.py`:

```python
"""Pomodoro Timer — AURORAZ plugin with chat tools + sidebar UI."""

from __future__ import annotations

import asyncio
import logging
import time

from auroraz_sdk import Plugin, aurora, hook, tool

logger = logging.getLogger("auroraz.plugin.pomodoro-timer")

plugin = Plugin(
    id="pomodoro-timer",
    name="Pomodoro Timer",
    version="0.1.0",
    permissions=["notifications:show"],
)


# In-memory state. A real plugin would persist via aurora.memory or
# settings, but for the timer ephemeral state is fine.
_state = {
    "running": False,
    "started_at": 0.0,
    "duration_sec": 25 * 60,
}


@tool(
    name="pomodoro_timer_start",
    description="Start a 25-minute Pomodoro focus session.",
    when="user wants to start a focus session, pomodoro, or productivity timer",
)
async def start_pomodoro(duration_minutes: int = 25) -> str:
    if _state["running"]:
        elapsed = int(time.time() - _state["started_at"])
        remaining = max(0, _state["duration_sec"] - elapsed)
        return f"Already running ({remaining // 60}:{remaining % 60:02d} left)."
    _state["running"] = True
    _state["started_at"] = time.time()
    _state["duration_sec"] = duration_minutes * 60
    await aurora.notify(f"Pomodoro started ({duration_minutes} min)", via="app")
    return f"Started a {duration_minutes}-minute Pomodoro."


@tool(
    name="pomodoro_timer_cancel",
    description="Cancel the current Pomodoro.",
    when="user wants to stop, cancel, or end a pomodoro",
)
async def cancel_pomodoro() -> str:
    if not _state["running"]:
        return "No Pomodoro running."
    _state["running"] = False
    await aurora.notify("Pomodoro cancelled", via="app")
    return "Cancelled."


@hook("on_startup")
async def on_startup(_ctx) -> None:
    logger.info("[pomodoro-timer] started")


if __name__ == "__main__":
    plugin.run()
```

Two tools, both straightforward async handlers. They call
`aurora.notify` to show desktop toasts.

The state lives in a module-level dict — fine for a single subprocess.
A multi-instance plugin would use `aurora.memory` or its settings
store.

## Step 3: HTML/CSS/JS for the iframe (15 min)

### `ui/index.html`

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Pomodoro Timer</title>
  <link rel="stylesheet" href="app.css" />
</head>
<body>
  <main>
    <h1 id="time">25:00</h1>
    <div class="state" id="state">Idle</div>
    <div class="row">
      <button id="start">Start 25-min Pomodoro</button>
      <button id="cancel" disabled>Cancel</button>
    </div>
    <p id="status" class="muted">Initializing...</p>
  </main>
  <script src="app.js"></script>
</body>
</html>
```

### `ui/app.css`

```css
* { box-sizing: border-box; }
html, body {
  margin: 0; padding: 0;
  background: radial-gradient(circle at top, #1a1a2e, #0c0c14);
  color: #e8e8f0;
  font-family: 'Inter', system-ui, sans-serif;
  height: 100vh;
}
main {
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  height: 100vh; gap: 20px;
}
h1#time {
  font-size: 80px; font-weight: 200;
  letter-spacing: -0.04em; margin: 0;
  font-feature-settings: 'tnum';
  color: #c7b8ff;
}
.state {
  font-size: 14px; color: #888;
  text-transform: uppercase; letter-spacing: 0.1em;
}
.row { display: flex; gap: 12px; }
button {
  background: rgba(124, 90, 255, 0.18);
  color: #d6caff;
  border: 1px solid rgba(124, 90, 255, 0.5);
  border-radius: 8px;
  padding: 10px 18px;
  font-size: 14px;
  font-family: inherit;
  cursor: pointer;
}
button:hover { background: rgba(124, 90, 255, 0.32); }
button:disabled { opacity: 0.4; cursor: default; }
.muted { color: #555; font-size: 11px; }
```

### `ui/app.js`

```js
// Pomodoro UI — talks to AURORAZ via postMessage protocol.

(function () {
  const TRUSTED_ORIGINS = new Set([
    window.location.origin,
    'http://localhost:5173',
    'http://127.0.0.1:5173',
  ]);

  const timeEl = document.getElementById('time');
  const stateEl = document.getElementById('state');
  const statusEl = document.getElementById('status');
  const startBtn = document.getElementById('start');
  const cancelBtn = document.getElementById('cancel');

  let timerId = null;
  let endsAt = 0;

  function fmt(secs) {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  }

  function tick() {
    const remaining = Math.max(0, Math.round((endsAt - Date.now()) / 1000));
    timeEl.textContent = fmt(remaining);
    if (remaining === 0) {
      stop();
      stateEl.textContent = 'Done!';
      window.parent.postMessage(
        { type: 'plugin/notify', message: 'Pomodoro done!', level: 'info' },
        '*',
      );
    }
  }

  function start() {
    endsAt = Date.now() + 25 * 60 * 1000;
    stateEl.textContent = 'Running';
    startBtn.disabled = true;
    cancelBtn.disabled = false;
    timerId = setInterval(tick, 1000);
    tick();
  }

  function stop() {
    clearInterval(timerId);
    timerId = null;
    timeEl.textContent = '25:00';
    stateEl.textContent = 'Idle';
    startBtn.disabled = false;
    cancelBtn.disabled = true;
  }

  startBtn.addEventListener('click', start);
  cancelBtn.addEventListener('click', stop);

  window.addEventListener('message', (e) => {
    if (!TRUSTED_ORIGINS.has(e.origin)) return;
    const data = e.data || {};
    if (data.type === 'auroraz/init') {
      statusEl.textContent = `Connected to AURORAZ as ${data.plugin_id}`;
    }
  });

  window.parent.postMessage({ type: 'plugin/ready' }, '*');
})();
```

## Step 4: postMessage protocol (10 min)

The iframe is sandboxed (`allow-scripts allow-same-origin`). It can't
call AURORAZ's APIs directly. Communication happens via `postMessage`.

The protocol has 4 message types:

### From AURORAZ to iframe

- **`auroraz/init`** — sent once on iframe load:

  ```js
  {
    type: 'auroraz/init',
    plugin_id: 'pomodoro-timer',
    settings: { /* current settings values */ },
    permissions: ['notifications:show'],
  }
  ```

- **`auroraz/settings-changed`** — sent whenever settings update:

  ```js
  { type: 'auroraz/settings-changed', settings: { /* ... */ } }
  ```

### From iframe to AURORAZ

- **`plugin/ready`** — iframe signals it's loaded and listening:

  ```js
  window.parent.postMessage({ type: 'plugin/ready' }, '*');
  ```

- **`plugin/notify`** — show a toast in AURORAZ:

  ```js
  window.parent.postMessage(
    { type: 'plugin/notify', message: 'Pomodoro done!', level: 'info' },
    '*',
  );
  ```

- **`plugin/request-settings`** — ask for current settings:

  ```js
  window.parent.postMessage({ type: 'plugin/request-settings' }, '*');
  ```

### Origin checking

**Always check `event.origin`** in the iframe's message listener:

```js
const TRUSTED_ORIGINS = new Set([
  window.location.origin,         // production: same origin
  'http://localhost:5173',        // dev: Vite frontend
  'http://127.0.0.1:5173',
]);

window.addEventListener('message', (e) => {
  if (!TRUSTED_ORIGINS.has(e.origin)) return;
  // ... handle message
});
```

In production (Electron), iframe and parent share an origin. In dev,
Vite (5173) and the FastAPI backend (8741) are on different origins —
the iframe loads from 8741, parent dashboard runs on 5173.
Whitelisting both makes both work.

## Step 5: Real-time updates from plugin to iframe (10 min)

The current example has the timer logic entirely in the iframe — fine
for a Pomodoro. But many plugins need the Python side to push live
updates to the UI.

The pattern: plugin emits a postMessage payload via `aurora.notify` or
a custom IPC method, AURORAZ relays to the iframe.

For Stage 6a, the simplest path is plugin-driven UI: the plugin sends
toasts via `aurora.notify`, and the iframe polls or listens for its
own state.

A future Stage will add a direct plugin→iframe channel. For now, the
two main pipes are:

- `aurora.notify` → AURORAZ toast → user sees it
- iframe → AURORAZ via `plugin/notify` → AURORAZ toast → user sees it

## Step 6: Settings (5 min)

If you want user-configurable settings (e.g. timer duration), add a
`settings` block to the manifest:

```yaml
settings:
  default_duration_minutes:
    type: number
    label: "Default Pomodoro length"
    description: "Used when no duration argument is passed."
    default: 25
    min: 5
    max: 120
  notify_on_complete:
    type: boolean
    label: "Notify on completion"
    default: true
```

AURORAZ renders this as a form in the Plugin Page. Settings persist
to `<DATA_PATH>/plugins/pomodoro-timer/config.json`. Encrypted fields
(if you set `secret: true` or `type: password`) are encrypted with
the AURORAZ master key — see [reference/connection.md](../reference/connection.md).

The plugin reads them via... a Stage 6a.2 limitation: the
subprocess plugin's `Plugin.config` dict is populated from the
encrypted-decrypted config at spawn time. Settings changes take
effect on next plugin restart.

## Step 7: Test in AURORAZ (5 min)

Drop the folder into `backend/plugins/pomodoro-timer/`, install +
enable. The 🍅 icon should appear in the sidebar.

Click it. The Plugin Page should:

1. Render the header (Pomodoro Timer · v0.1.0 · subprocess · 2 tools)
2. Show the status strip with State / Remaining
3. Embed the iframe — you see the 25:00 countdown
4. Right rail shows Activity feed, Settings, Permissions

Click **Start 25-min Pomodoro** in the iframe. The timer counts down.
When it hits 0, the iframe sends `plugin/notify` and AURORAZ shows a
toast.

Try via chat:

> **You:** Start a Pomodoro

Luna calls `pomodoro_timer_start`. The plugin shows a toast.

## Concepts

### Why iframes (sandbox boundary)

The iframe runs in its own browsing context. It can't read the parent
dashboard's DOM, intercept the user's chat, or steal session storage.
It's a security boundary — even a buggy plugin UI can't compromise
AURORAZ. postMessage is the only channel.

### Cross-origin in dev, same-origin in production

Iframe URL: `http://localhost:8741/api/plugins/pomodoro-timer/ui/index.html`  
Parent dashboard URL: `http://localhost:5173/` (dev) or
`file://...` (Electron production)

In dev these are different origins. In production Electron, AURORAZ
serves both from the bundled webserver — same origin. The iframe's
TRUSTED_ORIGINS set should cover both.

### Settings encryption is automatic

If your manifest schema marks a setting `secret: true` or
`type: password`, AURORAZ encrypts the value at rest using
[Fernet + the OS keychain](../reference/connection.md). The plugin
reads decrypted plaintext via `Plugin.config[key]`. You don't need to
think about it.

## Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| iframe shows blank | UI files not at `frontend.ui_entry` path | Check `ui_entry: ui/index.html` matches actual file location |
| iframe shows 404 | Path traversal blocked | `ui_entry` can only point inside the plugin folder; no `..` |
| `auroraz/init` never arrives | Iframe didn't send `plugin/ready` | Send `plugin/ready` on iframe load |
| Toast never appears | Origin check failing | Add Vite dev origin to TRUSTED_ORIGINS in your iframe JS |
| Sidebar icon doesn't appear | `frontend.ui_entry` missing | Add the `frontend:` block |
| CSP error in iframe | Inline scripts disallowed | Move to external `app.js`; AURORAZ serves it via the same static route |

## What you learned

- The `frontend:` manifest block (ui_entry, icon, display_name, status_strip)
- How AURORAZ serves iframe assets
- The postMessage protocol (4 message types)
- Origin checking in dev vs production
- The sandbox boundary — why plugins can't directly manipulate AURORAZ

## Next steps

→ [Tutorial 4: Subprocess best practices](04-subprocess-best-practices.md) — production patterns for plugins that run in their own process.
