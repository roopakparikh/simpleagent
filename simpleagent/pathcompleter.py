"""Shim module for backward compatibility after moving into simpleagent.ui package."""

from .ui.pathcompleter import (
    _resolve_abs_path,
    get_path_completed_text,
)

__all__ = [
    "_resolve_abs_path",
    "get_path_completed_text",
]
