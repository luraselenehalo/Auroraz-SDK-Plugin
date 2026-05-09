# Publishing your plugin

How to share a plugin once it lints clean and runs locally.

## Today (Stage 6a): manual install

The marketplace remote isn't live yet — plugins are installed by
copying the folder into AURORAZ's `backend/plugins/<id>/`. Steps:

1. **Lint locally**

   ```bash
   auroraz-sdk lint .
   ```

   Get to 0 errors. Warnings are author judgment calls.

2. **Pack a `.azpkg` (optional)**

   The SDK CLI builds a signed package:

   ```bash
   auroraz-sdk pack .            # uses an ephemeral test key
   auroraz-sdk pack . --key ~/my-author-key.pem   # production
   ```

   Output: `<plugin-id>-<version>.azpkg` in the current dir. Ed25519
   signed; AURORAZ verifies on install.

3. **Install into AURORAZ desktop**

   ```bash
   curl -X POST http://localhost:8741/api/plugins/install-azpkg \
     -H "Content-Type: application/json" \
     -d '{"azpkg_path": "/abs/path/to/my-plugin-0.1.0.azpkg"}'
   ```

   Or, for development, just copy the folder:

   ```bash
   cp -r my-plugin/ <path-to-AURORAZ>/backend/plugins/
   ```

   The marketplace will reload and show your plugin.

## Coming in Stage 6b: marketplace remote

Stage 6b will add a hosted plugin marketplace where authors upload
`.azpkg` files and AURORAZ users browse + install with one click. The
hosting server, web UI, and AURORAZ desktop integration are all
covered there. Stage 5's signing primitives are the foundation —
nothing about your plugin or your signing key changes between Stage 6a
and 6b.

For now: manual install + folder copy is the path. Plenty of plugin
authors ship their first version this way.

## Versioning

Follow semver. Bump:

- **patch** (0.1.0 → 0.1.1) for bugfixes
- **minor** (0.1.0 → 0.2.0) for new tools / new permissions
- **major** (0.1.0 → 1.0.0) for breaking changes (renamed tool, removed
  API surface)

Update `version` in `plugin.yaml` AND the `Plugin(version="...")`
constructor call in `main.py` — they should always match.

## Compatibility

`min_auroraz_version` in your manifest gates which AURORAZ versions
will load your plugin. Set it to the lowest version you've tested
against:

```yaml
min_auroraz_version: "0.1.0"
```

AURORAZ refuses to enable a plugin whose minimum exceeds the running
version, surfacing a clear "requires AURORAZ X.Y.Z" message in the UI.

## Signing keys

For Stage 6a the model is **self-signed** — your `.azpkg` carries its
own public key, AURORAZ verifies the signature against that bundled
key. There's no central key authority yet (Stage 6b may introduce one).

Practical implications:
- Generate a key once, reuse for all your plugin releases
- Same author keyfingerprint across releases helps users trust updates
- Lose the key → publish from a new identity (ok for hobby plugins,
  not great for established ones)

The CLI generates an ephemeral key per-pack if `--key` isn't given.
That works for dev, but means every release ships a different identity.
