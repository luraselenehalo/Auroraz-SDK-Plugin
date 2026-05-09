# Architecture

How an auroraz-sdk plugin connects to AURORAZ desktop.

## In-process vs subprocess

AURORAZ supports two plugin shapes:

| | In-process | Subprocess |
|---|---|---|
| Lives in | AURORAZ's address space | Its own Python process |
| Boilerplate | Subclass `AURORAZPlugin` | Construct `Plugin(...)`, call `plugin.run()` |
| Crash isolation | None — a panic kills AURORAZ | Full — subprocess can die without affecting Aurora |
| Memory cost | Zero overhead | ~30 MB venv per plugin |
| Best for | First-party, trusted, hot-path plugins | Third-party, untrusted, anything that pip-installs deps |

The auroraz-sdk publication is **subprocess-first** — that's the safer
default for the public ecosystem. In-process authoring is supported
(via `AURORAZPlugin` exported from the SDK), but the wizard scaffolds
subprocess by default.

## Plugin lifecycle (subprocess)

```
1. AURORAZ desktop installs the plugin → plugin.yaml discovered, registry updated
2. User clicks Enable → SubprocessPluginLauncher spawns `python backend/main.py`
3. The subprocess connects to AURORAZ via Unix socket / TCP loopback (AURORAZ_IPC_ADDR)
4. Plugin sends `plugin.register` over IPC with its tool catalog + permissions
5. AURORAZ records the catalog; the agent's planner can now call the tools
6. Plugin sits in an event loop, awaits tool calls + lifecycle events
7. User clicks Disable → AURORAZ sends SIGTERM → on_shutdown hook → process exits
```

No HTTP between plugin and AURORAZ — IPC is a length-prefixed JSON
stream over a local socket. Latency is ~1ms, throughput ~10k req/s
locally.

## IPC permission model

Every aurora API call routes through AURORAZ's IPC server, which checks
the calling plugin's declared permissions before dispatching:

```
Plugin                 AURORAZ
  |                       |
  | aurora.memory.search  |
  |---------------------->|
  |                       | _check_permission("memory:read")
  |                       | <-- plugin.permissions had memory:read? YES
  |                       | dispatch to ChromaDB
  |<----- result ---------|
```

If the permission is missing the call returns
`PermissionDeniedError` to the plugin, which surfaces as a tool error
in chat. The plugin never has the option to bypass — the check is
server-side.

## Memory sandboxing

`aurora.memory.remember(text)` automatically tags the memory with the
calling plugin's id. `aurora.memory.search(query)` scopes results to
the calling plugin's namespace. So plugins can't read each other's
memories.

The exception is the global semantic pool used by AURORAZ itself —
read-only on shared memories with no plugin tag. Documented in
`api.md`.

## Settings storage

When AURORAZ writes a setting marked `secret: true` or `type: password`
in your `plugin.yaml` schema, it encrypts the value with the AURORAZ
master key (Fernet, AES-128 in CBC + HMAC-SHA256). The master key
lives in the OS keychain — Windows Credential Manager / macOS
Keychain / Linux Secret Service — falling back to a key file on disk
when the keychain isn't available.

When your plugin reads the setting (via `aurora.settings.get(key)`
in subprocess, or `services.settings.get(key)` in-process), AURORAZ
decrypts transparently. The plugin sees plaintext.

If you want a setting redacted from the API but readable inside the
plugin, mark it `secret: true` in the manifest schema.

## .azpkg signed packaging (Stage 5+)

For remote distribution, plugins are packaged as `.azpkg` files —
signed ZIP archives. The verifier (in AURORAZ desktop) checks:

1. Per-file SHA-256 hashes match the manifest
2. Ed25519 signature over the manifest is valid against the bundled
   public key
3. No member path escapes the plugin folder (path-traversal guard)

Stage 6a's SDK ships a CLI command `auroraz-sdk pack` that builds a
`.azpkg` from your plugin folder using a key generated on first use.
Authors who want a stable identity manage their own keys — the SDK CLI
can use a key path passed via `--key`.

## Where the SDK ends and AURORAZ begins

Anything under `auroraz_sdk.*` is portable — runs anywhere Python +
the listed deps run. The IPC client doesn't connect anywhere unless
`AURORAZ_IPC_ADDR` is set in the environment, which only AURORAZ
desktop's launcher sets. So your plugin's `main.py` running standalone
just hangs waiting for a connection — that's expected.

To test a plugin without AURORAZ:
1. Use the SDK CLI: `auroraz-sdk validate .` parses + lints the
   manifest and code without actually running the plugin.
2. Stub the aurora client in unit tests by importing
   `auroraz_sdk.aurora_client.AuroraClient` and constructing one with
   a mock IPC client.
