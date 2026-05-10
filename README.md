<div align="center">

# auroraz-sdk

**Official Plugin SDK for [AURORAZ](https://github.com/luraselenehalo/AURORAZ) — the Personal AI OS**

*Build plugins that extend a local-first AI companion with custom tools, memory, reasoning, and UI.*

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Status: active](https://img.shields.io/badge/status-active-brightgreen.svg)](#roadmap)
[![Version: 0.2.0](https://img.shields.io/badge/version-0.2.0-orange.svg)](RELEASE_NOTES_v0.2.0.md)

[**Quickstart**](docs/quickstart.md) · [**Tutorials**](docs/tutorials/) · [**API Reference**](docs/reference/api.md) · [**Examples**](examples/)

</div>

---

## ✨ What is this?

`auroraz-sdk` lets you build plugins for **AURORAZ** — a Personal AI OS that runs entirely on your machine, no cloud required.

A plugin can:

- 🔧 **Register custom tools** the AI calls when relevant to the conversation
- 🧠 **Invoke the reasoning engine** (K0 / K1 / K2 / K3 levels) directly from your code
- 💾 **Read & write memory** to give the AI persistent, plugin-scoped context
- 🎨 **Ship custom UIs** that render inside the AURORAZ desktop app (sandboxed iframes)
- 🔐 **Store encrypted secrets** safely via the OS keychain
- 📡 **Listen to lifecycle events** through the hooks system

All plugins run sandboxed as subprocesses with explicit, declared permissions.

---

## 🎯 Philosophy: The COE Framework

The SDK is organized around three concerns. Every API surface fits into one of them.

| | Concern | What it covers |
|---|---|---|
| **C** | **Controllable** | What your plugin is allowed to do — permissions, consent, audit logs, confirmations, limits, and revocation. |
| **O** | **Ownership** | What your plugin can access or store — user data, memory, identity, files, outputs, IP, and export boundaries. |
| **E** | **Ecosystem** | What your plugin can connect to — tools, devices, services, workflows, agents, and external systems. |

If a feature doesn’t fit one of these, it doesn’t belong in a plugin.

Plugins extend Aurora’s ecosystem — they must not weaken user control, ownership, or trust.

---

## 📦 Install

Requires **Python 3.10+**.

```bash
# Latest stable (Core SDK + Reasoning API)
pip install auroraz-sdk

# Pin a specific version
pip install auroraz-sdk==0.2.0
```

You'll also need the **AURORAZ desktop app** to run plugins — the SDK handles authoring; the desktop app is the runtime that loads, sandboxes, and routes IPC. Get it from Auroraz.

---

## 🚀 Quickstart

A full plugin in under 30 lines:

```python
from auroraz_sdk import Plugin, aurora, hook, tool

plugin = Plugin(
    id="my-plugin",
    name="My Plugin",
    version="0.1.0",
    permissions=["memory:read", "memory:write"],
)


@tool(
    name="my_plugin_remember",
    description="Tell AURORAZ to remember something",
    when="user wants to remember information",
)
async def remember(thing: str) -> str:
    await aurora.memory.remember(thing)
    return f"Got it, will remember: {thing}"


@hook("on_startup")
async def on_startup(ctx):
    print("Plugin started")


if __name__ == "__main__":
    plugin.run()
```

Drop this into a folder with a `plugin.yaml` manifest, point AURORAZ at it, and the AI will call `my_plugin_remember` when the conversation calls for it.

See the [10-minute quickstart](docs/quickstart.md) for the full first-plugin walkthrough.

---

## 🧱 Core SDK (v0.1.0)

The Core SDK gives your plugin everything it needs to participate in a chat session.

### Tools

Decorate any async function with `@tool(...)` and AURORAZ's planner can call it. The `when` field tells the planner *when* the tool is relevant — the more specific, the better the routing.

```python
@tool(name="weather_lookup", when="user asks about weather in a specific city")
async def lookup(city: str) -> str:
    ...
```

### Memory API

Plugin-scoped memory backed by ChromaDB. Each plugin sees only its own writes; cross-plugin reads aren't possible by default.

```python
await aurora.memory.remember("user prefers metric units")
hits = await aurora.memory.search("preferences", k=5)
```

### Encrypted Settings

Mark a setting `secret: true` in `plugin.yaml` and AURORAZ encrypts it with the OS keychain master key (Fernet / AES-128 + HMAC-SHA256). Your plugin reads plaintext; the disk store is unreadable.

```python
api_key = await aurora.settings.get("openai_key")
```

### Notifications

Send desktop toasts, progress bars, and confirmations.

```python
await aurora.notifications.show("Sync complete", level="success")
```

### Context Injection

Add a line to the live system prompt during chat — useful for plugins that maintain dynamic state the AI should always know.

```python
await aurora.context.inject("The user is currently in Focus mode.")
```

### Custom UIs

Ship an `ui/index.html` and AURORAZ renders it in a sandboxed iframe with a postMessage bridge to your Python plugin. Build a settings panel, a dashboard, anything.

---

## 🧠 Reasoning API (v0.2.0)

> **Pre-release.** The Reasoning API is functional and used in production, but the surface may evolve.

### Why

Some plugins need the AI's *reasoning ability*, not just its tool-routing. A research bot wants to actually think through a question. A code assistant wants to verify its own output. The Reasoning API exposes AURORAZ's Fractal 1:3 cognitive engine — the same reasoning the desktop uses in chat — directly to plugin code.

```python
@tool(name="research")
async def research(question: str) -> str:
    return await aurora.reasoning.ask(question, level="K3")
```

### Reasoning levels

Pick the depth that fits the cost/quality budget:

| Level | Cost | What it's for |
|---|---|---|
| **K0** | Fast, no LLM | Greetings, simple lookups, classification |
| **K1** | Single LLM pass | General questions (default) |
| **K2** | Multi-step reasoning | Deep analysis |
| **K3** | Draft + verify + refine | Highest-quality answers |

### Permissions are additive

Higher levels imply lower ones. Declaring `reasoning:k3` unlocks the entire range — no need to list each.

```yaml
permissions:
  - reasoning:k3   # implies k2, k1, k0
```

### Built-in safety

The desktop runtime enforces three guards so a misbehaving plugin can't melt the host:

| Guard | Default |
|---|---|
| **Rate limits** | K1: 60/min · K2: 30/min · K3: 10/min (per plugin) |
| **Recursion cap** | Max depth of 2 — prevents plugin → reasoning → plugin loops |
| **Concurrency lock** | At most one plugin reasoning call in flight system-wide. **User chat is unaffected** — it runs on a separate path |

Limit hits raise typed exceptions: `RateLimitError`, `RecursionLimitError`, `PluginTimeoutError`.

### Activity transparency

Every reasoning call shows up on the Plugin Page activity feed with the K-level pill, question preview, duration, and token estimate. Tools that internally use reasoning render a `🧠 used K3 reasoning (8.2s)` sub-line on their `ToolUseCard` in chat — users always know when their compute was spent on plugin reasoning.

---

## 📚 Documentation

### Tutorials (start here)

| # | Tutorial | Time |
|---|---|---|
| 1 | [Your first plugin](docs/tutorials/01-first-plugin.md) | 45 min |
| 2 | [Memory + tools](docs/tutorials/02-memory-and-tools.md) | 30 min |
| 3 | [Plugin with UI](docs/tutorials/03-plugin-with-ui.md) | 60 min |
| 4 | [Subprocess best practices](docs/tutorials/04-subprocess-best-practices.md) | 30 min |
| 5 | [Use the AURORAZ brain (Reasoning API)](docs/tutorials/05-auroraz-brain.md) | 30 min |

### Reference

- [API surface](docs/reference/api.md) — every method on `aurora.*`
- [Manifest fields](docs/reference/manifest.md) — `plugin.yaml` schema
- [Permissions](docs/reference/permissions.md) — canonical vocabulary + implication rules
- [Hooks](docs/reference/hooks.md) — lifecycle events your plugin can listen for
- [Connection (IPC + lifecycle)](docs/reference/connection.md) — how plugins reach AURORAZ
- [Architecture](docs/reference/architecture.md) — subprocess vs in-process, IPC model, sandboxing
- [Troubleshooting](docs/reference/troubleshooting.md) — common pitfalls
- [Migration (prototype → SDK)](docs/reference/migration.md) — upgrading from the pre-SDK prototype
- [Publishing](docs/reference/publishing.md) — packaging and distributing `.azpkg` plugins

### Quickstart

- [10-minute quickstart](docs/quickstart.md)

---

## 🧪 Examples

| Example | What it shows |
|---|---|
| [hello-world/](examples/hello-world/) | Minimal viable plugin — one tool, no permissions |
| [memory-bot/](examples/memory-bot/) | Tools + plugin-scoped memory |
| [with-ui/](examples/with-ui/) | Sandboxed iframe UI with postMessage bridge |
| [research-bot/](examples/research-bot/) | Reasoning API (K1 + K3) with per-level permission gating |

Every example is self-contained — clone the repo, point AURORAZ at the folder, and it runs.

---

## 🛠️ Tooling

The SDK ships a CLI for the day-to-day plugin author:

```bash
auroraz-sdk scaffold my-plugin     # generate a fresh plugin from template
auroraz-sdk lint .                 # static checks (permissions, manifest, imports)
auroraz-sdk pack                   # build a signed .azpkg for distribution
```

The linter catches deprecated permission spellings, missing manifest fields, dangling imports, and disallowed top-level side effects — fix at author time, not at install time.

---

## 🏛️ Architecture in brief

```
┌─────────────────────────────────────────────────────────┐
│                   AURORAZ desktop                       │
│                                                         │
│  ┌──────────┐    ┌────────────┐    ┌─────────────────┐  │
│  │  Chat /  │ ←→ │  Reasoning │ ←→ │   Memory store  │  │
│  │  Planner │    │   engine   │    │   (ChromaDB)    │  │
│  └──────────┘    └────────────┘    └─────────────────┘  │
│        ↑                                                │
│        │ IPC (length-prefixed JSON over local socket)   │
│        ↓                                                │
│  ┌──────────────────────────────────────────────────┐   │
│  │  IPC server  ── permission gate ── tool dispatch │   │
│  └──────────────────────────────────────────────────┘   │
│        ↑                                                │
└────────┼────────────────────────────────────────────────┘
         │
         ↓
   ┌───────────────┐    ┌───────────────┐    ┌───────────┐
   │ Plugin (proc) │    │ Plugin (proc) │ …  │  Plugin   │
   │  auroraz_sdk  │    │  auroraz_sdk  │    │   (UI)    │
   └───────────────┘    └───────────────┘    └───────────┘
```

Five design points worth knowing:

1. **Subprocess-first.** Each plugin runs in its own Python process. A plugin crash never takes down AURORAZ.
2. **IPC over a local socket.** Length-prefixed JSON, ~1ms latency, no HTTP. The plugin and the host share the machine, never the network.
3. **Server-side permission checks.** Every `aurora.*` call goes through a permission gate inside AURORAZ. Plugins can't bypass — the check is on the host side, not the client.
4. **Plugin-scoped memory.** Memory writes are tagged with the calling plugin's id; searches scope to that namespace. Cross-plugin leakage is structurally impossible.
5. **OS keychain for secrets.** Settings marked `secret: true` are encrypted with a master key stored in Windows Credential Manager / macOS Keychain / Linux Secret Service.

Full details: [docs/reference/architecture.md](docs/reference/architecture.md) and [docs/reference/connection.md](docs/reference/connection.md).

---

## 🔌 Connecting to AURORAZ

Plugins ship as a folder. To install one:

1. Drop the plugin folder into AURORAZ's plugins directory (the desktop UI's "Install from folder" does this for you).
2. AURORAZ scans `plugin.yaml`, validates the manifest, normalizes permissions, and records the plugin in the registry.
3. Click **Enable** in the Plugin Page. AURORAZ spawns the subprocess, the SDK connects over IPC (`AURORAZ_IPC_ADDR`), and your `plugin.register` payload announces tools + hooks + permissions.
4. The agent's tool catalog now includes your tools. Lifecycle hooks (`on_startup`, `on_shutdown`, etc.) start firing.

For local development you can also run `python backend/main.py` directly with `AURORAZ_IPC_ADDR` set — the plugin will connect to a running AURORAZ instance without going through registry install. See [docs/reference/connection.md](docs/reference/connection.md) for the full lifecycle.

For distribution, package a signed `.azpkg` bundle (`auroraz-sdk pack`) — see [docs/reference/publishing.md](docs/reference/publishing.md).

---

## 🗺️ Roadmap

| Status | Item |
|---|---|
| ✅ Done | Core SDK (tools, memory, settings, notifications, context, hooks) |
| ✅ Done | Subprocess sandboxing + IPC permission gate |
| ✅ Done | Custom iframe UIs with postMessage bridge |
| ✅ Done | Static linter (`auroraz-sdk lint`) |
| ✅ Done | Scaffolder (`auroraz-sdk scaffold`) |
| ✅ Done | Reasoning API (K0 / K1 / K2 / K3) |
| 🚧 In progress | `.azpkg` signed packaging + verification |
| 🚧 In progress | Marketplace / discovery surface |
| 📋 Planned | Hot reload during development |
| 📋 Planned | Streaming reasoning responses |
| 📋 Planned | Cross-plugin message bus (opt-in) |

---

## 🤝 Contributing

Issues, design feedback, and PRs are welcome at [luraselenehalo/Auroraz-SDK-Plugin](https://github.com/luraselenehalo/Auroraz-SDK-Plugin).

If you're filing a bug, a minimal reproducer plugin folder is the fastest path to a fix.
If you're proposing an API change, open an issue first so we can talk through compatibility.

---

## 📄 License

Apache-2.0 — see [LICENSE](LICENSE).

---

## 🙏 Credits

Built by [ResinCore](https://github.com/luraselenehalo) for the AURORAZ Personal AI OS.

*Local-first AI is the only AI worth building. The plugin layer is how we make it yours.*

<div align="center">

[⬆ back to top](#auroraz-sdk)

</div>
