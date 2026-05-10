"""AI-prioritized inbox — ranks tasks by urgency, OKR alignment, and age.

Works with any IssueTrackerProvider. Caches ranking for 30 minutes in SQLite.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from maggy.config import MaggyConfig
from maggy.services.ai_client import ai_complete
from maggy.providers.base import IssueTrackerProvider, Task

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 30 * 60  # 30 min


def _connect_sqlite(path: Path) -> sqlite3.Connection:
    """Open a SQLite connection with sensible defaults for concurrent use.

    FastAPI serves requests concurrently, and the heartbeat worker writes from
    a different thread. WAL lets readers and writers coexist; foreign_keys
    enforces referential integrity; busy_timeout avoids 'database is locked'
    errors under contention. Matches the convention used by scripts/icpg/store.py.
    """
    db = sqlite3.connect(path, timeout=30.0)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=30000")
    return db


class InboxService:
    def __init__(self, cfg: MaggyConfig, provider: IssueTrackerProvider):
        self.cfg = cfg
        self.provider = provider
        self.db_path = Path(cfg.storage.path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with _connect_sqlite(self.db_path) as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS inbox_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cached_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
            """)

    def _read_cache(self, ignore_ttl: bool = False) -> list[dict] | None:
        with _connect_sqlite(self.db_path) as db:
            row = db.execute(
                "SELECT cached_at, payload FROM inbox_cache ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if not row:
            return None
        if not ignore_ttl:
            cached_at = datetime.fromisoformat(row[0])
            age = (datetime.now(timezone.utc) - cached_at).total_seconds()
            if age > CACHE_TTL_SECONDS:
                return None
        return json.loads(row[1])

    def _write_cache(self, items: list[dict]) -> None:
        with _connect_sqlite(self.db_path) as db:
            db.execute("DELETE FROM inbox_cache")  # keep just latest
            db.execute(
                "INSERT INTO inbox_cache (cached_at, payload) VALUES (?, ?)",
                (datetime.now(timezone.utc).isoformat(), json.dumps(items)),
            )

    async def get_prioritized(self, force_refresh: bool = False) -> list[dict]:
        """Return AI-ranked tasks. Cached 30 min.

        On provider failure (GitHub/Asana down), fall back to the last cached
        ranking — even if stale — rather than 500ing the whole endpoint.
        Staleness is indicated to clients via the `stale` flag on items.
        """
        if not force_refresh:
            cached = self._read_cache()
            if cached is not None:
                return cached

        try:
            tasks = await self.provider.list_tasks(state="open", limit=50)
        except Exception as e:
            logger.warning("provider.list_tasks failed, falling back to stale cache: %s", e)
            stale = self._read_cache(ignore_ttl=True) or []
            for item in stale:
                item["stale"] = True
            return stale

        if not tasks:
            return []

        ranked = await self._rank_with_ai(tasks)
        self._write_cache(ranked)
        return ranked

    async def _rank_with_ai(self, tasks: list[Task]) -> list[dict]:
        """Ask Claude to rank tasks by priority. Falls back to date-sorted if AI unavailable."""
        prompt = self._build_rank_prompt(tasks)
        text = await self._call_ai(prompt)
        if not text:
            return [self._task_to_dict(t, rank=i + 1, reason="AI not available; sorted by recency")
                    for i, t in enumerate(tasks)]
        try:
            start = text.find("{")
            end = text.rfind("}")
            data = json.loads(text[start:end + 1]) if start >= 0 else {"rankings": []}
        except Exception as e:
            logger.warning("AI ranking parse failed: %s", e)
            return [self._task_to_dict(t, rank=i + 1, reason="AI ranking unavailable")
                    for i, t in enumerate(tasks)]

        # Apply rankings — validate each row before trusting it.
        # LLMs routinely return missing indices, string ranks, or out-of-range values.
        rank_map: dict[int, dict] = {}
        for r in data.get("rankings", []):
            if not isinstance(r, dict):
                continue
            idx = r.get("index")
            rank = r.get("rank")
            if not isinstance(idx, int) or idx < 0 or idx >= len(tasks):
                continue
            # Coerce rank defensively
            try:
                rank_int = int(rank)
            except (TypeError, ValueError):
                continue
            if rank_int < 1:
                continue
            # First write wins — LLM occasionally emits duplicate indices
            rank_map.setdefault(idx, {"rank": rank_int, "reason": str(r.get("reason", ""))[:300]})

        ranked: list[dict] = []
        for i, t in enumerate(tasks):
            r = rank_map.get(i) or {"rank": i + 1, "reason": ""}
            ranked.append(self._task_to_dict(t, rank=r["rank"], reason=r["reason"]))
        ranked.sort(key=lambda x: x["rank"])
        return ranked

    def _build_rank_prompt(self, tasks: list[Task]) -> str:
        """Build the ranking prompt for AI."""
        okr_block = ""
        if self.cfg.okrs.source == "yaml" and self.cfg.okrs.items:
            okr_lines = [f"- {o.id}: {o.title}" for o in self.cfg.okrs.items]
            okr_block = "## Current OKRs\n" + "\n".join(okr_lines) + "\n"
        task_lines = []
        for i, t in enumerate(tasks):
            snippet = (t.description or "")[:200].replace("\n", " ")
            task_lines.append(f"[{i}] id={t.id} board={t.board} labels={','.join(t.labels[:3])}\n    {t.title}\n    {snippet}")
        return f"""You are the AI triage assistant for {self.cfg.org.name}.

{okr_block}
Rank the following {len(tasks)} open tasks by priority. Consider:
- OKR alignment (if OKRs provided)
- Urgency signals (labels like "bug", "critical", "urgent")
- Age (older + stale = deprioritize, older + active = maybe important)

Respond with STRICT JSON only:
{{"rankings": [{{"index": 0, "rank": 1, "reason": "<20 word explanation>"}}, ...]}}

Tasks:
{chr(10).join(task_lines)}"""

    async def _call_ai(self, prompt: str) -> str | None:
        """Call AI via API key or CLI subscription."""
        return await ai_complete(prompt, self.cfg)

    def _task_to_dict(self, t: Task, rank: int, reason: str) -> dict:
        return {
            "id": t.id,
            "title": t.title,
            "description": t.description[:500],
            "status": t.status,
            "assignee": t.assignee,
            "author": t.author,
            "url": t.url,
            "labels": t.labels,
            "board": t.board,
            "created_at": t.created_at,
            "updated_at": t.updated_at,
            "rank": rank,
            "ai_reason": reason,
        }
