"""Autonomous Engagement System — watch topics, reply to relevant conversations.

Per-project cadence that monitors important topics and accounts,
instantly engages with relevant posts, and builds presence.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


class SmartEngager:
    """Watches topics and accounts, engages autonomously."""

    def __init__(self, project: str = "maggy", config: dict = None):
        self._project = project
        self._config = config or {}
        self._state = self._load_state()
        self._topics = self._load_topics()

    def _load_state(self) -> dict:
        path = Path.home() / ".maggy" / "build-in-public" / f"engage-{self._project}.json"
        try:
            return json.loads(path.read_text())
        except Exception:
            return {"last_scan": "", "replies": 0, "topics_seen": []}

    def _save_state(self):
        path = Path.home() / ".maggy" / "build-in-public" / f"engage-{self._project}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._state, indent=2))

    def _load_topics(self) -> dict:
        """Load per-project watch topics."""
        path = Path(__file__).parent / f"topics-{self._project}.yaml"
        if not path.exists():
            path = Path(__file__).parent / "topics.yaml"
        try:
            import yaml
            return yaml.safe_load(path.read_text())
        except Exception:
            return {"watch": [], "engage_on": [], "never_engage": []}

    def should_engage(self, topic: str, content: str) -> bool:
        """Decide whether to engage with a topic/conversation."""
        # Never engage on excluded topics
        never = self._topics.get("never_engage", [])
        if any(n in topic.lower() for n in never):
            return False

        # Must match a watch topic
        watch = self._topics.get("watch", [])
        engage_on = self._topics.get("engage_on", [])
        if not any(w in topic.lower() for w in watch + engage_on):
            return False

        # Rate limit: max 2 engagements per day
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self._state.get("last_engage_date") == today:
            if self._state.get("engagements_today", 0) >= 2:
                return False

        # Don't reply to own posts
        my_handles = self._topics.get("my_handles", [])
        if any(h.lower() in content.lower() for h in my_handles):
            return False

        return True

    def generate_reply(self, topic: str, content: str) -> str:
        """Generate an intelligent reply via DeepSeek."""
        prompt = (
            f"You are engaging on social media as a technical builder. "
            f"Someone posted about: {topic}. "
            f"Their post: {content[:300]}. "
            f"Write a genuine, valuable reply (max 280 chars). "
            f"No hype. No 'great post!' Add insight or ask a smart question. "
            f"Write ONLY the reply text."
        )
        try:
            r = subprocess.run(
                [os.path.expanduser("~/bin/deepseek"), "--flash", prompt],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()[:280]
        except Exception:
            pass
        return ""

    def record_engagement(self, topic: str, reply: str):
        """Log the engagement."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self._state.get("last_engage_date") != today:
            self._state["last_engage_date"] = today
            self._state["engagements_today"] = 0
        self._state["engagements_today"] = self._state.get("engagements_today", 0) + 1
        self._state["replies"] = self._state.get("replies", 0) + 1
        self._state["topics_seen"].append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "topic": topic, "reply": reply[:100],
        })
        self._state["topics_seen"] = self._state["topics_seen"][-50:]
        self._save_state()

    def status(self) -> dict:
        return {
            "project": self._project,
            "replies_total": self._state.get("replies", 0),
            "engagements_today": self._state.get("engagements_today", 0),
            "last_scan": self._state.get("last_scan", ""),
        }
