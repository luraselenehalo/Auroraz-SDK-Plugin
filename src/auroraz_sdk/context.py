from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class HookContext:
    """Passed to every @hook function."""

    text: str = ""

    emotion: str = ""
    intent: str = ""

    window: dict = field(default_factory=dict)

    session_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)

    plugin_store: dict = field(default_factory=dict)

    _plugin_id: str = ""
    _event_type: str = ""
