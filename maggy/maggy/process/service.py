"""Process Intelligence service — orchestrates the full pipeline.

Pipeline: fetch PRs -> extract signals -> find patterns -> generate report.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from maggy.config import MaggyConfig

from . import github_prs
from .models import ProcessReport
from .patterns import (
    generate_preemptive_fixes,
    generate_routing_recs,
    identify_bottlenecks,
)
from .report import format_health_metrics, generate_summary
from .signals import (
    extract_ci_signals,
    extract_review_signals,
    extract_velocity_signals,
)
from .store import ProcessStore

logger = logging.getLogger(__name__)


class ProcessService:
    """Orchestrates process intelligence analysis."""

    def __init__(self, cfg: MaggyConfig):
        self.cfg = cfg
        db_path = (
            Path(cfg.storage.path).expanduser().parent
            / "process.db"
        )
        self.store = ProcessStore(db_path)

    async def analyze(
        self, project_key: str
    ) -> ProcessReport:
        """Run full analysis pipeline for a project."""
        repo = self._resolve_repo(project_key)
        token = self.cfg.issue_tracker.github.token

        if not token:
            raise ValueError("GITHUB_TOKEN not configured")
        if not repo:
            raise ValueError(
                f"No repo found for project '{project_key}'"
            )

        logger.info(
            "Analyzing %s — fetching PRs from %s",
            project_key, repo,
        )

        # 1. Fetch PRs
        prs = await github_prs.fetch_prs(
            repo=repo, token=token, limit=200
        )
        logger.info("Fetched %d PRs from %s", len(prs), repo)

        # 2. Extract signals
        review_signals = extract_review_signals(prs)
        ci_signals = extract_ci_signals(prs)
        velocity = extract_velocity_signals(prs)

        # 3. Find patterns
        bottlenecks = identify_bottlenecks(velocity, prs)
        fixes = generate_preemptive_fixes(
            review_signals, ci_signals
        )
        routing = generate_routing_recs(prs)

        # 4. Build report
        now = datetime.now(timezone.utc).isoformat()
        report = ProcessReport(
            project_key=project_key,
            generated_at=now,
            total_prs=len(prs),
            velocity=velocity,
            review_signals=review_signals,
            ci_signals=ci_signals,
            routing_recommendations=routing,
            preemptive_fixes=fixes,
        )
        report.summary = generate_summary(report)

        # 5. Persist
        self.store.save_report(report)
        logger.info(
            "Process report saved for %s: %d PRs, "
            "%d review signals, %d CI signals",
            project_key, len(prs),
            len(review_signals), len(ci_signals),
        )

        return report

    def get_report(self, project_key: str) -> dict | None:
        """Get latest cached report."""
        return self.store.load_latest_report(project_key)

    def get_health(self, project_key: str) -> dict | None:
        """Get health metrics from latest report."""
        raw = self.store.load_latest_report(project_key)
        if not raw:
            return None
        return raw

    def _resolve_repo(
        self, project_key: str
    ) -> str | None:
        """Map project_key to GitHub org/repo."""
        gh = self.cfg.issue_tracker.github
        for repo in gh.repos:
            slug = repo.split("/")[-1]
            if slug == project_key:
                return repo
        # Try matching against codebase keys
        for cb in self.cfg.codebases:
            if cb.key == project_key:
                slug = Path(cb.path).name
                if gh.org:
                    return f"{gh.org}/{slug}"
        return None
