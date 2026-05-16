"""Build-in-Public Plugin — autonomous storyteller for your engineering work.

mWP (7/11 stars): Not a webhook wrapper. An autonomous narrative engine that:
1. Notices meaningful work (PR merged, feature shipped, review passed)
2. Extracts the narrative arc — what changed and WHY it matters
3. Redacts sensitive names via anonymize.yaml rules
4. Generates channel-native posts (LinkedIn, X)
5. Captures hero screenshots via Playwright
6. Schedules via Buffer API — zero clicks, zero manual intervention
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import httpx
import yaml

from maggy.plugins.manager import HookBus, PluginManifest

logger = logging.getLogger(__name__)

BUFFER_API = "https://api.bufferapp.com/1"


def register(bus: HookBus, manifest: PluginManifest):
    """Called by PluginManager on load. Registers hook handlers."""
    plugin = BuildInPublic(manifest)
    for hook in manifest.hooks:
        event = hook["event"]
        handler_name = hook["handler"]
        handler = getattr(plugin, handler_name, None)
        if handler:
            bus.subscribe(event, manifest.id, handler)
            logger.info("build-in-public: registered %s → %s", event, handler_name)


class BuildInPublic:
    """Autonomous build-in-public storyteller."""

    def __init__(self, manifest: PluginManifest):
        self._manifest = manifest
        self._config = manifest.config
        self._anonymize = self._load_anonymize()
        self._posts_today = 0
        self._last_post_date = ""

    def _load_anonymize(self) -> dict:
        rules_path = Path(self._manifest.path) / "anonymize.yaml"
        try:
            return yaml.safe_load(rules_path.read_text())
        except Exception:
            return {"rules": {}, "strip": [], "patterns": []}

    def _redact(self, text: str) -> str:
        """Apply anonymization rules — replace sensitive terms."""
        rules = self._anonymize.get("rules", {})
        for term, replacement in rules.items():
            text = re.sub(re.escape(term), replacement, text, flags=re.IGNORECASE)

        patterns = self._anonymize.get("patterns", [])
        for p in patterns:
            text = re.sub(p["match"], p["replace"], text)

        # Strip lines containing forbidden terms
        strip_terms = self._anonymize.get("strip", [])
        lines = text.split("\n")
        lines = [
            l for l in lines
            if not any(t.lower() in l.lower() for t in strip_terms)
        ]
        return "\n".join(lines)

    def _check_rate_limit(self) -> bool:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        max_posts = self._config.get("schedule", {}).get("max_posts_per_day", 1)
        if today != self._last_post_date:
            self._posts_today = 0
            self._last_post_date = today
        if self._posts_today >= max_posts:
            logger.info("build-in-public: rate limit reached (%d/%d today)",
                        self._posts_today, max_posts)
            return False
        return True

    async def handle_pr_merged(self, payload: dict):
        """PR merged → generate and schedule post."""
        if not self._check_rate_limit():
            return

        title = payload.get("title", "a feature")
        body = payload.get("body", "")[:1000]
        branch = payload.get("branch", "")
        url = payload.get("preview_url", "")

        narrative = self._build_narrative("shipped", {
            "what": title, "context": body, "branch": branch,
        })

        post = self._format_post(narrative, url)
        await self._schedule(post, url)

    async def handle_feature_shipped(self, payload: dict):
        """Feature shipped → hero post with screenshot."""
        if not self._check_rate_limit():
            return

        feature = payload.get("feature", "a feature")
        commits = payload.get("commits", "")
        outcome = payload.get("outcome", "")

        narrative = self._build_narrative("feature", {
            "what": feature, "commits": commits, "outcome": outcome,
        })

        screenshot_path = await self._capture_screenshot(
            payload.get("url", "http://localhost:3000"),
        )

        post = self._format_post(narrative, screenshot_path)
        await self._schedule(post, screenshot_path)

    async def handle_review_passed(self, payload: dict):
        """Multi-model review unanimously approved → share the approach."""
        if not self._check_rate_limit():
            return

        plan = payload.get("plan_summary", "")
        verdict = payload.get("verdict", "")

        if verdict != "APPROVED":
            return  # Only share unanimous approvals

        narrative = self._build_narrative("architecture", {
            "what": "architected a solution",
            "context": plan[:500],
        })

        post = self._format_post(narrative)
        await self._schedule(post)

    def _build_narrative(self, event_type: str, context: dict) -> str:
        """Synthesize a narrative arc from raw event data.

        Uses DeepSeek to extract the interesting story, not just the facts.
        """
        what = context.get("what", "")
        ctx = context.get("context", "")[:500]

        prompt = (
            f"You are a technical storyteller. Turn this work into ONE tweet-length "
            f"sentence (max 280 chars) that makes developers curious. "
            f"Tone: confident, sharp, no hype sludge. "
            f"Focus on the IMPACT and the APPROACH, not the feature name.\n\n"
            f"Event: {event_type}\n"
            f"What: {what}\n"
            f"Context: {ctx}\n\n"
            f"Write ONLY the post text, nothing else."
        )

        try:
            deepseek = os.path.expanduser("~/bin/deepseek")
            result = subprocess.run(
                [deepseek, "--flash", prompt],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                narrative = result.stdout.strip()[:280]
                return self._redact(narrative)
        except Exception:
            pass

        # Fallback: simple template
        return self._redact(f"Shipped {what}: {ctx[:100]}")

    def _format_post(self, narrative: str, media_path: str = "") -> dict:
        """Format for channel — currently LinkedIn-optimized."""
        return {
            "text": narrative,
            "media": [{"url": media_path}] if media_path else [],
            "scheduled_at": self._preferred_time(),
        }

    async def _schedule(self, post: dict, media_path: str = ""):
        """Schedule via Buffer API."""
        token = os.environ.get("BUFFER_ACCESS_TOKEN", "")
        if not token:
            logger.info("build-in-public: BUFFER_ACCESS_TOKEN not set, "
                        "would have posted: %s", post["text"][:100])
            # Log to file as fallback
            self._log_post(post)
            return

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                profiles = await client.get(
                    f"{BUFFER_API}/profiles.json",
                    params={"access_token": token},
                )
                profiles.raise_for_status()
                profile_id = profiles.json()[0]["id"]

                resp = await client.post(
                    f"{BUFFER_API}/updates/create.json",
                    params={"access_token": token},
                    data={
                        "profile_ids[]": profile_id,
                        "text": post["text"],
                        "now": False,
                        "scheduled_at": post.get("scheduled_at", ""),
                    },
                )
                resp.raise_for_status()
                self._posts_today += 1
                logger.info("build-in-public: post scheduled via Buffer")
        except Exception as e:
            logger.warning("build-in-public: Buffer schedule failed: %s", e)
            self._log_post(post)

    def _log_post(self, post: dict):
        """Fallback: log post to file when Buffer unavailable."""
        log_dir = Path.home() / ".maggy" / "build-in-public"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "posts.jsonl"
        with log_file.open("a") as f:
            import json
            f.write(json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(),
                **post,
            }) + "\n")

    async def _capture_screenshot(self, url: str) -> str:
        """Capture hero screenshot via Playwright."""
        if not url:
            return ""
        screenshot_dir = Path.home() / ".maggy" / "build-in-public" / "screenshots"
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        out_path = screenshot_dir / f"hero-{ts}.png"

        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page(viewport={"width": 1200, "height": 800})
                await page.goto(url, wait_until="networkidle", timeout=15000)
                await page.screenshot(path=str(out_path), full_page=False)
                await browser.close()
                return str(out_path)
        except ImportError:
            logger.debug("build-in-public: playwright not installed")
        except Exception as e:
            logger.debug("build-in-public: screenshot failed: %s", e)

        return ""

    def _preferred_time(self) -> str:
        """Return ISO timestamp for preferred posting time."""
        tz = timezone.utc
        now = datetime.now(tz)
        preferred = self._config.get("schedule", {}).get("preferred_time", "09:00")
        hour, minute = map(int, preferred.replace(" UTC", "").split(":"))
        scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if scheduled < now:
            from datetime import timedelta
            scheduled += timedelta(days=1)
        return scheduled.isoformat()
