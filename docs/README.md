# auroraz-sdk documentation

The official Plugin SDK for [AURORAZ](https://github.com/luraselenehalo/AURORAZ) — Personal AI OS.

## Start here

If you're new, follow this order:

1. **[Quickstart](quickstart.md)** — 10-minute "build and run a plugin"
2. **[Tutorial 1: Your first plugin](tutorials/01-first-plugin.md)** — 45 min walkthrough
3. **[Tutorial 2: Memory + tools](tutorials/02-memory-and-tools.md)** — 30 min, add memory APIs
4. **[Tutorial 3: Plugin with UI](tutorials/03-plugin-with-ui.md)** — 60 min, sandboxed iframe
5. **[Tutorial 4: Subprocess best practices](tutorials/04-subprocess-best-practices.md)** — 30 min, production patterns

After the tutorials, you have a working plugin and the foundations to
build more. The reference docs below are organized by topic.

## Reference

| Doc | What it covers |
|---|---|
| [api.md](reference/api.md) | Every public method + signature + return type |
| [manifest.md](reference/manifest.md) | Every `plugin.yaml` field |
| [permissions.md](reference/permissions.md) | Canonical permission vocabulary + alias table |
| [hooks.md](reference/hooks.md) | Lifecycle event handlers (`on_startup`, `on_shutdown`) |
| [connection.md](reference/connection.md) | Plugin → AURORAZ flow (IPC, lifecycle, settings) |
| [architecture.md](reference/architecture.md) | In-process vs subprocess, sandboxing |
| [troubleshooting.md](reference/troubleshooting.md) | Common errors + fixes |
| [migration.md](reference/migration.md) | Prototype plugins → published SDK |
| [publishing.md](reference/publishing.md) | Author-side publishing notes |

## By task

- **Setting up your dev environment** → [Tutorial 1](tutorials/01-first-plugin.md)
- **Reading/writing memory** → [Tutorial 2](tutorials/02-memory-and-tools.md), [api.md](reference/api.md#auroramemory)
- **Adding a UI** → [Tutorial 3](tutorials/03-plugin-with-ui.md), [manifest.md](reference/manifest.md#frontend-block-optional)
- **Authoring permissions** → [permissions.md](reference/permissions.md)
- **Production hardening** → [Tutorial 4](tutorials/04-subprocess-best-practices.md)
- **Debugging** → [troubleshooting.md](reference/troubleshooting.md)
- **Updating an existing plugin** → [migration.md](reference/migration.md)
- **Publishing** → [publishing.md](reference/publishing.md)

## Examples

Working code lives in `examples/`:

- [hello-world](../examples/hello-world/) — minimal subprocess plugin (1 tool, no permissions)
- [memory-bot](../examples/memory-bot/) — tools that read/write AURORAZ's memory
- [with-ui](../examples/with-ui/) — sandboxed iframe + postMessage protocol

Every tutorial mirrors one of these examples. If you get stuck, the
working code is right there.

## Audit

The `_audit.md` doc traces what's in the SDK package vs.
AURORAZ-internal. Useful if you're contributing to the SDK itself or
porting plugins between AURORAZ versions.
