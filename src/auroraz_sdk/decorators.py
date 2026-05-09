import functools
from typing import Callable

_tools: list = []
_hooks: dict = {}
_panels: list = []


def tool(name: str, description: str, when: str = ""):
    """Register a function as an Aurora tool."""

    def decorator(fn: Callable):
        _tools.append({
            "name": name,
            "description": description,
            "when": when,
            "handler": fn,
        })

        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            return await fn(*args, **kwargs)

        return wrapper

    return decorator


def hook(event_type: str):
    """Register a function as a hook for an Aurora event."""

    def decorator(fn: Callable):
        _hooks.setdefault(event_type, []).append(fn)

        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            return await fn(*args, **kwargs)

        return wrapper

    return decorator


def panel(slot: str = "sidebar"):
    """Register a UI panel (frontend only — marks the plugin as having UI)."""

    def decorator(fn: Callable):
        _panels.append({"slot": slot, "handler": fn})
        return fn

    return decorator
