"""Generic competitor intelligence — AI discovery + RSS/news monitoring + daily briefing.

Stores competitors in ~/.maggy/competitors.json. Monitored feeds stored in SQLite.
Works for ANY domain — CX, fintech, devtools, healthcare, etc. Domain comes from config.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote

import anthropic
import feedparser
import httpx

from src.config import MaggyConfig

logger = logging.getLogger(__name__)


class CompetitorService:
    def __init__(self, cfg: MaggyConfig):
        self.cfg = cfg
        self.competitors_path = Path(cfg.storage.path).expanduser().parent / "competitors.json"
        self.db_path = Path(cfg.storage.path).expanduser()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS competitor_news (
                    id TEXT PRIMARY KEY,
                    competitor_id TEXT NOT NULL,
                    competitor_name TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT,
                    source TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS idx_news_created ON competitor_news(created_at DESC)")
            db.execute("""
                CREATE TABLE IF NOT EXISTS briefing_cache (
                    date TEXT PRIMARY KEY,
                    summary TEXT NOT NULL,
                    signal_count INTEGER NOT NULL,
                    generated_at TEXT NOT NULL
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS feed_cursors (
                    feed_key TEXT PRIMARY KEY,
                    cursor TEXT NOT NULL
                )
            """)

    # ── Registry ─────────────────────────────────────────────────────────

    def load_registry(self) -> dict[str, dict]:
        if not self.competitors_path.exists():
            return {}
        try:
            return json.loads(self.competitors_path.read_text())
        except Exception:
            return {}

    def save_registry(self, registry: dict[str, dict]) -> None:
        self.competitors_path.parent.mkdir(parents=True, exist_ok=True)
        self.competitors_path.write_text(json.dumps(registry, indent=2))

    # ── Discovery ────────────────────────────────────────────────────────

    async def discover(self) -> dict:
        """Ask Claude to identify competitors in the configured domain categories.

        Stores results in ~/.maggy/competitors.json (merges with existing).
        """
        if not self.cfg.ai.api_key:
            return {"error": "ANTHROPIC_API_KEY not set", "added": 0}
        if not self.cfg.competitors.categories:
            return {"error": "No competitor categories configured", "added": 0}

        registry = self.load_registry()
        before = len(registry)

        categories = self.cfg.competitors.categories
        seed = self.cfg.competitors.seed
        org_name = self.cfg.org.name

        prompt = f"""Identify competitors for {org_name}, operating in these categories: {', '.join(categories)}.
{f"User already mentioned: {', '.join(seed)}. Include these and add more." if seed else ""}

Return 12-18 competitors as JSON. Include a mix of:
- Established market leaders
- AI-first challengers / next-gen disruptors
- Vertical-specific specialists

Format (STRICT JSON):
{{"competitors": [
  {{
    "id": "lowercase-slug",
    "name": "Display Name",
    "category": "One of: {' | '.join(categories)}",
    "website": "example.com",
    "description": "One-sentence positioning",
    "strengths": ["str1", "str2", "str3"],
    "weaknesses": ["w1", "w2"],
    "tags": ["tag1", "tag2"],
    "blog_rss": "optional RSS URL or null"
  }}
]}}"""

        try:
            client = anthropic.Anthropic(api_key=self.cfg.ai.api_key)
            msg = client.messages.create(
                model=self.cfg.ai.model,
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = msg.content[0].text if msg.content else ""
            start = text.find("{")
            end = text.rfind("}")
            data = json.loads(text[start:end + 1])
        except Exception as e:
            logger.error("Discovery failed: %s", e)
            return {"error": str(e), "added": 0}

        for comp in data.get("competitors", []):
            cid = comp.get("id", "").lower()
            if not cid:
                continue
            # Preserve blog_rss inside a social sub-dict for monitoring
            rss = comp.pop("blog_rss", None)
            if rss:
                comp["social"] = {"blog_rss": rss}
            # Merge (don't overwrite existing manual edits)
            if cid in registry:
                registry[cid].setdefault("social", {})
                if rss and not registry[cid]["social"].get("blog_rss"):
                    registry[cid]["social"]["blog_rss"] = rss
            else:
                registry[cid] = comp

        self.save_registry(registry)
        return {"total": len(registry), "added": len(registry) - before}

    def list_all(self) -> list[dict]:
        return list(self.load_registry().values())

    # ── Monitoring ───────────────────────────────────────────────────────

    async def monitor_all(self) -> dict:
        """Scan RSS + Google News for all competitors. Called by heartbeat or on-demand."""
        registry = self.load_registry()
        rss_new = 0
        news_new = 0
        for cid, comp in registry.items():
            try:
                rss_new += await self._check_rss(cid, comp)
            except Exception as e:
                logger.debug("RSS %s: %s", cid, e)
            try:
                news_new += await self._check_google_news(cid, comp)
            except Exception as e:
                logger.debug("News %s: %s", cid, e)
        return {"rss": rss_new, "news": news_new, "total_competitors": len(registry)}

    def _get_cursor(self, key: str) -> str:
        with sqlite3.connect(self.db_path) as db:
            row = db.execute("SELECT cursor FROM feed_cursors WHERE feed_key = ?", (key,)).fetchone()
        return row[0] if row else ""

    def _set_cursor(self, key: str, cursor: str) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO feed_cursors (feed_key, cursor) VALUES (?, ?) "
                "ON CONFLICT(feed_key) DO UPDATE SET cursor = excluded.cursor",
                (key, cursor),
            )

    def _classify(self, title: str) -> str:
        t = title.lower()
        if any(w in t for w in ["launch", "release", "introduces", "announces new", "ships"]):
            return "feature_launch"
        if any(w in t for w in ["pricing", "price", "cost", "free tier"]):
            return "pricing_change"
        if any(w in t for w in ["funding", "raises", "series", "valuation", "investment"]):
            return "funding"
        if any(w in t for w in ["acquir", "acquisition", "merge", "bought"]):
            return "acquisition"
        if any(w in t for w in ["partner", "integration with", "teams up"]):
            return "partnership"
        return "news"

    def _log_event(self, competitor_id: str, competitor_name: str, event_type: str, title: str, url: str, source: str) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO competitor_news (id, competitor_id, competitor_name, event_type, title, url, source, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), competitor_id, competitor_name, event_type, title, url, source, datetime.now(timezone.utc).isoformat()),
            )

    async def _check_rss(self, cid: str, comp: dict) -> int:
        rss_url = (comp.get("social") or {}).get("blog_rss")
        if not rss_url:
            return 0
        cursor_key = f"rss:{cid}"
        last_cursor = self._get_cursor(cursor_key)

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(rss_url)
                if resp.status_code >= 400:
                    return 0
                feed = feedparser.parse(resp.text)
        except Exception:
            return 0

        new_items = 0
        latest = last_cursor
        for entry in feed.entries[:10]:
            pub = entry.get("published", entry.get("updated", ""))
            if pub and pub <= last_cursor:
                continue
            title = entry.get("title", "")
            link = entry.get("link", "")
            if pub and pub > latest:
                latest = pub
            self._log_event(cid, comp.get("name", cid), "blog_post", f"{comp.get('name','')}: {title}", link, "rss")
            new_items += 1

        if latest and latest != last_cursor:
            self._set_cursor(cursor_key, latest)
        return new_items

    async def _check_google_news(self, cid: str, comp: dict) -> int:
        name = comp.get("name", "")
        if not name:
            return 0
        cursor_key = f"news:{cid}"
        last_cursor = self._get_cursor(cursor_key)

        # Use domain + category for better relevance — e.g. "Sprinklr CX" not "Sprinklr software"
        category = (comp.get("category") or "").replace("_", " ").split("/")[0]
        search_term = f"{name} {category}" if category else f"{name} {self.cfg.org.domain}"
        url = f"https://news.google.com/rss/search?q={quote(search_term)}&hl=en-US&gl=US&ceid=US:en"

        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"})
                if resp.status_code >= 400:
                    return 0
                feed = feedparser.parse(resp.text)
        except Exception:
            return 0

        new_items = 0
        latest = last_cursor
        for entry in feed.entries[:5]:
            pub = entry.get("published", "")
            if pub and pub <= last_cursor:
                continue
            title = entry.get("title", "")
            link = entry.get("link", "")
            if pub and pub > latest:
                latest = pub
            self._log_event(cid, name, self._classify(title), f"{name}: {title}", link, "google_news")
            new_items += 1

        if latest and latest != last_cursor:
            self._set_cursor(cursor_key, latest)
        return new_items

    # ── News query ───────────────────────────────────────────────────────

    def get_news(self, limit: int = 100) -> list[dict]:
        with sqlite3.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                "SELECT * FROM competitor_news ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Daily briefing (cached per day) ──────────────────────────────────

    async def get_daily_briefing(self, refresh: bool = False) -> dict:
        today = date.today().isoformat()

        if not refresh:
            with sqlite3.connect(self.db_path) as db:
                row = db.execute(
                    "SELECT summary, signal_count, generated_at FROM briefing_cache WHERE date = ?",
                    (today,),
                ).fetchone()
            if row:
                return {"date": today, "summary": row[0], "total_signals": row[1], "generated_at": row[2]}

        # Regenerate
        news = self.get_news(limit=80)
        if not news:
            return {"date": today, "summary": "No competitor news yet. Run a scan first.", "total_signals": 0}
        if not self.cfg.ai.api_key:
            return {"date": today, "summary": "AI not configured — add ANTHROPIC_API_KEY to generate briefings.", "total_signals": len(news)}

        digest = [f"[{n['event_type']}] {n['competitor_name']}: {n['title']}" for n in news[:50]]
        domain = self.cfg.org.domain or "our domain"

        prompt = f"""You are the competitive intelligence analyst for {self.cfg.org.name} in the {domain} space.

Write a daily competitive landscape briefing for {today}. Structure:

1. **Top Signals Today** — 3-5 most important moves (acquisitions, launches, partnerships) with specific competitor names
2. **Market Trends** — patterns across multiple signals (AI adoption, consolidation, pricing shifts)
3. **Implications for {self.cfg.org.name}** — 2-3 specific, actionable takeaways

Be specific with competitor names and facts. No generic advice. Under 250 words.

Signals ({len(digest)} total):
{chr(10).join(digest)}"""

        try:
            client = anthropic.Anthropic(api_key=self.cfg.ai.api_key)
            msg = client.messages.create(
                model=self.cfg.ai.model,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )
            summary = msg.content[0].text if msg.content else ""
        except Exception as e:
            return {"date": today, "summary": f"Failed to generate briefing: {e}", "total_signals": len(news)}

        generated_at = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO briefing_cache (date, summary, signal_count, generated_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(date) DO UPDATE SET summary = excluded.summary, signal_count = excluded.signal_count, generated_at = excluded.generated_at",
                (today, summary, len(news), generated_at),
            )

        return {"date": today, "summary": summary, "total_signals": len(news), "generated_at": generated_at}
