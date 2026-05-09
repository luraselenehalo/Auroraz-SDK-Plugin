"""Plugin linter — Stage 4 developer experience.

Pure-Python AST analysis (stdlib only). Flags manifest issues, deprecated
permission aliases, undeclared/unused permissions, missing aurora.* gates,
and tool name collisions.

Public surface::

    from auroraz_sdk.lint import lint_plugin, Diagnostic
"""

from auroraz_sdk.lint.diagnostics import Diagnostic, Severity
from auroraz_sdk.lint.lint import lint_plugin

__all__ = ["Diagnostic", "Severity", "lint_plugin"]
