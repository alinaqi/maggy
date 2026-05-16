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

import base64
import json
import logging
import os
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import yaml

try:
    from maggy.plugins.manager import HookBus, PluginManifest
except ImportError:
    HookBus = None  # type: ignore
    PluginManifest = dict  # type: ignore

# Content strategy engine inlined for standalone compatibility
# (Python 3.14 @dataclass breaks with importlib dynamic loading)

BEST_TIMES = {
    "linkedin": {
        "deep_dive": ["Tue 09:00", "Wed 09:00", "Thu 09:00"],
        "announcement": ["Tue 08:30", "Wed 08:30", "Thu 08:30"],
        "insight": ["Tue 10:00", "Wed 10:00", "Thu 10:00"],
    },
    "x": {
        "deep_dive": ["Tue 10:00", "Wed 10:00", "Thu 10:00"],
        "announcement": ["Tue 09:00", "Wed 09:00", "Thu 14:00"],
        "insight": ["Tue 11:00", "Wed 11:00", "Thu 11:00", "Fri 11:00"],
        "thread": ["Wed 10:30", "Thu 10:30"],
    },
}

SERIES_TEMPLATE = [
    ("teaser", 0, "curiosity, one-line hook"),
    ("deep_dive", 1, "technical, teaches something"),
    ("lessons", 3, "reflective, what surprised you"),
]


class ScheduledPost:
    def __init__(self, channel="", text="", scheduled_at="", format="single",
                 thread_index=0, thread_total=1, media=None):
        self.channel = channel
        self.text = text
        self.scheduled_at = scheduled_at
        self.format = format
        self.thread_index = thread_index
        self.thread_total = thread_total
        self.media = media or []

logger = logging.getLogger(__name__)

BUFFER_API = "https://api.buffer.com"  # GraphQL endpoint
IMAGE_API = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-image-preview:generateContent"
IMAGE_MODEL = "gemini-3.1-flash-image-preview"


