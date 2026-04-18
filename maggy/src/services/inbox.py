"""AI-prioritized inbox — ranks tasks by urgency, OKR alignment, and age.

Works with any IssueTrackerProvider. Caches ranking for 30 minutes in SQLite.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import anthropic

from src.config import MaggyConfig
from src.providers.base import IssueTrackerProvider, Task

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 30 * 60  # 30 min


class InboxService:
    def __init__(self, cfg: MaggyConfig, provider: IssueTrackerProvider):
        self.cfg = cfg
        self.provider = provider
        self.db_path = Path(cfg.storage.path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS inbox_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cached_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
            """)

    def _read_cache(self) -> list[dict] | None:
        with sqlite3.connect(self.db_path) as db:
            row = db.execute(
                "SELECT cached_at, payload FROM inbox_cache ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if not row:
            return None
        cached_at = datetime.fromisoformat(row[0])
        age = (datetime.now(timezone.utc) - cached_at).total_seconds()
        if age > CACHE_TTL_SECONDS:
            return None
        return json.loads(row[1])

    def _write_cache(self, items: list[dict]) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.execute("DELETE FROM inbox_cache")  # keep just latest
            db.execute(
                "INSERT INTO inbox_cache (cached_at, payload) VALUES (?, ?)",
                (datetime.now(timezone.utc).isoformat(), json.dumps(items)),
            )

    async def get_prioritized(self, force_refresh: bool = False) -> list[dict]:
        """Return AI-ranked tasks. Cached 30 min."""
        if not force_refresh:
            cached = self._read_cache()
            if cached is not None:
                return cached

        tasks = await self.provider.list_tasks(state="open", limit=50)
        if not tasks:
            return []

        ranked = await self._rank_with_ai(tasks)
        self._write_cache(ranked)
        return ranked

    async def _rank_with_ai(self, tasks: list[Task]) -> list[dict]:
        """Ask Claude to rank tasks by priority. Falls back to date-sorted if AI unavailable."""
        if not self.cfg.ai.api_key:
            return [self._task_to_dict(t, rank=i + 1, reason="AI not configured; sorted by recency")
                    for i, t in enumerate(tasks)]

        # Build ranking prompt
        okr_block = ""
        if self.cfg.okrs.source == "yaml" and self.cfg.okrs.items:
            okr_lines = [f"- {o.id}: {o.title}" for o in self.cfg.okrs.items]
            okr_block = "## Current OKRs\n" + "\n".join(okr_lines) + "\n"

        task_lines = []
        for i, t in enumerate(tasks):
            snippet = (t.description or "")[:200].replace("\n", " ")
            task_lines.append(f"[{i}] id={t.id} board={t.board} labels={','.join(t.labels[:3])}\n    {t.title}\n    {snippet}")

        prompt = f"""You are the AI triage assistant for {self.cfg.org.name}.

{okr_block}
Rank the following {len(tasks)} open tasks by priority. Consider:
- OKR alignment (if OKRs provided)
- Urgency signals (labels like "bug", "critical", "urgent")
- Age (older + stale = deprioritize, older + active = maybe important)
- Dependencies mentioned

Respond with STRICT JSON only:
{{"rankings": [{{"index": 0, "rank": 1, "reason": "<20 word explanation>"}}, ...]}}

Tasks:
{chr(10).join(task_lines)}"""

        try:
            client = anthropic.Anthropic(api_key=self.cfg.ai.api_key)
            msg = client.messages.create(
                model=self.cfg.ai.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = msg.content[0].text if msg.content else ""
            # Extract JSON
            start = text.find("{")
            end = text.rfind("}")
            data = json.loads(text[start:end + 1]) if start >= 0 else {"rankings": []}
        except Exception as e:
            logger.warning("AI ranking failed, falling back to date sort: %s", e)
            return [self._task_to_dict(t, rank=i + 1, reason="AI ranking unavailable")
                    for i, t in enumerate(tasks)]

        # Apply rankings
        rank_map = {r["index"]: r for r in data.get("rankings", [])}
        ranked: list[dict] = []
        for i, t in enumerate(tasks):
            r = rank_map.get(i, {})
            ranked.append(self._task_to_dict(
                t,
                rank=r.get("rank", i + 1),
                reason=r.get("reason", ""),
            ))
        ranked.sort(key=lambda x: x["rank"])
        return ranked

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
