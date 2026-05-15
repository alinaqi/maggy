"""One-shot process intelligence analysis runner."""

import asyncio
import json
import sys
import os
import logging

logging.basicConfig(level=logging.WARNING)

# Add maggy to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "maggy"))

from maggy.process import github_prs
from maggy.process.signals import (
    extract_ci_signals,
    extract_review_signals,
    extract_velocity_signals,
)
from maggy.process.patterns import (
    generate_preemptive_fixes,
    generate_routing_recs,
    identify_bottlenecks,
)
from maggy.process.report import generate_summary
from maggy.process.models import ProcessReport
from datetime import datetime, timezone


async def main():
    repo = sys.argv[1] if len(sys.argv) > 1 else "zenloopGmbH/survey-backend"
    token = os.environ.get("GITHUB_TOKEN", "")
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 200

    if not token:
        print("ERROR: Set GITHUB_TOKEN")
        sys.exit(1)

    print(f"Fetching {limit} PRs from {repo}...")
    prs = await github_prs.fetch_prs(repo=repo, token=token, limit=limit)
    print(f"Fetched {len(prs)} PRs")

    print("Extracting signals...")
    review_signals = extract_review_signals(prs)
    ci_signals = extract_ci_signals(prs)
    velocity = extract_velocity_signals(prs)

    print("Finding patterns...")
    bottlenecks = identify_bottlenecks(velocity, prs)
    fixes = generate_preemptive_fixes(review_signals, ci_signals)
    routing = generate_routing_recs(prs)

    now = datetime.now(timezone.utc).isoformat()
    report = ProcessReport(
        project_key=repo.split("/")[-1],
        generated_at=now,
        total_prs=len(prs),
        velocity=velocity,
        review_signals=review_signals,
        ci_signals=ci_signals,
        routing_recommendations=routing,
        preemptive_fixes=fixes,
    )
    report.summary = generate_summary(report)

    print("\n" + "=" * 60)
    print(report.summary)
    print("=" * 60)

    print("\n### Bottlenecks")
    for b in bottlenecks:
        print(f"  - {b}")

    print("\n### PR Details")
    for pr in sorted(prs, key=lambda p: p.number):
        ttm = f"{pr.time_to_merge_hours:.1f}h" if pr.time_to_merge_hours else "open"
        print(f"  #{pr.number} [{pr.state}] {pr.title[:50]}")
        print(f"    +{pr.additions}/-{pr.deletions} ({pr.changed_files} files) | "
              f"merge: {ttm} | reviews: {len(pr.reviews)} | "
              f"checks: {len(pr.checks)}")

    if routing:
        print("\n### Routing Recommendations")
        for r in routing:
            rec = f"  - {r['pattern']} -> {r['model']}"
            if r.get("validation"):
                rec += f" + {r['validation']}"
            print(rec)

    if fixes:
        print("\n### Pre-emptive Fixes")
        for f in fixes:
            print(f"  - {f}")

    print(f"\nAnalysis complete: {len(prs)} PRs, "
          f"{len(review_signals)} review signals, "
          f"{len(ci_signals)} CI signals")


if __name__ == "__main__":
    asyncio.run(main())
