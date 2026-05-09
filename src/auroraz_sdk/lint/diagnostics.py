"""Diagnostic dataclass shared by every lint rule.

The shape mirrors LSP-style diagnostics so a future IDE integration can
adopt it without translation.
"""

from __future__ import annotations

# Aliased to avoid the name shadow: the dataclass below has an attribute
# called `field` (manifest field reference like "permissions[2]"), which
# would clobber `dataclasses.field` during class-body evaluation and
# produce a confusing `TypeError: 'NoneType' object is not callable`.
from dataclasses import dataclass, field as _dc_field
from typing import Any, Literal

Severity = Literal["error", "warn", "info"]


@dataclass
class Diagnostic:
    severity: Severity
    code: str                              # stable id, e.g. "PERM001"
    message: str
    file: str | None = None                # plugin-relative path
    line: int | None = None                # 1-indexed
    column: int | None = None
    field: str | None = None               # manifest field, e.g. "permissions[2]"
    suggestion: str | None = None
    extras: dict[str, Any] = _dc_field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "field": self.field,
            "suggestion": self.suggestion,
            "extras": self.extras,
        }
