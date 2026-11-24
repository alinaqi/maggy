"""Vision reviewer (RFC §2.5 Verify, §2.6.9): verdict mapping, no backend -> PENDING (never
PASS), and external backends refused unless `evidence.external_review` lists the provider."""

from __future__ import annotations

from pathlib import Path

import pytest

from maggy.harness.schema import HarnessProfile
from maggy.runner.verify.ollama_vision import OllamaVision
from maggy.runner.verify.vision import VisionRequest, review_criterion
from verify_helpers import FakeVision
from worker_git_helpers import profile_data


def _request(tmp_path: Path) -> VisionRequest:
    (tmp_path / "ref.png").write_bytes(b"ref")
    (tmp_path / "cand.png").write_bytes(b"cand")
    return VisionRequest(criterion_id="AC3", criterion_text="message under the field",
                         reference=tmp_path / "ref.png", candidate=tmp_path / "cand.png",
                         viewport="mobile")


def _profile(external: object = False) -> HarnessProfile:
    data = profile_data()
    data["evidence"] = {"external_review": external}
    return HarnessProfile.model_validate(data)


@pytest.mark.parametrize(("answer", "verdict"), [("pass", "PASS"), ("fail", "FAIL"),
                                                 ("uncertain", "PENDING")])
def test_fake_backend_verdicts_map_to_gate_verdicts(tmp_path: Path, answer: str,
                                                    verdict: str) -> None:
    backend = FakeVision(answer)
    outcome = review_criterion([backend], _profile(), _request(tmp_path))
    assert outcome.verdict == verdict and outcome.backend == "fake-vision"
    assert backend.calls[0].viewport == "mobile" and backend.calls[0].criterion_id == "AC3"
    assert "coupon error" in outcome.detail


def test_no_backend_is_pending_not_pass(tmp_path: Path) -> None:
    outcome = review_criterion([], _profile(), _request(tmp_path))
    assert outcome.verdict == "PENDING" and "no vision backend" in outcome.detail


def test_unavailable_ollama_is_pending(tmp_path: Path) -> None:
    ollama = OllamaVision(url="http://127.0.0.1:9")
    assert ollama.available() is False
    assert review_criterion([ollama], _profile(), _request(tmp_path)).verdict == "PENDING"


def test_external_backend_refused_unless_opted_in(tmp_path: Path) -> None:
    external = FakeVision("pass", provider="openai")
    refused = review_criterion([external], _profile(), _request(tmp_path))
    assert refused.verdict == "PENDING" and external.calls == []
    assert "openai" in refused.detail and "external_review" in refused.detail
    other = review_criterion([external], _profile(["anthropic"]), _request(tmp_path))
    assert other.verdict == "PENDING" and external.calls == []
    allowed = review_criterion([external], _profile(["openai"]), _request(tmp_path))
    assert allowed.verdict == "PASS" and len(external.calls) == 1


def test_external_review_is_personal_only(tmp_path: Path) -> None:
    from maggy.harness.errors import HarnessConfigError
    from maggy.harness.loader import read_layer
    layer = tmp_path / "harness.yaml"
    layer.write_text("evidence:\n  external_review: [openai]\n")
    assert read_layer(layer, personal=True)["evidence"]["external_review"] == ["openai"]
    with pytest.raises(HarnessConfigError, match="external_review"):
        read_layer(layer)