class ContentStrategy:
    """Decides what, where, when, and how to post — full editorial logic."""

    def __init__(self, config: dict):
        self._config = config
        self._queue = self._load_queue()

    def plan(self, event_type: str, context: dict,
             narratives: dict) -> list:
        posts = []
        channels = self._config.get("channels", {})
        for channel, text in narratives.items():
            cfg = channels.get(channel, {})
            content_type = self._classify(event_type, text, channel)
            fmt = self._best_format(text, channel, content_type)
            if fmt == "thread":
                posts += self._build_thread(channel, text, cfg, content_type, context)
            elif fmt == "series":
                posts += self._build_series(channel, context, cfg)
            else:
                posts.append(ScheduledPost(
                    channel=channel, text=text[:cfg.get("max_chars", 3000)],
                    scheduled_at=self._best_time(channel, content_type), format="single",
                ))
        return self._space_out(posts)

    def _classify(self, event_type, text, channel):
        if event_type in ("on_feature_shipped", "on_pr_merged"):
            return "announcement"
        if event_type == "on_review_passed":
            return "insight"
        return "deep_dive" if len(text) > 500 or channel == "linkedin" else "insight"

    def _best_format(self, text, channel, content_type):
        if channel != "x":
            return "single"
        max_chars = self._config.get("channels", {}).get("x", {}).get("max_chars", 280)
        if len(text) > max_chars * 1.5 and self._ai_yes_no(
            f"Does this have multiple distinct insights for a thread? {text[:400]}"
        ):
            return "thread"
        if content_type in ("announcement", "deep_dive") and len(text) > 400:
            return "series"
        return "single"

    def _ai_yes_no(self, question):
        try:
            deepseek = os.path.expanduser("~/bin/deepseek")
            r = subprocess.run([deepseek, "--flash", question], capture_output=True, text=True, timeout=15)
            return "YES" in (r.stdout or "").upper()[:10]
        except Exception:
            return False

    def _build_thread(self, channel, text, cfg, content_type, context):
        max_chars = cfg.get("max_chars", 280)
        tweets = self._split_tweets(text, max_chars)
        if len(tweets) <= 1:
            return [ScheduledPost(channel=channel, text=text[:max_chars],
                    scheduled_at=self._best_time(channel, content_type), format="single")]
        base = self._next_slot(channel, content_type)
        posts = []
        for i, t in enumerate(tweets):
            label = f"{t} ({i+1}/{len(tweets)})" if len(tweets) > 1 else t
            posts.append(ScheduledPost(channel=channel, text=label,
                scheduled_at=base.isoformat(), format="thread_tweet",
                thread_index=i+1, thread_total=len(tweets)))
            base += timedelta(minutes=2)
        return posts

    def _split_tweets(self, text, max_chars):
        tweets, current = [], ""
        for s in text.replace("\n", " ").split(". "):
            test = f"{current}. {s}" if current else s
            if len(test) > max_chars and current:
                tweets.append(current.strip())
                current = s
            else:
                current = test
        if current:
            tweets.append(current.strip()[:max_chars])
        return tweets

    def _build_series(self, channel, context, cfg):
        what, body = context.get("what", ""), context.get("context", "")[:500]
        posts = []
        for stage, delay, tone in SERIES_TEMPLATE:
            prompt = (f"Write a {stage} post ({tone}) for {channel.upper()} "
                      f"about: {what}. Context: {body}. Max {cfg.get('max_chars', 280)} chars.")
            try:
                r = subprocess.run(
                    [os.path.expanduser("~/bin/deepseek"), "--flash", prompt],
                    capture_output=True, text=True, timeout=30)
                text = r.stdout.strip() if r.returncode == 0 else ""
            except Exception:
                text = ""
            if text:
                ct = "deep_dive" if stage != "teaser" else "announcement"
                posts.append(ScheduledPost(channel=channel, text=text[:cfg.get("max_chars", 3000)],
                    scheduled_at=self._best_time(channel, ct, delay), format=f"series_{stage}"))
        return posts

    def _best_time(self, channel, content_type, offset_days=0):
        times = BEST_TIMES.get(channel, {}).get(content_type, BEST_TIMES.get(channel, {}).get("insight", ["Tue 09:00"]))
        now = datetime.now(timezone.utc)
        for d in range(offset_days, offset_days + 14):
            target = now + timedelta(days=d)
            day = target.strftime("%a")
            for t in times:
                if t.startswith(day):
                    h, m = map(int, t.split(" ")[1].split(":"))
                    return target.replace(hour=h, minute=m, second=0, microsecond=0).isoformat()
        return (now + timedelta(days=offset_days)).replace(hour=9, minute=0, second=0, microsecond=0).isoformat()

    def _next_slot(self, channel, content_type):
        candidate = datetime.fromisoformat(self._best_time(channel, content_type))
        for post in self._queue:
            existing = datetime.fromisoformat(post["scheduled_at"])
            if abs((candidate - existing).total_seconds()) < 7200:
                candidate += timedelta(hours=2)
        return candidate

    def _space_out(self, posts):
        if not posts:
            return posts
        # Load ALL project queues to avoid conflicts across projects
        used = set()
        for qf in (Path.home() / ".maggy" / "build-in-public").glob("schedule*.json"):
            try:
                q = json.loads(qf.read_text())
                for p in (q if isinstance(q, list) else [q]):
                    used.add(p["scheduled_at"][:13])
            except Exception:
                pass
        for p in posts:
            dt = datetime.fromisoformat(p.scheduled_at)
            while dt.isoformat()[:13] in used:
                dt += timedelta(hours=1)
            used.add(dt.isoformat()[:13])
            p.scheduled_at = dt.isoformat()
        return sorted(posts, key=lambda p: p.scheduled_at)

    def commit(self, posts):
        for p in posts:
            self._queue.append({"channel": p.channel, "text": p.text[:100],
                               "scheduled_at": p.scheduled_at,
                               "project": getattr(self, '_project', 'unknown'),
                               "format": p.format})
        self._save_queue()

    def _load_queue(self):
        qf = Path.home() / ".maggy" / "build-in-public" / "schedule.json"
        try:
            return json.loads(qf.read_text())
        except Exception:
            return []

    def _save_queue(self):
        qf = Path.home() / ".maggy" / "build-in-public" / "schedule.json"
        qf.parent.mkdir(parents=True, exist_ok=True)
        qf.write_text(json.dumps(self._queue[-50:], indent=2))


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

    def __init__(self, manifest):
        self._manifest = manifest
        self._config = getattr(manifest, 'config', manifest.get('config', {}))
        self._anonymize = self._load_anonymize()
        self._customization = self._load_customization()
        self._tags = self._load_tags()
        self._strategy = ContentStrategy(self._config)
        self._posts_today = 0
        self._last_post_date = ""
        self._project_state = self._load_project_state()

    def _load_tags(self) -> dict:
        """Load smart tagging rules from tags.yaml."""
        path = Path(__file__).parent / "tags.yaml"
        try:
            return yaml.safe_load(path.read_text())
        except Exception:
            return {"platforms": {}}

    def _load_customization(self) -> dict:
        """Load user customization from customization.md."""
        path = Path(__file__).parent / "customization.md"
        try:
            text = path.read_text()
            # Parse markdown for explicit_brands and explicit_clickouts
            brands = []
            clickouts = []
            in_brands = False
            in_clickouts = False
            for line in text.split("\n"):
                if "explicit_brands:" in line:
                    in_brands = True; continue
                if "explicit_clickouts:" in line:
                    in_clickouts = True; continue
                if line.startswith("#") or not line.strip():
                    in_brands = in_clickouts = False; continue
                if in_brands and line.strip().startswith("-"):
                    brand = line.strip().lstrip("-").strip().strip('"')
                    if brand: brands.append(brand)
                if in_clickouts and line.strip().startswith("-"):
                    url = line.strip().lstrip("-").strip().strip('"')
                    if url: clickouts.append(url)
            return {"brands": brands, "clickouts": clickouts}
        except Exception:
            return {"brands": [], "clickouts": []}

    def _load_project_state(self) -> dict:
        """Load per-project enabled state."""
        path = Path.home() / ".maggy" / "build-in-public" / "projects.json"
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}

    def is_enabled_for(self, project: str) -> bool:
        return self._project_state.get(project, {}).get("enabled", True)

    def _smart_tag(self, text: str, channel: str) -> str:
        """Auto-tag relevant accounts based on post content."""
        platform = "linkedin" if channel == "linkedin" else "x"
        accounts = self._tags.get("platforms", {}).get(platform, {}).get("accounts", [])
        if not accounts:
            return text

        text_lower = text.lower()
        tagged = set()
        mentions = []
        for acct in accounts:
            for kw in acct.get("trigger_keywords", []):
                if kw in text_lower and acct["handle"] not in tagged:
                    mentions.append(acct["handle"])
                    tagged.add(acct["handle"])
                    break

        if not mentions:
            return text

        # X: append @handles at end (up to 3)
        if channel == "x":
            tag_str = " ".join(mentions[:3])
            if tag_str not in text:
                text = text.rstrip() + "\n\n" + tag_str
        # LinkedIn: append company mentions
        else:
            tag_str = " ".join(f"@{h}" for h in mentions[:3])
            if tag_str not in text:
                text = text.rstrip() + "\n\n" + tag_str

        return text

    def set_enabled(self, project: str, enabled: bool):
        self._project_state[project] = self._project_state.get(project, {})
        self._project_state[project]["enabled"] = enabled
        path = Path.home() / ".maggy" / "build-in-public" / "projects.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._project_state, indent=2))

    def _load_anonymize(self) -> dict:
        manifest_path = getattr(self._manifest, 'path', self._manifest.get('_path', ''))
        rules_path = Path(manifest_path) / "anonymize.yaml" if manifest_path else Path(__file__).parent / "anonymize.yaml"
        try:
            return yaml.safe_load(rules_path.read_text())
        except Exception:
            return {"rules": {}, "strip": [], "patterns": []}

    def _redact(self, text: str) -> str:
        """Apply anonymization rules — replace sensitive terms, skip explicit brands."""
        rules = self._anonymize.get("rules", {})
        explicit = self._customization.get("brands", [])
        for term, replacement in rules.items():
            # Skip if brand is explicitly allowed by user
            if term in explicit or term.lower() in [b.lower() for b in explicit]:
                continue
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

    async def _handle_event(self, event_type: str, payload: dict):
        """Generic handler — classify, plan, schedule."""
        if not self._check_rate_limit():
            return

        what = payload.get("title") or payload.get("feature") or payload.get("what", "")
        body = payload.get("body", "")[:1000] or payload.get("context", "")[:1000]
        context = {"what": what, "context": body, **payload}

        # Phase 1: Build channel-native narratives
        narratives = self._build_narrative(event_type, context)

        # Phase 2: Strategy engine decides format + timing
        scheduled = self._strategy.plan(event_type, context, narratives)

        # Phase 3: Capture screenshot if feature shipped
        screenshot_path = ""
        if event_type in ("on_feature_shipped", "on_pr_merged"):
            screenshot_path = await self._capture_screenshot(
                payload.get("url", payload.get("preview_url", ""))
            )

        # Phase 3b: Generate AI image if visualization adds value
        image_path = ""
        if self._should_generate_image(event_type, context, narratives):
            image_path = self._generate_image(event_type, context)

        # Phase 4: Schedule all posts (with best available media)
        media = screenshot_path or image_path
        await self._schedule_posts([s.__dict__ for s in scheduled], media)

        # Phase 5: Commit to queue
        self._strategy.commit(scheduled)

        # Log the plan
        self._log_plan(scheduled)

    async def handle_pr_merged(self, payload: dict):
        await self._handle_event("on_pr_merged", payload)

    async def handle_feature_shipped(self, payload: dict):
        await self._handle_event("on_feature_shipped", payload)

    async def handle_review_passed(self, payload: dict):
        if payload.get("verdict", "") != "APPROVED":
            return
        if not payload.get("plan_summary"):
            payload["plan_summary"] = "architected a solution"
        await self._handle_event("on_review_passed", payload)

    def _build_narrative(self, event_type: str, context: dict) -> dict:
        """Synthesize narrative arcs per channel. Returns {channel: text}."""
        what = context.get("what", "")
        ctx = context.get("context", "")[:500]
        channels = self._config.get("channels", {})

        narratives = {}
        for channel, cfg in channels.items():
            max_chars = cfg.get("max_chars", 280)
            tone = cfg.get("tone", "confident, sharp")
            prompt = (
                f"You are a technical storyteller posting on {channel.upper()}. "
                f"Turn this work into a post (max {max_chars} chars). "
                f"Tone: {tone}. "
                f"Focus on IMPACT and APPROACH, not feature names. "
                f"No hashtags unless they flow naturally.\n\n"
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
                    text = self._redact(result.stdout.strip()[:max_chars])
                    # X posts: always append clickout
                    if channel == "x":
                        clickouts = self._customization.get("clickouts", [])
                        if clickouts and clickouts[0] not in text:
                            text = text.rstrip() + " " + clickouts[0]
                    # Apply smart tagging
                    text = self._smart_tag(text, channel)
                    narratives[channel] = text
            except Exception:
                pass

        if not narratives:
            narratives["linkedin"] = self._redact(
                f"Shipped {what}: {ctx[:200]}"
            )
        return narratives

    def _format_posts(self, narratives: dict, media_path: str = "") -> list[dict]:
        """Format channel-specific posts."""
        posts = []
        channels = self._config.get("channels", {})
        for channel, text in narratives.items():
            cfg = channels.get(channel, {})
            posts.append({
                "channel": channel,
                "text": text,
                "media": [{"url": media_path}] if media_path else [],
                "scheduled_at": self._channel_schedule(cfg),
            })
        return posts

    def _channel_schedule(self, cfg: dict) -> str:
        """Get preferred schedule time for a channel."""
        tz = timezone.utc
        now = datetime.now(tz)
        schedule = cfg.get("schedule", "09:00 UTC")
        try:
            hour, minute = map(int, schedule.replace(" UTC", "").split(":")[:2])
            scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if scheduled < now:
                from datetime import timedelta
                scheduled += timedelta(days=1)
            return scheduled.isoformat()
        except Exception:
            return now.isoformat()

    def _log_plan(self, scheduled: list):
        """Log the full schedule plan."""
        plan_dir = Path.home() / ".maggy" / "build-in-public"
        plan_dir.mkdir(parents=True, exist_ok=True)
        plan_file = plan_dir / "schedule-plan.json"
        plan_file.write_text(json.dumps(
            [s.__dict__ for s in scheduled], indent=2, default=str,
        ))

    async def _schedule_posts(self, posts: list[dict], media_path: str = ""):
        """Schedule posts via Buffer GraphQL API."""
        token = os.environ.get("BUFFER_ACCESS_TOKEN", "")
        if not token:
            for post in posts:
                logger.info(
                    "build-in-public: [%s] no token, would have posted: %s",
                    post["channel"], post["text"][:100],
                )
                self._log_post(post)
            return

        try:
            org_id, channels = await self._fetch_buffer_channels(token)
            if not channels:
                logger.warning("build-in-public: no Buffer channels found")
                for post in posts:
                    self._log_post(post)
                return

            async with httpx.AsyncClient(timeout=30) as client:
                for post in posts:
                    service = "linkedin" if post["channel"] == "linkedin" else "twitter"
                    ch = next(
                        (c for c in channels
                         if c.get("service", "").lower() == service),
                        None,
                    )
                    if not ch:
                        logger.warning("build-in-public: no Buffer %s channel", service)
                        self._log_post(post)
                        continue

                    mutation = """
                    mutation SchedulePost($input: CreatePostInput!) {
                      createPost(input: $input) {
                        __typename
                        ... on PostActionSuccess {
                          post { id status dueAt text channelService }
                        }
                      }
                    }"""
                    variables = {
                        "input": {
                            "channelId": ch["id"],
                            "text": post["text"],
                            "schedulingType": "automatic",
                            "dueAt": post.get("scheduled_at", ""),
                            "mode": "customScheduled",
                        }
                    }
                    # Attach image to LinkedIn posts
                    if media_path and post["channel"] == "linkedin" and media_path.startswith("http"):
                        variables["input"]["assets"] = [{"image": {"url": media_path}}]
                    resp = await client.post(
                        BUFFER_API,
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Content-Type": "application/json",
                        },
                        json={"query": mutation, "variables": variables},
                    )
                    if resp.status_code == 200 and "errors" not in resp.json():
                        self._posts_today += 1
                        logger.info("build-in-public: scheduled on %s via GraphQL",
                                    post["channel"])
                    else:
                        error = resp.json().get("errors", [{}])[0].get("message", resp.text[:200])
                        logger.warning("build-in-public: GraphQL error: %s", error)
                        self._log_post(post)
        except Exception as e:
            logger.warning("build-in-public: Buffer GraphQL failed: %s", e)
            for post in posts:
                self._log_post(post)

    async def _fetch_buffer_channels(self, token: str) -> tuple:
        """Fetch org ID and channels from Buffer GraphQL."""
        async with httpx.AsyncClient(timeout=15) as client:
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            # Get org ID
            resp = await client.post(
                BUFFER_API,
                headers=headers,
                json={"query": "query { account { organizations { id name } } }"},
            )
            if resp.status_code != 200:
                return "", []
            data = resp.json()
            orgs = data.get("data", {}).get("account", {}).get("organizations", [])
            if not orgs:
                return "", []
            org_id = orgs[0]["id"]

            # Get channels
            resp = await client.post(
                BUFFER_API,
                headers=headers,
                json={
                    "query": """
                    query GetChannels($input: ChannelsInput!) {
                      channels(input: $input) {
                        id name service type isDisconnected
                      }
                    }""",
                    "variables": {"input": {"organizationId": org_id, "filter": None}},
                },
            )
            channels = resp.json().get("data", {}).get("channels", [])
            return org_id, channels

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

    def _public_url(self, path: str) -> str:
        """Convert local image path to public GitHub raw URL."""
        repo_root = Path(__file__).parent.parent.parent.parent
        try:
            rel = str(Path(path).relative_to(repo_root))
            # Build raw.githubusercontent.com URL
            remote = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True, text=True, cwd=str(repo_root),
            ).stdout.strip()
            # Extract org/repo from git URL
            if "github.com" in remote:
                parts = remote.rstrip(".git").split("github.com")[-1].strip("/:").split("/")
                if len(parts) >= 2:
                    org, repo = parts[0], parts[1]
                    branch = "main"
                    return f"https://raw.githubusercontent.com/{org}/{repo}/{branch}/{rel}"
        except Exception:
            pass
        return path  # Fallback: local path

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

    def _should_generate_image(self, event_type: str, context: dict,
                               narratives: dict) -> bool:
        """Ask DeepSeek if a visual would meaningfully improve these posts."""
        # Only for architecture/deep-dive content
        if event_type not in ("on_feature_shipped", "on_review_passed"):
            return False
        text = narratives.get("linkedin", narratives.get("x", ""))
        if len(text) < 500:
            return False
        prompt = (
            f"Would this post benefit from a generated visual (architecture "
            f"diagram, technical illustration, or concept visualization)? "
            f"Reply YES or NO.\n\n{text[:600]}"
        )
        try:
            r = subprocess.run(
                [os.path.expanduser("~/bin/deepseek"), "--flash", prompt],
                capture_output=True, text=True, timeout=15,
            )
            return "YES" in (r.stdout or "").upper()[:10]
        except Exception:
            return False

    def _generate_image(self, event_type: str, context: dict) -> str:
        """Generate a technical illustration via Gemini Imagen."""
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            return ""

        what = context.get("what", "")[:200]
        image_prompt = (
            f"Create a clean, modern technical illustration or diagram "
            f"that visualizes this concept: {what}. "
            f"Use a dark theme with orange accents. "
            f"Minimalist, professional, suitable for a LinkedIn post. "
            f"No text in the image unless it's labels on a diagram. "
            f"Abstract visualization, not a screenshot or UI mockup."
        )

        try:
            resp = httpx.post(
                IMAGE_API,
                headers={"x-goog-api-key": api_key,
                         "Content-Type": "application/json"},
                json={
                    "contents": [{"parts": [{"text": image_prompt}]}],
                    "generationConfig": {
                        "responseModalities": ["TEXT", "IMAGE"],
                    },
                },
                timeout=60,
            )
            if resp.status_code != 200:
                logger.debug("Gemini image gen failed: %s", resp.text[:200])
                return ""

            data = resp.json()
            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            for part in parts:
                if "inlineData" in part:
                    b64 = part["inlineData"]["data"]
                    img_dir = Path.home() / ".maggy" / "build-in-public" / "images"
                    img_dir.mkdir(parents=True, exist_ok=True)
                    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
                    path = img_dir / f"hero-{ts}.png"
                    path.write_bytes(base64.b64decode(b64))
                    logger.info("build-in-public: generated image %s", path)
                    # Return public URL if image is in repo, else local path
                    return self._public_url(path)

            return ""
        except Exception as e:
            logger.debug("build-in-public: image generation failed: %s", e)
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
