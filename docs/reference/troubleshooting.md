# Troubleshooting

Common errors plugin authors hit, with fixes.

## Discovery & Loading

### "Plugin not discovered" — folder is in `backend/plugins/` but doesn't appear

**Cause**: Folder name doesn't match `plugin.yaml`'s `id`, OR the
folder name starts with `_` / `.`, OR the manifest is missing.

**Fix**: Folder name should match `id`. Don't use `_` prefix. Make
sure `plugin.yaml` exists and parses.

```bash
# Quick diagnostic
ls backend/plugins/<your-folder>/plugin.yaml
grep '^id:' backend/plugins/<your-folder>/plugin.yaml
```

### "Plugin discovered but skipped" — boot logs say `not in enabled_ids`

**Cause**: Plugin is installed but not enabled in `plugins.json`.

**Fix**:

```bash
curl -X POST http://localhost:8741/api/plugins/<id>/install
curl -X POST http://localhost:8741/api/plugins/<id>/enable
```

Or click Install + Enable in the marketplace UI.

### "FAILED to load: incompatible: requires AURORAZ >= X.Y.Z"

**Cause**: Your manifest's `min_auroraz_version` is higher than the
running AURORAZ version.

**Fix**: Either lower `min_auroraz_version` in `plugin.yaml`, or
upgrade AURORAZ. Check current version with
`grep __version__ backend/auroraz/__init__.py`.

### "ImportError: cannot import name 'auroraz_sdk'" at boot

**Cause**: AURORAZ tried to spawn the subprocess but `auroraz-sdk`
isn't installed in its venv.

**Fix**:

```bash
backend/.venv312/Scripts/pip install auroraz-sdk
```

For development, point at your local source:

```bash
backend/.venv312/Scripts/pip install -e /path/to/dist/auroraz-sdk
```

### "could not resolve sdk_entry"

**Cause**: AURORAZ can't find your subprocess entry point.

**Fix**: Either:

1. Declare `sdk_entry: <relative-path>` in `plugin.yaml`, or
2. Place `main.py` at plugin root, or
3. Place `backend/main.py` (Stage 4 scaffolder convention)

## IPC & Tool Calls

### "PermissionDeniedError: <permission>"

**Cause**: Tool tried to call an aurora API but the corresponding
permission isn't declared in the manifest.

**Fix**: Add to `permissions:` list. Common mappings:

| API call | Permission |
|---|---|
| `aurora.memory.remember` / `store` | `memory:write` |
| `aurora.memory.search` / `get` | `memory:read` |
| `aurora.notify` | `notifications:show` |
| `aurora.inject` | `context:inject` |
| `aurora.context.get_*` | `context:read` |
| `httpx.get(...)` | `network` or `network:<host>` |

The linter (`auroraz-sdk lint .`) flags this with rule `API001`.

### "RuntimeError: aurora not initialized — call plugin.run() first"

**Cause**: Code tried to use `aurora.*` at module load time, before
`plugin.run()` has connected to AURORAZ.

**Fix**: Move the `aurora.*` call inside a tool handler or hook.
Module-level code runs at import, before IPC is up.

```python
# WRONG — at module scope
status = aurora.context.get_emotion()

# RIGHT — inside a tool
@tool(name="...")
async def my_tool():
    status = await aurora.context.get_emotion()
    ...
```

### "Tool registered but Luna doesn't pick it up"

**Cause**: `description` and/or `when` are too vague, or the chat
agent prefers a different tool.

**Fix**: Make `when` specific. Use trigger words the user is likely
to say:

```python
# WEAK
@tool(name="my_tool", description="Does something", when="when needed")

# STRONG
@tool(
    name="memory_bot_remember",
    description="Store a fact in AURORAZ's long-term memory.",
    when="user asks to remember, save, or note something for later",
)
```

Test by asking Luna directly to use the tool: "use my_tool to ..."

### "Tool ran but the result is empty / weird"

**Cause**: The tool handler returned None or a non-string.

**Fix**: Always return a string:

```python
# WRONG
return {"data": [...]}     # dict gets repr()'d, looks bad in chat

# RIGHT
import json
return json.dumps({"data": [...]}, ensure_ascii=False)
```

## Settings

### Settings field shows `<saved>` but my plugin gets None

**Cause**: The plugin reads `Plugin.config[key]`, but `<saved>` is
the API redaction sentinel — never the actual stored value. Plugin
config is populated from the decrypted JSON at spawn time.

**Fix**: Make sure your subprocess plugin reads
`plugin.config["api_token"]` directly. AURORAZ decrypts before
passing the dict via env var.

If `plugin.config["api_token"]` is `None`:

