"""Autonomous Engagement System — watch topics, monitor accounts, engage.

Per-project cadence that monitors important topics and accounts,
instantly engages with relevant posts, and builds presence.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


class SmartEngager:
    """Watches topics and accounts, engages autonomously."""

    def __init__(self, project: str = "maggy", config: dict = None):
        self._project = project
        self._config = config or {}
        self._state = self._load_state()
        self._topics = self._load_topics()
        self._engaged_posts = self._load_engaged_posts()
        self._social = None  # Lazy SocialMonitor

    def _load_state(self) -> dict:
        path = Path.home() / ".maggy" / "build-in-public" / f"engage-{self._project}.json"
        try:
            return json.loads(path.read_text())
        except Exception:
            return {"last_scan": "", "replies": 0, "topics_seen": [],
                    "accounts_monitored": {}, "last_monitor_scan": ""}

    def _save_state(self):
        path = Path.home() / ".maggy" / "build-in-public" / f"engage-{self._project}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._state, indent=2))

    def _load_engaged_posts(self) -> set:
        """Load set of already-engaged post IDs to prevent duplicates."""
        path = Path.home() / ".maggy" / "build-in-public" / f"engaged-{self._project}.json"
        try:
            return set(json.loads(path.read_text()))
        except Exception:
            return set()

    def _save_engaged_posts(self):
        path = Path.home() / ".maggy" / "build-in-public" / f"engaged-{self._project}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(list(self._engaged_posts)[-500:]))

    def _load_topics(self) -> dict:
        """Load per-project watch topics."""
        path = Path(__file__).parent / f"topics-{self._project}.yaml"
        if not path.exists():
            path = Path(__file__).parent / "topics.yaml"
        try:
            import yaml
            return yaml.safe_load(path.read_text())
        except Exception:
            return {"watch": [], "engage_on": [], "never_engage": [],
                    "monitor_accounts": []}

    def get_monitored_accounts(self) -> list:
        """Get list of accounts to monitor with their engagement rules."""
        return self._topics.get("monitor_accounts", [])

    def should_monitor_now(self, account: dict) -> bool:
        """Check if it's time to fetch this account's posts."""
        handle = account.get("handle", "")
        interval = account.get("interval_minutes",
            self._topics.get("monitor_config", {}).get("interval_minutes", 30))

        last_check = self._state.get("accounts_monitored", {}).get(handle, "")
        if not last_check:
            return True

        since = (datetime.now(timezone.utc) -
                 datetime.fromisoformat(last_check)).total_seconds()
        return since >= interval * 60

    def _rate_limit_ok(self) -> bool:
        """Check global rate limit for API calls."""
        cfg = self._topics.get("monitor_config", {})
        limit = cfg.get("rate_limit_per_hour", 200)
        hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        recent = [t for t in self._state.get("api_calls", []) if t > hour_ago]
        return len(recent) < limit

    def _record_api_call(self):
        calls = self._state.get("api_calls", [])
        calls.append(datetime.now(timezone.utc).isoformat())
        self._state["api_calls"] = calls[-500:]
        self._save_state()

    def check_account_posts(self, account: dict) -> list:
        """Fetch recent posts from a monitored account. Returns [{id, text, topic}]."""
        handle = account.get("handle", "")
        platform = account.get("platform", "x")
        max_items = account.get("max_items_per_fetch", 10)

        # Mark as checked regardless of API success
        if "accounts_monitored" not in self._state:
            self._state["accounts_monitored"] = {}
        self._state["accounts_monitored"][handle] = datetime.now(timezone.utc).isoformat()
        self._save_state()

        if not self._rate_limit_ok():
            logger.debug("SmartEngager: rate limit reached, skipping %s", handle)
            return []

        self._record_api_call()

        # Fetch posts (platform-specific implementations)
        if platform == "x":
            posts = self._fetch_x_posts(handle, max_items)
        else:
            posts = self._fetch_linkedin_posts(handle, max_items)

        # Filter: new posts only (not already engaged with)
        new_posts = []
        for post in posts:
            pid = post.get("id", "")
            if pid not in self._engaged_posts:
                # Check if post matches any engagement rules
                rule = self._match_engagement_rule(account, post)
                if rule:
                    post["matched_rule"] = rule
                    new_posts.append(post)

        return new_posts

    def _fetch_x_posts(self, handle: str, max_items: int) -> list:
        """Fetch recent tweets from X account. Uses API if credentials exist."""
        token = os.environ.get("X_BEARER_TOKEN", "")
        if not token:
            logger.debug("SmartEngager: no X_BEARER_TOKEN, skipping %s", handle)
            return []

        # Note: X API v2 requires user ID lookup first, then timeline fetch.
        # This is a placeholder — real implementation needs X API v2 endpoints.
        logger.info("SmartEngager: would fetch %d tweets from %s (X API not wired)",
                    max_items, handle)
        return []

    def _fetch_linkedin_posts(self, handle: str, max_items: int) -> list:
        """Fetch recent LinkedIn posts. Uses API if credentials exist."""
        token = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
        if not token:
            logger.debug("SmartEngager: no LINKEDIN_ACCESS_TOKEN, skipping %s", handle)
            return []

        logger.info("SmartEngager: would fetch %d posts from %s (LinkedIn API not wired)",
                    max_items, handle)
        return []

    def _match_engagement_rule(self, account: dict, post: dict) -> dict | None:
        """Find matching engagement rule for a post. Returns rule dict or None."""
        rules = account.get("engagement_rules", [])
        post_text = (post.get("text", "") or "").lower()

        for rule in rules:
            topic = rule.get("topic", "").lower()
            if topic and topic in post_text:
                return rule

        # Fallback: check global watch topics
        watch = self._topics.get("watch", [])
        if any(w in post_text for w in watch):
            return {"action": "just_log", "topic": "global_watch"}

        return None

    def process_account_post(self, account: dict, post: dict) -> dict | None:
        """Process a monitored account's post — generate reply if warranted."""
        rule = post.get("matched_rule", {})
        action = rule.get("action", "just_log")

        if action == "just_log":
            self._engaged_posts.add(post.get("id", ""))
            self._save_engaged_posts()
            return None

        topic = rule.get("topic", post.get("text", "")[:50])

        if not self.should_engage(topic, post.get("text", "")):
            return None

        reply = ""
        if "reply" in action:
            reply = self.generate_reply(topic, post.get("text", ""))

        result = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "account": account.get("handle", ""),
            "platform": account.get("platform", ""),
            "post_id": post.get("id", ""),
            "action": action,
            "reply": reply[:280] if reply else "",
            "topic": topic,
        }

        # Mark as engaged
        self._engaged_posts.add(post.get("id", ""))
        self._save_engaged_posts()
        self.record_engagement(topic, reply if reply else f"monitor:{action}")

        return result

    def should_engage(self, topic: str, content: str) -> bool:
        """Decide whether to engage with a topic/conversation."""
        never = self._topics.get("never_engage", [])
        if any(n in topic.lower() for n in never):
            return False

        watch = self._topics.get("watch", [])
        engage_on = self._topics.get("engage_on", [])
        if not any(w in topic.lower() for w in watch + engage_on):
            return False

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self._state.get("last_engage_date") == today:
            if self._state.get("engagements_today", 0) >= 2:
                return False

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

    def run_account_monitor(self) -> list:
        """Run full account monitoring cycle including Reddit. Returns engagement results."""
        if not self._rate_limit_ok():
            logger.debug("SmartEngager: global rate limit reached")
            return []

        accounts = self.get_monitored_accounts()
        self._state["last_monitor_scan"] = datetime.now(timezone.utc).isoformat()
        self._save_state()

        results = []

        # X/Twitter accounts
        if accounts:
            for account in accounts:
                if not self.should_monitor_now(account):
                    continue
                posts = self.check_account_posts(account)
                for post in posts:
                    result = self.process_account_post(account, post)
                    if result:
                        results.append(result)

        # Reddit subreddits
        reddit_results = self._monitor_reddit()
        results.extend(reddit_results)

        return results

    def _monitor_reddit(self) -> list:
        """Monitor Reddit subreddits for relevant content. Posts comments when warranted."""
        if not self._social:
            try:
                from maggy.plugins.build_in_public.social_api import SocialMonitor
            except ImportError:
                return []
            self._social = SocialMonitor(self._project)

        subreddits = self._topics.get("reddit_monitor", [])
        if not subreddits:
            try:
                from maggy.plugins.build_in_public.social_api import get_competitor_reddit_subreddits
            except ImportError:
                pass
            subreddits = get_competitor_reddit_subreddits()

        if not self._rate_limit_ok():
            return []

        async def _scan():
            results = []
            watch = self._topics.get("watch", [])
            engage_on = self._topics.get("engage_on", [])

            # Scan top 3 priority subreddits
            for sr in subreddits[:3]:
                try:
                    posts = await self._social.reddit_hot(sr, limit=5)
                    for post in posts:
                        pid = post.id
                        if pid in self._engaged_posts:
                            continue
                        post_text = (post.text or "").lower()

                        # Check if post matches our topics
                        matched = [t for t in watch + engage_on if t.lower() in post_text]
                        if not matched:
                            continue

                        # Generate engagement
                        if not self.should_engage(matched[0], post.text):
                            self._engaged_posts.add(pid)
                            continue

                        reply = self.generate_reply(
                            f"Reddit r/{post.subreddit}: {matched[0]}",
                            post.text[:500],
                        )
                        if reply:
                            # Post comment via Reddit API
                            fullname = f"t3_{pid}"
                            ok = await self._social.reddit_comment(fullname, reply)
                            result = {
                                "ts": datetime.now(timezone.utc).isoformat(),
                                "platform": "reddit",
                                "subreddit": post.subreddit,
                                "post_id": pid,
                                "action": "comment",
                                "reply": reply[:280],
                                "topic": matched[0],
                                "success": ok,
                                "url": post.url,
                            }
                            results.append(result)
                            self.record_engagement(matched[0], reply)
                            logger.info("SmartEngager: Reddit comment posted in r/%s", sr)

                        self._engaged_posts.add(pid)
                except Exception as e:
                    logger.debug("Reddit scan failed for r/%s: %s", sr, e)

            self._save_engaged_posts()
            return results

        try:
            import asyncio
            results = asyncio.run(_scan())
        except Exception as e:
            logger.debug("Reddit monitoring error: %s", e)
            results = []

        # Store state
        if "reddit_monitored" not in self._state:
            self._state["reddit_monitored"] = {}
        self._state["reddit_monitored"]["last_scan"] = datetime.now(timezone.utc).isoformat()
        self._state["reddit_monitored"]["subreddits"] = subreddits
        self._save_state()

        return results

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
            "last_monitor_scan": self._state.get("last_monitor_scan", ""),
            "monitored_accounts": len(self.get_monitored_accounts()),
            "engaged_posts": len(self._engaged_posts),
        }
