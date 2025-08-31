"""Shim module to maintain backward compatibility.

Re-exports SimpleAgentUI from the new package path simpleagent.ui.ui
so existing imports `from simpleagent.ui import SimpleAgentUI` continue to work.
"""

from .ui import SimpleAgentUI  # type: ignore F401

__all__ = ["SimpleAgentUI"]