1. Did you save a value via the Plugin Page?
2. Did you restart the plugin after saving? (Settings hot-reload
   isn't implemented yet.)
3. Is the field name in the manifest schema spelled the same?

### "DecryptError: Failed to decrypt setting"

**Cause**: The master key has changed or the encrypted blob is
corrupt.

**Fix**: Re-enter the secret value via the settings UI. The new
value gets encrypted with the current key.

If this happens repeatedly: check
`<DATA_PATH>/.master_key` (Linux fallback) or your OS keychain
entry — it may have been overwritten.

## UI

### Iframe loads blank

**Cause**: 404 on the entry HTML, or HTML loaded but no content.

**Fix**:

1. Check `frontend.ui_entry` matches the actual filename:

   ```bash
   ls backend/plugins/<id>/ui/
   ```

2. Hit the URL directly in a browser:

   ```
   http://localhost:8741/api/plugins/<id>/ui/<ui_entry>
   ```

   Should return your HTML. If 404, check the filename. If 403, your
   `ui_entry` has a `..` or absolute path.

3. Open Chrome DevTools → Console while the iframe is loaded;
   any JS errors there?

### Iframe shows "iframe · /api/plugins/<id>/ui/<entry> · error"

**Cause**: The fallback rendered because `iframe.onError` fired.

**Fix**: Same as above — check the URL directly + DevTools Console.

### Toast not appearing when iframe sends `plugin/notify`

**Cause**: Origin check failed in AURORAZ.

**Fix**: AURORAZ accepts `plugin/notify` from same-origin (production)
or `http://localhost:5173` / `http://127.0.0.1:5173` (dev). If you're
on a non-standard port, add it to AURORAZ's accepted origins (see
`utils/pluginPostMessage.js` in the frontend).

For debugging, log the iframe's outgoing origin:

```js
console.log("posting from:", window.location.origin);
window.parent.postMessage({...}, '*');
```

### "Refused to display in a frame because of CSP"

**Cause**: AURORAZ's CSP blocks framing of arbitrary URLs.

**Fix**: Plugin UI must be served from the AURORAZ static-file
endpoint (`/api/plugins/<id>/ui/...`). Don't embed external URLs in
your `ui_entry`.

## Permissions Vocabulary

### "Permission 'memory_read' is a deprecated alias"

**Cause**: Manifest uses the old underscore vocabulary.

**Fix**: Update to canonical:

| Old | New |
|---|---|
| `memory_read` | `memory:read` |
| `memory_write` | `memory:write` |
| `working_memory` | `working_memory:read` |
| `context_injection` | `context:inject` |
| `process_scan` | `process:scan` |
| `notifications` | `notifications:show` |
| `prompt:inject` | `context:inject` |

Run the migration script:

```bash
backend/.venv312/Scripts/python.exe backend/scripts/migrate_plugin_perms.py <id> --apply
```

It rewrites the manifest in place with a `.bak` backup.

## Build & Publish

### `auroraz-sdk lint .` says "PERM001: not recognized"

**Cause**: Permission name typo (e.g. `memry:read`).

**Fix**: Check spelling against [permissions.md](permissions.md).
The linter doesn't auto-correct; you have to edit `plugin.yaml`.

### Smoke install fails after rebuilding the SDK

**Cause**: A new cross-import slipped in (you added `from auroraz.X` to
a public module).

**Fix**: Audit `tools/build_sdk.py:IMPORT_REWRITES`. Add the rewrite
or move the dependency to a `_stub_*.py` module.

### `pip install auroraz-sdk` says "no matching distribution"

**Cause**: PyPI propagation delay (right after upload).

**Fix**: Wait 1-2 minutes; the CDN catches up.

## Diagnostic commands

```bash
# What does AURORAZ see?
curl http://localhost:8741/api/plugins/<id>

# Run the linter
auroraz-sdk lint <plugin-folder>
# or
backend/.venv312/Scripts/python.exe -c "
from pathlib import Path
from auroraz_sdk.lint import lint_plugin
for d in lint_plugin(Path('.')):
    print(f'{d.severity:5} {d.code} {d.message}')
"

# What permissions did AURORAZ canonicalize?
curl http://localhost:8741/api/plugins/<id> | python -m json.tool | grep -A 30 permissions_raw

# Tail the plugin log
tail -f <DATA_PATH>/logs/plugin-<id>.log

# Tail AURORAZ's main log
tail -f <DATA_PATH>/logs/auroraz.log
```

## Still stuck?

- Read the boot logs end-to-end (the IPC handshake messages are
  informative)
- Open DevTools console for UI issues
- Check the Plugin Page activity feed in AURORAZ desktop
- Compare your code against the working examples in `examples/`
