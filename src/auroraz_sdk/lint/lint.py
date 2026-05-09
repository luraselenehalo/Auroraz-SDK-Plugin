"""Top-level entry point for the plugin linter."""

from __future__ import annotations

from pathlib import Path

from auroraz_sdk.lint.diagnostics import Diagnostic
from auroraz_sdk.lint.rules import ALL_RULES, CodeIndex
from auroraz_sdk.manifest import parse_manifest


def lint_plugin(plugin_dir: Path) -> list[Diagnostic]:
    """Run every registered rule against ``plugin_dir`` and return diagnostics.

    Behavior:
      * Missing folder → single error.
      * Missing/unparseable manifest → single error (no rules can run).
      * Per-file Python parse errors are surfaced as ``SYN001`` and the
        file is skipped (other files still get scanned).
      * A crashing rule produces a ``LINT999`` diagnostic but never aborts
        the whole run.
    """
    if not plugin_dir.is_dir():
        return [Diagnostic(
            severity="error", code="ENV001",
            message=f"Plugin directory not found: {plugin_dir}",
        )]

    manifest_path = plugin_dir / "plugin.yaml"
    if not manifest_path.exists():
        manifest_path = plugin_dir / "plugin.json"
    if not manifest_path.exists():
        return [Diagnostic(
            severity="error", code="MAN000",
            message="No plugin.yaml or plugin.json found in plugin directory",
            file=plugin_dir.name,
        )]

    try:
        manifest = parse_manifest(plugin_dir)
    except Exception as e:
        return [Diagnostic(
            severity="error", code="MAN999",
            message=f"Failed to parse manifest: {e}",
            file=manifest_path.name,
        )]

    code_index = CodeIndex.build(plugin_dir)

    diagnostics: list[Diagnostic] = list(code_index.parse_errors)
    for rule_id, rule_fn in ALL_RULES:
        try:
            diagnostics.extend(rule_fn(manifest, code_index))
        except Exception as e:
            diagnostics.append(Diagnostic(
                severity="error", code="LINT999",
                message=f"Rule {rule_id} crashed: {e}",
            ))

    return diagnostics
