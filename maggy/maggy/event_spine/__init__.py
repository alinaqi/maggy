"""Event Spine — canonical event flow for end-to-end tracing."""

from .emitter import EventEmitter
from .header import EventHeader

__all__ = ["EventEmitter", "EventHeader"]
