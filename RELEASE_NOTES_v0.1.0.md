# auroraz-sdk v0.1.0

The first public release of the Plugin SDK for **AURORAZ — Personal AI OS**.

## Install

```bash
pip install auroraz-sdk
```

## What's in this release

### Core API

- **`Plugin(id, name, version, permissions)`** — declare your plugin
- **`@tool(name, description, when)`** — register tools the chat agent can call
- **`@hook("on_startup" | "on_shutdown")`** — lifecycle hooks
- **`aurora.memory`** — read/write AURORAZ's long-term memory
- **`aurora.notify`** — show desktop toasts
- **`aurora.inject`** — inject context into the chat system prompt
- **`aurora.context.*`** — read current emotion / intent / active window

### Tooling

- **`auroraz_sdk.lint`** — lint your manifest + code (10 rules covering manifest, permissions, API contracts, tool naming)
- **`auroraz_sdk.scaffold`** — generate plugin boilerplate from templates (in-process or subprocess)
- **`auroraz_sdk.permission_vocab`** — canonical permission vocabulary + alias normalization
- **`auroraz-sdk` CLI** — `init`, `lint`, `pack`, `validate` from your shell

### Documentation

**4 tutorials** (long-form, hands-on):

- Tutorial 1: Your first plugin (45 min)
- Tutorial 2: Memory + tools (30 min)
- Tutorial 3: Plugin with UI (60 min)
- Tutorial 4: Subprocess best practices (30 min)

**9 reference docs** (encyclopedia):

- API reference
- Manifest fields
- Permission vocabulary
- Hooks
- Connection (IPC + lifecycle)
- Architecture (in-process vs subprocess)
- Troubleshooting (15+ common errors with fixes)
- Migration (prototype plugins → SDK)
- Publishing

**3 working examples**:

- `hello-world` — minimal subprocess plugin
- `memory-bot` — memory read/write tools
- `with-ui` — sandboxed iframe + postMessage

Every tutorial mirrors a working example. Every example lints clean
(0 errors). Every code block in tutorials is straight from a working
example.

### Security

- Plugin permissions canonically named (`memory:read`, `network:<host>`, …) with
  full backward-compat for legacy `memory_read` / `memory.read` / `prompt:inject` aliases
- Plugin settings encrypted at rest (Fernet + OS keychain) when marked
  `secret: true` or `type: password`
- Plugin signing via Ed25519 verified at install time
- Version compatibility enforcement (`min_auroraz_version` is a real load-time gate)

## Compatibility

- Requires AURORAZ desktop **>= 0.1.0**
- Python **>= 3.10**

## Verified

The 3 examples were installed into AURORAZ desktop and exercised end-to-end:

- All 3 plugins spawn as subprocesses
- All 3 register tools over IPC successfully
- Memory roundtrip (`remember` → `recall`) goes through ChromaDB
- Notify roundtrip (`aurora.notify` from tool) reaches the AURORAZ toast layer
- Permissions enforced server-side (declared `memory:read` / `memory:write` actually gate the call)

## What's not in this release (planned)

- **Remote marketplace** (Stage 6b) — for now, distribute by copy-into-folder OR `.azpkg` install
- **Hot reload** of plugins during dev (currently restart required)
- **Plugin debugging dashboard** (today: tail logs + Plugin Page activity feed)
- **Plugin upload UI** in AURORAZ desktop (today: `POST /api/plugins/install-azpkg`)

## Acknowledgments

Built by [ResinCore](https://github.com/luraselenehalo) for AURORAZ.

## License

MIT — see [LICENSE](LICENSE).

---

**Get started**: [docs/quickstart.md](docs/quickstart.md) (10 min) or [Tutorial 1](docs/tutorials/01-first-plugin.md) (45 min).
