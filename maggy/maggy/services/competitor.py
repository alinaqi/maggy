"""Generic competitor intelligence — AI discovery + RSS/news monitoring + daily briefing.

Stores competitors in ~/.maggy/competitors.json. Monitored feeds stored in SQLite.
Works for ANY domain — CX, fintech, devtools, healthcare, etc. Domain comes from config.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import logging
import socket
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlparse

import anthropic
import feedparser
import httpx

from maggy.config import MaggyConfig

logger = logging.getLogger(__name__)


def _connect_sqlite(path: Path) -> sqlite3.Connection:
    """Open a SQLite connection with WAL + foreign_keys + busy_timeout.

    Same defaults as InboxService — safe for concurrent FastAPI handlers
    plus the heartbeat worker writing from another thread.
    """
    db = sqlite3.connect(path, timeout=30.0)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=30000")
    return db


def _parse_feed_date(raw: str) -> datetime | None:
    """Parse RFC 822 / ISO 8601 date strings from RSS/Atom feeds.

    feedparser returns `published` as RFC 822 ("Mon, 15 Jan 2024 10:30:00 GMT").
    Comparing those lexicographically is wrong because day names cycle weekly.
    Returns a timezone-aware UTC datetime, or None if parsing fails.
    """
    if not raw:
        return None
    # feedparser exposes parsed tuple when it can
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        pass
    # Fall through: try ISO 8601 (atom feeds, Google News sometimes)
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _is_safe_feed_url(url: str) -> bool:
    """Reject RSS URLs that would let an attacker hit internal services.

    Blocks non-HTTP(S), bare hostnames without scheme, and any host whose
    resolved IPs include loopback, link-local, private, or multicast ranges.
    Prevents SSRF via AI-discovered or user-edited competitor registry.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").strip().lower()
    if not host or host in ("localhost",):
        return False
    # Block bare IP strings that are themselves private
    try:
        ip = ipaddress.ip_address(host)
        return not (ip.is_loopback or ip.is_private or ip.is_link_local
                    or ip.is_multicast or ip.is_reserved or ip.is_unspecified)
    except ValueError:
        pass
    # Hostname: resolve and check every returned address
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr.split("%")[0])  # strip scope id on v6
        except ValueError:
            return False
        if (ip.is_loopback or ip.is_private or ip.is_link_local
                or ip.is_multicast or ip.is_reserved or ip.is_unspecified):
            return False
    return True


class CompetitorService:
    def __init__(self, cfg: MaggyConfig):
        self.cfg = cfg
        self.competitors_path = Path(cfg.storage.path).expanduser().parent / "competitors.json"
        self.db_path = Path(cfg.storage.path).expanduser()
        self._init_db()

    def _init_db(self) -> None:
        with _connect_sqlite(self.db_path) as db:
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
            # Use async client so the event loop isn't blocked during
            # a multi-second LLM round-trip.
            client = anthropic.AsyncAnthropic(api_key=self.cfg.ai.api_key)
            msg = await client.messages.create(
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
        with _connect_sqlite(self.db_path) as db:
            row = db.execute("SELECT cursor FROM feed_cursors WHERE feed_key = ?", (key,)).fetchone()
        return row[0] if row else ""

    def _set_cursor(self, key: str, cursor: str) -> None:
        with _connect_sqlite(self.db_path) as db:
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
        # Deterministic ID so the same article logged twice (cursor reset,
        # overlapping scans) becomes a no-op instead of a duplicate row.
        id_seed = f"{competitor_id}|{source}|{url or title}"
        event_id = hashlib.sha256(id_seed.encode("utf-8")).hexdigest()[:32]
        with _connect_sqlite(self.db_path) as db:
            db.execute(
                "INSERT OR IGNORE INTO competitor_news "
                "(id, competitor_id, competitor_name, event_type, title, url, source, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (event_id, competitor_id, competitor_name, event_type, title, url, source,
                 datetime.now(timezone.utc).isoformat()),
            )

    async def _check_rss(self, cid: str, comp: dict) -> int:
        rss_url = (comp.get("social") or {}).get("blog_rss")
        if not rss_url:
            return 0
        if not _is_safe_feed_url(rss_url):
            logger.warning("Skipping unsafe RSS URL for %s: %s", cid, rss_url)
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

        # Cursor is stored as an ISO-8601 UTC string so comparisons are
        # valid lexicographically AND survive round-trips through SQLite.
        last_cursor_dt = _parse_feed_date(last_cursor) if last_cursor else None
        new_items = 0
        latest_dt = last_cursor_dt
        for entry in feed.entries[:10]:
            pub_raw = entry.get("published", entry.get("updated", ""))
            pub_dt = _parse_feed_date(pub_raw)
            # Skip entries already seen (we have a cursor AND the entry's parsed date is ≤ cursor).
            # Entries without a parseable date are always processed — INSERT OR IGNORE dedupes.
            if pub_dt and last_cursor_dt and pub_dt <= last_cursor_dt:
                continue
            title = entry.get("title", "")
            link = entry.get("link", "")
            if pub_dt and (latest_dt is None or pub_dt > latest_dt):
                latest_dt = pub_dt
            self._log_event(cid, comp.get("name", cid), "blog_post", f"{comp.get('name','')}: {title}", link, "rss")
            new_items += 1

        if latest_dt and latest_dt != last_cursor_dt:
            self._set_cursor(cursor_key, latest_dt.isoformat())
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

        last_cursor_dt = _parse_feed_date(last_cursor) if last_cursor else None
        new_items = 0
        latest_dt = last_cursor_dt
        for entry in feed.entries[:5]:
            pub_dt = _parse_feed_date(entry.get("published", ""))
            if pub_dt and last_cursor_dt and pub_dt <= last_cursor_dt:
                continue
            title = entry.get("title", "")
            link = entry.get("link", "")
            if pub_dt and (latest_dt is None or pub_dt > latest_dt):
                latest_dt = pub_dt
            self._log_event(cid, name, self._classify(title), f"{name}: {title}", link, "google_news")
            new_items += 1

        if latest_dt and latest_dt != last_cursor_dt:
            self._set_cursor(cursor_key, latest_dt.isoformat())
        return new_items

    # ── News query ───────────────────────────────────────────────────────

    def get_news(self, limit: int = 100) -> list[dict]:
        with _connect_sqlite(self.db_path) as db:
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
            with _connect_sqlite(self.db_path) as db:
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
            client = anthropic.AsyncAnthropic(api_key=self.cfg.ai.api_key)
            msg = await client.messages.create(
                model=self.cfg.ai.model,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )
            summary = msg.content[0].text if msg.content else ""
        except Exception as e:
            return {"date": today, "summary": f"Failed to generate briefing: {e}", "total_signals": len(news)}

        generated_at = datetime.now(timezone.utc).isoformat()
        with _connect_sqlite(self.db_path) as db:
            db.execute(
                "INSERT INTO briefing_cache (date, summary, signal_count, generated_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(date) DO UPDATE SET summary = excluded.summary, signal_count = excluded.signal_count, generated_at = excluded.generated_at",
                (today, summary, len(news), generated_at),
            )

        return {"date": today, "summary": summary, "total_signals": len(news), "generated_at": generated_at}
