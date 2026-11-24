"""Screenshots stay local by default (RFC §2.6.9): only with the personal profile's
`evidence.publish_screenshots` and a passing secret scan are they uploaded to the PR."""

from __future__ import annotations

from pathlib import Path

import pytest

from maggy.harness.schema import HarnessProfile
from maggy.runner.pr_evidence.models import ArtifactRef, CriterionRow, EvidenceRecord
from maggy.runner.pr_evidence.render import render_record
from maggy.runner.pr_evidence.screens import ScreenPolicy, with_screenshots
from pr_evidence_helpers import LEAK, SHA
from worker_git_helpers import profile_data

PNG = b"\x89PNG\r\n\x1a\n\0\0pixels"


class FakeUploader:
    def __init__(self) -> None:
        self.calls: list[Path] = []

    def __call__(self, path: Path) -> str:
        self.calls.append(path)
        return f"https://uploads.invalid/{path.name}"


def _record(tmp_path: Path, shots: dict[str, bytes]) -> EvidenceRecord:
    refs = []
    for name, data in shots.items():
        (tmp_path / name).write_bytes(data)
        refs.append(ArtifactRef(name, "0" * 64, "actual"))
    row = CriterionRow("AC3", "passed", ("visual mobile",), ("visual",), tuple(refs), "ok")
    return EvidenceRecord("AWG-1", "3", SHA, (row,))


def _profile(tmp_path: Path, publish: bool) -> HarnessProfile:
    data = profile_data({"test": "true"}, ["test"])
    data["evidence"] = {"publish_screenshots": publish}
    return HarnessProfile.model_validate(data)


def test_screenshots_are_not_uploaded_by_default(tmp_path: Path) -> None:
    uploader = FakeUploader()
    record = _record(tmp_path, {"AC3-mobile.png": PNG})
    profile = HarnessProfile.model_validate(profile_data({"test": "true"}, ["test"]))
    published = with_screenshots(record, ScreenPolicy(profile, uploader, tmp_path))
    assert uploader.calls == [] and published.uploads == ()
    assert "uploads.invalid" not in render_record(published)


def test_opted_in_clean_screenshot_is_embedded(tmp_path: Path) -> None:
    uploader = FakeUploader()
    record = _record(tmp_path, {"AC3-mobile.png": PNG})
    published = with_screenshots(record, ScreenPolicy(_profile(tmp_path, True), uploader,
                                                      tmp_path))
    assert uploader.calls == [tmp_path / "AC3-mobile.png"]
    assert "![AC3-mobile.png](https://uploads.invalid/AC3-mobile.png)" in render_record(published)


def test_secret_scan_failure_excludes_the_screenshot_and_records_a_gap(tmp_path: Path) -> None:
    uploader = FakeUploader()
    record = _record(tmp_path, {"ok.png": PNG, "leak.png": PNG + LEAK.encode()})
    published = with_screenshots(record, ScreenPolicy(_profile(tmp_path, True), uploader,
                                                      tmp_path))
    assert uploader.calls == [tmp_path / "ok.png"]
    assert any("leak.png" in gap and "secret scan" in gap for gap in published.gaps)


def test_opted_in_without_an_uploader_records_a_gap(tmp_path: Path) -> None:
    record = _record(tmp_path, {"AC3-mobile.png": PNG})
    published = with_screenshots(record, ScreenPolicy(_profile(tmp_path, True), None, tmp_path))
    assert published.uploads == () and any("uploader" in gap for gap in published.gaps)


def test_publish_screenshots_is_personal_only(tmp_path: Path) -> None:
    from maggy.harness.errors import HarnessConfigError
    from maggy.harness.loader import read_layer
    layer = tmp_path / "harness.yaml"
    layer.write_text("evidence:\n  publish_screenshots: true\n")
    assert read_layer(layer, personal=True)["evidence"]["publish_screenshots"] is True
    with pytest.raises(HarnessConfigError, match="publish_screenshots"):
        read_layer(layer, personal=False)
