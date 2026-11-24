"""Mnemos fatigue routing thresholds used by the executor and model router.

The full Mnemos implementation lives in scripts/mnemos (`python3 -m mnemos`).
"""

from __future__ import annotations

FATIGUE_ROUTING_ESCALATE = 0.60   # PRE_SLEEP: skip cheap tiers
FATIGUE_ROUTING_PREMIUM = 0.75    # REM: force premium model
FATIGUE_PARALLEL_BLOCK = 0.50     # Disable parallel exec
