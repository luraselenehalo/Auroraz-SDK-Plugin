# Plugin connection: how plugins reach AURORAZ

A deep dive into what happens between writing your plugin and AURORAZ
calling its tools. Covers both subprocess (recommended) and in-process
plugins.

## High-level flow

```
[Plugin folder on disk]
    ↓ (registry discovery)
[AURORAZ scans backend/plugins/]
    ↓ (manifest parsing + permission canonicalization + version compat)
[Registry records the plugin; plugins.json is updated on install/enable]
    ↓ (subprocess spawn OR in-process import)
[Plugin sends `plugin.register` over IPC]
    ↓
[AURORAZ records the plugin's tools, hooks, permissions]
    ↓
[Available in agent's tool catalog; tools dispatch via execute_tool]
```

## Section 1: Plugin discovery

AURORAZ scans `backend/plugins/` at startup. For each subdirectory:

1. Skip if the name starts with `.` or `__` (caches, hidden)
2. Look for `plugin.yaml` (preferred) or `plugin.json`
3. Parse + validate the manifest:
   - Required fields: `id`, `name`, `version`
   - `id` must match `^[a-z][a-z0-9_-]{1,49}$`
   - `permissions` normalized through Stage 3's vocabulary
     (`memory_read` → `memory:read`, etc.)
   - `min_auroraz_version` checked against running version
4. Record in the registry; expose via `/api/plugins/installed`

Discovery is cheap (~1ms per plugin); it runs on every backend boot.
Adding a folder doesn't require a restart — call
`POST /api/plugins/install` to trigger registry rediscover.

The state file at `<DATA_PATH>/plugins/plugins.json` decides which
plugins are *enabled* (load + run), independent of which are
*installed* (visible in marketplace).

## Section 2: Subprocess plugins

The launch sequence:

### 2.1 SDK detection

AURORAZ asks `_is_sdk_plugin()` — does this plugin folder ship a
subprocess entry point? Resolution order:

1. Manifest's `sdk_entry: <relative-path>` (Stage 6a recommended)
2. Convention: `backend/main.py` (Stage 4 scaffolder default)
3. Convention: `main.py` at plugin root

Then peek the entry file's first 50 lines for SDK import hints
(`from auroraz_sdk import …` or the older `from sdk import …`). If
present → it's an SDK plugin → spawn as subprocess.

### 2.2 IPC server

Before spawning anything, AURORAZ starts an IPC server (Unix socket
on Linux/Mac, TCP loopback on Windows). It allocates a per-plugin
address.

### 2.3 Spawn

```python
asyncio.create_subprocess_exec(
    sys.executable, str(main_py),
    env={
        "AURORAZ_IPC_ADDR": ipc_addr,         # how to reach the IPC server
        "AURORAZ_PLUGIN_ID": plugin_id,        # so plugin knows its own id
        "AURORAZ_PLUGIN_CONFIG": json.dumps(config_dict),  # decrypted settings
        ...
    },
    stdout=PIPE, stderr=PIPE,
)
```

`sys.executable` is AURORAZ's own Python (the venv that has
`auroraz-sdk` installed).

### 2.4 IPC handshake

The plugin's `Plugin.run()` connects to `AURORAZ_IPC_ADDR`, then
sends `plugin.register` with its tool catalog and permissions:

```json
{
  "method": "plugin.register",
  "params": {
    "id": "memory-bot",
    "name": "Memory Bot",
    "version": "0.1.0",
    "permissions": ["memory:read", "memory:write"],
    "tools": [
      {"name": "memory_bot_remember", "description": "...", "parameters": {...}},
      {"name": "memory_bot_recall", "description": "...", "parameters": {...}}
    ],
    "hooks": ["on_startup"]
  }
}
```

AURORAZ records this and the plugin is now in the agent's tool
catalog. `on_startup` hooks fire next.

### 2.5 Steady state

The plugin sits in an event loop. AURORAZ sends:

- **`tool.call`** when an agent dispatches a tool
- **`hook.event`** for lifecycle hooks (currently rare beyond startup/shutdown)
- **Shutdown signal** (SIGTERM on Unix, equivalent on Windows) to
  terminate

The plugin sends:

- **`<method>.<call>`** to invoke aurora APIs (`aurora.memory.remember`, etc.)
- **`tool.result`** as a response to a `tool.call`
- **`plugin.register_tool`** if it dynamically registers a new tool
  after startup

All messages are line-delimited JSON-RPC. ~1ms latency, ~10k req/s
locally.

### 2.6 Crash + restart

If the subprocess crashes (non-zero exit), AURORAZ's launcher does
exponential backoff (1s, 2s, 4s, 8s, capped at 30s) and respawns up
to 3 times. After that it gives up and marks the plugin `error`.

## Section 3: In-process plugins

Less common, but supported. Identified by:

- `entry_points.backend: "<module>:<ClassName>"` in the manifest
- The class subclasses `auroraz_sdk.AURORAZPlugin`

AURORAZ imports the module, instantiates the class, and calls
`on_enable()`. The plugin runs in AURORAZ's address space, sharing
memory and event loop. No IPC.

Trade-off: faster + no resource overhead, but a panic in the plugin
crashes AURORAZ. Use only for first-party plugins.

## Section 4: The `plugin.register` message

Full schema:

