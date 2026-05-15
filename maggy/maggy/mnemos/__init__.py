"""Mnemos — Task-scoped memory lifecycle system."""

__version__ = "0.1.0"

# Backward-compatible v0 stub APIs
from maggy.mnemos._compat import FatigueTracker, SignalLog

__all__ = ["FatigueTracker", "SignalLog"]
