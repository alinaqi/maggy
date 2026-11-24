"""Secret scan before an artifact is referenced in a PR (RFC §2.6.9)."""

from __future__ import annotations

from pathlib import Path

from maggy.runner.verify.secret_scan import referable, scan_file

GITHUB_TOKEN = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
HIGH_ENTROPY = "Zx9Qw7Er5Ty3Ui1Op8As6Df4Gh2Jk0LmNbVcXz"


def _write(tmp_path: Path, name: str, body: str | bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(body if isinstance(body, bytes) else body.encode())
    return path


def test_clean_log_passes(tmp_path: Path) -> None:
    log = _write(tmp_path, "ok.log", "3 passed in 0.2s at 1f0e9c2d3b4a5f60718293a4b5c6d7e8f9a0b1c2\n")
    assert scan_file(log, {}) == []


def test_token_patterns_entropy_and_env_values_are_found(tmp_path: Path) -> None:
    assert scan_file(_write(tmp_path, "a.log", f"token={GITHUB_TOKEN}\n"), {})
    assert scan_file(_write(tmp_path, "b.log", f"value {HIGH_ENTROPY}\n"), {})
    env = {"STRIPE_SECRET": "hunter2-plain-words", "PATH": "/usr/bin"}
    found = scan_file(_write(tmp_path, "c.log", "dump: hunter2-plain-words\n"), env)
    assert found and all("hunter2" not in finding for finding in found)


def test_binary_artifact_is_scanned_for_patterns_only(tmp_path: Path) -> None:
    png = _write(tmp_path, "shot.png", b"\x89PNG\r\n\x1a\n\x00" + bytes(range(256)) * 4)
    assert scan_file(png, {}) == []
    leaky = _write(tmp_path, "leak.png", b"\x89PNG\x00tEXt" + GITHUB_TOKEN.encode())
    assert scan_file(leaky, {})


def test_referable_withholds_flagged_artifacts(tmp_path: Path) -> None:
    clean = _write(tmp_path, "clean.log", "all good\n")
    leaky = _write(tmp_path, "leaky.log", f"Authorization: Bearer {GITHUB_TOKEN}\n")
    allowed, withheld = referable([clean, leaky], {})
    assert allowed == [clean] and list(withheld) == [leaky]
    assert GITHUB_TOKEN not in " ".join(withheld[leaky])
