"""Background lease heartbeat (RFC §2.6.3): on failure, interrupt the worker at once.

The thread extends the lease every `interval_s`. The first failure (lease lost, stale fence,
or awg unreachable) records why and touches the attempt's interrupt file, which makes the
supervisor kill the worker's process group; the runner then skips every side effect.
"""

from __future__ import annotations

import threading
from pathlib import Path

from maggy.runner.awg_client import AwgClient
from maggy.runner.awg_types import Claim


class Heartbeat:
    def __init__(self, awg: AwgClient, claim: Claim, plan: tuple[float, Path]) -> None:
        self.awg, self.claim = awg, claim
        self.interval_s, self.interrupt_file = plan
        self.lost: str | None = None
        self._done = threading.Event()
        self._thread = threading.Thread(target=self._loop, name=f"heartbeat-{claim.ref}",
                                        daemon=True)

    def __enter__(self) -> Heartbeat:
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._done.set()
        self._thread.join()

    def _loop(self) -> None:
        while not self._done.wait(self.interval_s):
            try:
                self.awg.heartbeat(self.claim)
            except Exception as exc:  # any failure means we may no longer hold the lease
                self.lost = f"heartbeat failed: {type(exc).__name__}: {exc}"[:300]
                self.interrupt_file.parent.mkdir(parents=True, exist_ok=True)
                self.interrupt_file.write_text(self.lost + "\n")
                return
