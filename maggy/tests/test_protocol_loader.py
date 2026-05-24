"""Tests for protocol loader."""
import pytest
import tempfile
from pathlib import Path

from maggy.skills.protocol_loader import load_protocols


@pytest.fixture
def proto_dir(tmp_path):
    (tmp_path / "git-push.yaml").write_text("""
name: git-push
description: Push changes to remote
triggers:
  - push changes
  - push to git
steps:
  - name: status
    label: Check status
    cmd: git status --short
  - name: lint
    label: Python lint
    cmd: ruff check .
    optional: true
    condition: "*.py"
""")
    (tmp_path / "run-tests.yaml").write_text("""
name: run-tests
description: Run test suite
triggers:
  - run tests
steps:
  - name: test
    label: Run pytest
    cmd: python3 -m pytest tests/ -x -q
""")
    (tmp_path / "not-yaml.txt").write_text("ignore me")
    return tmp_path


class TestLoadProtocols:
    def test_loads_yaml_files(self, proto_dir):
        protos = load_protocols(proto_dir)
        assert len(protos) == 2
        names = {p.name for p in protos}
        assert names == {"git-push", "run-tests"}

    def test_parses_steps(self, proto_dir):
        protos = load_protocols(proto_dir)
        gp = next(p for p in protos if p.name == "git-push")
        assert len(gp.steps) == 2
        assert gp.steps[1].optional is True
        assert gp.steps[1].condition == "*.py"

    def test_empty_dir(self, tmp_path):
        protos = load_protocols(tmp_path)
        assert protos == []

    def test_missing_dir(self, tmp_path):
        protos = load_protocols(tmp_path / "nope")
        assert protos == []

    def test_ignores_non_yaml(self, proto_dir):
        protos = load_protocols(proto_dir)
        assert all(p.name != "not-yaml" for p in protos)
