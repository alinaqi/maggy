"""Execution contracts — enforce agentic response quality."""

from __future__ import annotations

from maggy.pipeline.steering import needs_steering


class ExecutionContract:
    def __init__(self, mode: str = "strict-agentic") -> None:
        self.mode = mode

    def validate_response(self, response: str) -> bool:
        if self.mode != "strict-agentic":
            return True
        if not response.strip():
            return True
        return not needs_steering(response)
