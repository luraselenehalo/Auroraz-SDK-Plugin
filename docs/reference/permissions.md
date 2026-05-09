# Permissions Reference

AURORAZ uses a colon-namespaced permission vocabulary: `scope:action`
(plus an optional `:qualifier` for some scopes). Permissions are
declared in `plugin.yaml` and enforced at runtime by AURORAZ when a
plugin tries to use a gated API.

## Canonical permissions

| Permission | Description |
|---|---|
| `memory:read` | Read AURORAZ's long-term memory |
| `memory:write` | Store new long-term memories |
| `context:read` | Read current emotion, intent, active window |
| `context:inject` | Add lines to the system prompt during chat |
| `working_memory:read` | Read the active conversation context |
| `working_memory:write` | Modify the active conversation context |
| `notifications:show` | Show desktop toasts |
| `network` | Make HTTP requests to any host |
| `network:<host>` | Make HTTP requests to a specific host (e.g. `network:api.spotify.com`) |
| `process:scan` | Detect running OS processes (game detection, etc.) |
| `anthropic:proxy` | Call the Anthropic API via AURORAZ-managed token |
| `reasoning:k0` | Invoke AURORAZ's reasoning engine at K0 (fast, no LLM) |
| `reasoning:k1` | Invoke AURORAZ's reasoning engine at K1 (general questions) |
| `reasoning:k2` | Invoke AURORAZ's reasoning engine at K2 (deep analysis) |
| `reasoning:k3` | Invoke AURORAZ's reasoning engine at K3 (verify + refine) |

## Network host scoping

`network` (no qualifier) grants any-host access — wide. Prefer
host-scoped permissions when you only talk to specific APIs:

```yaml
permissions:
  - network:api.spotify.com
  - network:accounts.spotify.com
```

The host pattern is exact match — it's not a prefix or wildcard.

## Implication rules

Some permissions imply others:

- `memory:write` implies `memory:read`
- `working_memory:write` implies `working_memory:read`
- `network` implies any `network:<host>`
- `reasoning:k3` implies `reasoning:k2`, `:k1`, `:k0`
- `reasoning:k2` implies `reasoning:k1`, `:k0`
- `reasoning:k1` implies `reasoning:k0`

So a plugin that declares `memory:write` can call read methods without
declaring `memory:read` separately.

## Deprecated alias forms

The vocabulary was unified in Stage 3. These older spellings still
work but produce a deprecation warning at load:

| Old | Canonical |
|---|---|
| `memory_read` | `memory:read` |
| `memory_write` | `memory:write` |
| `working_memory` | `working_memory:read` |
| `context_injection` | `context:inject` |
| `process_scan` | `process:scan` |
| `notifications` | `notifications:show` |
| `prompt:inject` | `context:inject` |
| `anthropic_sdk` | `anthropic:proxy` |
| `memory.read` (dot) | `memory:read` |
| `memory.write` (dot) | `memory:write` |
| `chat.inject` | `context:inject` |
| `network.outbound` | `network` |

The linter (Stage 4) flags deprecated aliases at `info` severity. Run
`auroraz-sdk lint .` to surface them. The migration script in
AURORAZ's source tree (`backend/scripts/migrate_plugin_perms.py`)
rewrites `plugin.yaml` in-place with `.bak` backup if you want to
upgrade.

## Authoring tips

1. **Declare only what you need.** The Plugin Page shows your
   permission list to the user with descriptions; minimize for trust.
2. **Lint before shipping.** `auroraz-sdk lint .` catches
   declared-but-unused (`PERM003`) and used-but-undeclared (`API001`)
   permissions.
3. **Strict mode for CI.** Set `AURORAZ_STRICT_PERM_VOCAB=1` to fail
   parse on any deprecated alias — useful in your test suite to keep
   manifests forward-clean.
