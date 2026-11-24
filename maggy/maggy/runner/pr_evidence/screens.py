"""Screenshots stay local unless the personal profile opts in (RFC §2.6.9).

With `evidence.publish_screenshots: true` (personal-only) and an uploader, each referenced
screenshot is secret-scanned again right before upload; one that fails is not uploaded and
becomes a verification gap. Without the opt-in nothing is uploaded and nothing is embedded.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from maggy.harness.schema import HarnessProfile
from maggy.runner.pr_evidence.models import EvidenceRecord
from maggy.runner.verify.secret_scan import referable

IMAGES = (".png", ".jpg", ".jpeg", ".webp")
NO_UPLOADER = ("evidence.publish_screenshots is on but no screenshot uploader is "
               "configured: screenshots stay local")


@dataclass(frozen=True)
class ScreenPolicy:
    profile: HarnessProfile
    uploader: Callable[[Path], str] | None
    root: Path  # the record's artifact paths are relative to it


def with_screenshots(record: EvidenceRecord, policy: ScreenPolicy) -> EvidenceRecord:
    if not policy.profile.evidence.publish_screenshots:
        return record
    if policy.uploader is None:
        return replace(record, gaps=(*record.gaps, NO_UPLOADER))
    shots = [policy.root / ref.path for row in record.rows for ref in row.artifacts
             if Path(ref.path).suffix.lower() in IMAGES]
    allowed, withheld = referable(list(dict.fromkeys(shots)), os.environ)
    uploads = tuple((str(p.relative_to(policy.root)), policy.uploader(p)) for p in allowed)
    gaps = tuple(f"screenshot {p.relative_to(policy.root)} not uploaded: secret scan "
                 f"({', '.join(found)})" for p, found in withheld.items())
    return replace(record, uploads=uploads, gaps=(*record.gaps, *gaps))
