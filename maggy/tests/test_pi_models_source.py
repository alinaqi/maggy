"""Guard: the Pi model set has exactly one source of truth."""

from __future__ import annotations

from maggy.api import routes_chat
from maggy.pipeline import backend_claude, backend_pi


def test_backend_claude_reuses_backend_pi_models():
    assert backend_claude._PI_MODELS is backend_pi._PI_MODELS


def test_backends_partition_models_from_one_list():
    claude = backend_claude.ClaudeBackend(chat=None)
    pi = backend_pi.PiBackend(pi=None)
    for model in backend_pi._PI_MODELS | {"claude-opus", "sonnet"}:
        assert claude.handles(model) != pi.handles(model)
        assert routes_chat._is_claude_model(model) == claude.handles(model)