```json
{
  "method": "plugin.register",
  "params": {
    "id": "string (required, plugin id)",
    "name": "string (required, display name)",
    "version": "string (required, semver)",
    "permissions": ["string (canonical permission)"],
    "tools": [
      {
        "name": "string (tool id)",
        "description": "string (one-line summary)",
        "when": "string (planner hint)",
        "parameters": {
          "type": "object",
          "properties": {
            "<param_name>": {"type": "string|number|boolean|...", "description": "..."}
          },
          "required": ["<param_name>"]
        }
      }
    ],
    "hooks": ["on_startup", "on_shutdown", ...]
  }
}
```

The `parameters` schema is JSON Schema; AURORAZ validates tool calls
against it before dispatching.

## Section 5: How tools become tool calls

1. Plugin declares (`@tool` at module load OR `register_tool` at runtime)
2. AURORAZ's IPC server records the catalog, exposes via
   `agent_service.get_tool_catalog()`
3. Chat agent's planner (Luna) sees the tool, decides to use it
4. AURORAZ dispatches via `agent_service.execute_tool(tool_name, params)`
5. The dispatcher routes to the owning plugin's IPC connection
6. Plugin's loop receives `tool.call`, runs the handler, sends
   `tool.result`
7. Result feeds back into the chat agent's response

End-to-end latency: ~50-200ms for a no-op tool, dominated by Luna's
planning, not IPC.

## Section 6: aurora client roundtrip

When your code calls `aurora.memory.remember("hello")`:

1. The lazy proxy resolves to a real `_MemoryClient` (set up after
   `plugin.run()` connects)
2. `_MemoryClient.remember` calls `self._perms.require("memory:write")`.
   Local check — fails fast if the permission isn't declared.
3. Calls `self._ipc.call("memory.remember", {"text": "hello"})` — sends
   the IPC request.
4. AURORAZ-side IPC server receives, calls `_check_permission(method,
   plugin_id)` (server-side double-check; the plugin can't lie).
5. AURORAZ dispatches to the memory service (ChromaDB / ArcadeDB).
6. Result flows back as a `<request_id>.response` IPC message.
7. The plugin awaits, gets the dict, returns it from `remember`.

## Section 7: Settings flow

Per-plugin settings live at:

```
<DATA_PATH>/plugins/<plugin_id>/config.json
```

When the user edits a setting in the Plugin Page:

1. POST `/api/plugins/<id>/settings` arrives with new values
2. Backend validates against the manifest schema
3. For each field: if `secret: true` or `type: password`, encrypt
   with the AURORAZ master key (Fernet). Otherwise store as-is.
4. Write the JSON file
5. Echo back the values, with secrets redacted to `<saved>`

When a subprocess plugin spawns:

1. AURORAZ reads `config.json`
2. Decrypts any `azenc:v1:` blobs
3. Sets `AURORAZ_PLUGIN_CONFIG` env var to the decrypted JSON
4. Plugin reads `os.environ["AURORAZ_PLUGIN_CONFIG"]` → `Plugin.config` dict
5. Plugin sees plaintext

Settings changes take effect on the next plugin restart. There's no
hot reload yet (planned).

## Section 8: UI iframe connection

Plugins with a `frontend.ui_entry` block get a sandboxed iframe page:

1. AURORAZ adds the plugin's icon to the sidebar
2. Clicking it routes to a Plugin Page
3. The page renders the iframe pointing to
   `/api/plugins/<id>/ui/<ui_entry>`
4. AURORAZ serves files from the plugin's folder (path-traversal
   guarded)
5. The iframe gets sandbox attributes: `allow-scripts allow-same-origin`
6. postMessage protocol (4 message types) handles communication —
   see [Tutorial 3](../tutorials/03-plugin-with-ui.md)

## Section 9: Distribution

For now (Stage 6a):

- Drop the plugin folder into `backend/plugins/<id>/`
- POST `/api/plugins/<id>/install` then `/enable`
- Or use the marketplace UI in the dashboard

For Stage 6b (future):

- Author packs `.azpkg` (signed Ed25519)
- User installs via marketplace remote OR
- POST `/api/plugins/install-azpkg` with a local file path

The verifier (Stage 5) is already in AURORAZ — it's just waiting for
the marketplace UI / remote download to plug into.

## Section 10: Debugging the connection

### Boot logs

Look at AURORAZ's stdout/stderr (or the file at
`<DATA_PATH>/logs/auroraz.log`):

```
[Registry] Discovered N plugins
[Registry] Loaded state for M plugin(s); enabled=[…]
[PluginLoader] Skipping 'X': not in enabled_ids
[SDKPluginManager] Started subprocess plugin 'Y'
[IPCServer] Registered plugin 'Y' v0.1.0 (tools=2, hooks=1)
```

### Plugin logs

Subprocess stdout/stderr is captured by AURORAZ and written to:

```
<DATA_PATH>/logs/plugin-<id>.log
```

(or visible in AURORAZ desktop's Plugin Page activity feed).

### Chrome DevTools for iframe

Open Chrome DevTools → Application → Frames → find the plugin's
iframe. Console errors there are usually CSP / origin / postMessage
issues. The Network tab shows iframe asset loads.

### IPC errors

`[IPCServer] Connection loop error: ...` in the log usually means
the plugin subprocess died. Check the plugin's log for the actual
crash.

## See also

- [Tutorial 1: First plugin](../tutorials/01-first-plugin.md) — walk through the connection step-by-step
- [Tutorial 4: Subprocess best practices](../tutorials/04-subprocess-best-practices.md) — production patterns
- [Reference: troubleshooting](troubleshooting.md) — common errors + fixes
