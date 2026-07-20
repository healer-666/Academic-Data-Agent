"""FastAPI web workspace exports."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = ["create_app"]

_EXPORT_MAP = {
    "create_app": ("data_analysis_agent.web.api", "create_app"),
}


def __getattr__(name: str) -> Any:
    if name not in _EXPORT_MAP:
        raise AttributeError(name)
    module_name, attr_name = _EXPORT_MAP[name]
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
