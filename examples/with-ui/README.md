# with-ui

Plugin shipping a sandboxed iframe UI alongside its tool. Demonstrates
the postMessage protocol between AURORAZ desktop and a plugin's iframe.

## Files

- `plugin.yaml` — manifest with `frontend.ui_entry: ui/index.html`
- `main.py` — Plugin entry, registers `with_ui_toast`
- `ui/index.html` — iframe entry
- `ui/app.css` — styles
- `ui/app.js` — postMessage consumer

## Permissions

- `notifications:show` — to call `aurora.notify` from the tool

## postMessage protocol

After the iframe loads, AURORAZ sends:
- `{type: 'auroraz/init', plugin_id, settings, permissions}` once
- `{type: 'auroraz/settings-changed', settings}` whenever settings update

The plugin can post back:
- `{type: 'plugin/ready'}` — signal readiness
- `{type: 'plugin/notify', message, level}` — show a toast in AURORAZ
- `{type: 'plugin/request-settings'}` — re-request the current settings

Origin is checked on both sides. In dev (Vite + FastAPI on different ports)
the iframe is cross-origin — the example whitelists both origins.
