# auroraz-sdk

Official Plugin SDK for AURORAZ - the Personal AI OS.

## Install

```
pip install auroraz-sdk
```

## Quickstart

```python
from auroraz_sdk import Plugin, aurora, hook, tool

plugin = Plugin(
    id="my-plugin",
    name="My Plugin",
    version="0.1.0",
    permissions=["memory:read", "memory:write"],
)


@tool(name="my_plugin_remember", description="Tell AURORAZ to remember something",
      when="user wants to remember information")
async def remember(thing: str) -> str:
    await aurora.memory.remember(thing)
    return f"Got it, will remember: {thing}"


@hook("on_startup")
async def on_startup(ctx):
    print("Plugin started")


if __name__ == "__main__":
    plugin.run()
```

See [docs/quickstart.md](docs/quickstart.md) for the 10-minute getting-started guide.

## Documentation

### Tutorials (start here)

- [Tutorial 1: Your first plugin](docs/tutorials/01-first-plugin.md) — 45 min
- [Tutorial 2: Memory + tools](docs/tutorials/02-memory-and-tools.md) — 30 min
- [Tutorial 3: Plugin with UI](docs/tutorials/03-plugin-with-ui.md) — 60 min
- [Tutorial 4: Subprocess best practices](docs/tutorials/04-subprocess-best-practices.md) — 30 min
- [Tutorial 5: Use brain (reasoning API)] — 30 min

### Reference

- [API](docs/reference/api.md)
- [Manifest fields](docs/reference/manifest.md)
- [Permissions](docs/reference/permissions.md)
- [Hooks](docs/reference/hooks.md)
- [Connection (IPC + lifecycle)](docs/reference/connection.md)
- [Architecture](docs/reference/architecture.md)
- [Troubleshooting](docs/reference/troubleshooting.md)
- [Migration (prototype → SDK)](docs/reference/migration.md)
- [Publishing](docs/reference/publishing.md)

### Quickstart

- [10-minute quickstart](docs/quickstart.md)

## Examples

- [hello-world/](examples/hello-world/) - minimal plugin
- [memory-bot/](examples/memory-bot/) - memory + tools
- [with-ui/](examples/with-ui/) - sandboxed iframe UI
- [research-bot/](examples/research-bot/) - reasoning API (K1 + K3, Stage 7)

## License

MIT - see [LICENSE](LICENSE).
