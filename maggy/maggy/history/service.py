"""History analysis service — orchestrates the full pipeline."""

from __future__ import annotations

import logging
from pathlib import Path

from .analyzer import build_report
from .models import HistoryReport
from .parsers.claude import ClaudeHistoryParser
from .parsers.codex import CodexHistoryParser
from .parsers.kimi import KimiHistoryParser
from .store import HistoryStore

logger = logging.getLogger(__name__)


class HistoryService:
    """Orchestrates session history analysis."""

    def __init__(
        self,
        db_path: Path | None = None,
        cli_dirs: dict[str, Path] | None = None,
    ):
        db = db_path or (
            Path.home() / ".maggy" / "history.db"
        )
        self._store = HistoryStore(db)
        dirs = cli_dirs or {}
        self._parsers = [
            ClaudeHistoryParser(dirs.get("claude")),
            CodexHistoryParser(dirs.get("codex")),
            KimiHistoryParser(dirs.get("kimi")),
        ]

    def analyze(self) -> HistoryReport:
        """Parse all CLIs, analyze, store report."""
        all_sessions = self._collect_sessions()
        report = build_report(all_sessions)

        if all_sessions:
            self._store.save_sessions(all_sessions)
        self._store.save_report(report)

        logger.info(
            "History analysis: %d sessions, %d prompts, "
            "%d providers",
            report.total_sessions,
            report.total_prompts,
            len(report.providers),
        )
        return report

    def _collect_sessions(self) -> list:
        """Collect sessions from all available parsers."""
        sessions = []
        for parser in self._parsers:
            if not parser.is_available():
                logger.debug(
                    "%s not available, skipping",
                    parser.provider,
                )
                continue
            try:
                parsed = parser.parse_sessions()
                sessions.extend(parsed)
                logger.info(
                    "Parsed %d sessions from %s",
                    len(parsed), parser.provider,
                )
            except Exception:
                logger.exception(
                    "Failed to parse %s history",
                    parser.provider,
                )
        return sessions

    def get_report(self) -> dict | None:
        """Get latest cached report."""
        return self._store.load_latest_report()

    def get_sessions(
        self, provider: str | None = None,
    ) -> list[dict]:
        """Get stored session records."""
        return self._store.load_sessions(
            provider=provider,
        )

    def available_providers(self) -> list[str]:
        """List which CLIs are available."""
        return [
            p.provider for p in self._parsers
            if p.is_available()
        ]
