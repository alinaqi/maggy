"""Mnemos thresholds, weights, and enumerations."""

from __future__ import annotations

# -- Fatigue thresholds --
FATIGUE_WEIGHT_TOKEN = 0.40
FATIGUE_WEIGHT_SCOPE_SCATTER = 0.25
FATIGUE_WEIGHT_REREAD_RATIO = 0.20
FATIGUE_WEIGHT_ERROR_DENSITY = 0.15
CHECKPOINT_THRESHOLD = 0.60
CHECKPOINT_COOLDOWN_S = 120

# -- Transcript size calibration --
TRANSCRIPT_FULL_BYTES = 800_000  # ~200k tokens
COMPACT_UTILIZATION = 0.83       # PreCompact fires ~83%

# -- Fatigue states --
STATE_FLOW = "FLOW"              # 0.00 - 0.40
STATE_COMPRESS = "COMPRESS"      # 0.40 - 0.60
STATE_PRE_SLEEP = "PRE_SLEEP"    # 0.60 - 0.75
STATE_REM = "REM"                # 0.75 - 0.90
STATE_EMERGENCY = "EMERGENCY"    # 0.90+

STATE_BOUNDARIES: list[tuple[float, str]] = [
    (0.40, STATE_FLOW),
    (0.60, STATE_COMPRESS),
    (0.75, STATE_PRE_SLEEP),
    (0.90, STATE_REM),
    (float("inf"), STATE_EMERGENCY),
]

# -- Fatigue routing thresholds --
FATIGUE_ROUTING_ESCALATE = 0.60   # PRE_SLEEP: skip cheap tiers
FATIGUE_ROUTING_PREMIUM = 0.75    # REM: force premium model
FATIGUE_PARALLEL_BLOCK = 0.50     # Disable parallel exec

# -- Node types (all tiers) --
NODE_TYPES = frozenset({
    "GoalNode", "ConstraintNode", "DecisionNode",
    "CodeRefNode", "FactNode", "ErrorNode",
    "CheckpointNode", "HandoffNode",
    "ContextNode", "ResultNode", "WorkingNode", "SkillNode",
})

# -- Node statuses --
STATUS_ACTIVE = "ACTIVE"
STATUS_COMPRESSED = "COMPRESSED"
STATUS_EVICTED = "EVICTED"
STATUS_CRYSTALLIZED = "CRYSTALLIZED"

# -- Link types --
LINK_RELATED = "RELATED"
LINK_DEPENDS_ON = "DEPENDS_ON"
LINK_CAUSED_BY = "CAUSED_BY"

# -- Activation weight coefficients --
WEIGHT_RECENCY = 0.50
WEIGHT_FREQUENCY = 0.30
WEIGHT_CENTRALITY = 0.20

# -- Consolidation thresholds --
MICRO_CONSOLIDATION_MIN = 0.40
MICRO_CONSOLIDATION_MAX = 0.60
EVICTION_WEIGHT_THRESHOLD = 0.20
COMPRESS_BATCH_SIZE = 10
REM_TARGET_RATIO = 0.50
REM_TRIGGER_THRESHOLD = 0.75

# -- Skill fingerprint thresholds --
SKILL_PROMOTION_COUNT = 3
SKILL_REINFORCE_BOOST = 0.05
SKILL_CONFIDENCE_CAP = 0.95
FP_STRONG_THRESHOLD = 0.95
FP_STANDARD_THRESHOLD = 0.80
FP_WEAK_THRESHOLD = 0.60

# -- Storage paths --
DB_FILENAME = "mnemo.db"
FATIGUE_FILENAME = "fatigue.json"
CHECKPOINT_LATEST = "checkpoint-latest.json"
JUST_COMPACTED_MARKER = "just-compacted"
SIGNALS_FILENAME = "signals.jsonl"
ORCHESTRATOR_SIGNALS = "orchestrator-signals.jsonl"
MNEMOS_DIR = ".mnemos"
