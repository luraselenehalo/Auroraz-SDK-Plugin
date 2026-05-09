# hello-world

The simplest possible auroraz-sdk plugin. Registers one tool, no
permissions, no AURORAZ APIs.

## Files

- `plugin.yaml` — manifest
- `main.py` — entry point with one tool

## Try it

```bash
pip install auroraz-sdk
auroraz-sdk lint .            # should report 0 errors
```

Drop the folder into AURORAZ's `backend/plugins/hello-world/` and enable
via the marketplace. Luna gains a `hello_world_greet` tool you can ask
for in chat.
