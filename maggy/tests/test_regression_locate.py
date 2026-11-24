"""A bare pytest test name resolves to exact node ids in the candidate's changed test files,
so an unrelated broken test file or a name prefix cannot change the RED/GREEN verdict."""

from __future__ import annotations

from pathlib import Path

from maggy.harness.schema_sections import Regression
from maggy.runner.regression.locate import target_for

PYTEST = Regression(runner="pytest")
SOURCE = ("def test_ac1():\n    assert 1\n\n\ndef test_ac10():\n    assert 1\n\n\n"
          "class TestCoupon:\n    async def test_ac1(self):\n        assert 1\n")


def _files(tmp_path: Path) -> list[str]:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_a.py").write_text(SOURCE)
    (tmp_path / "tests/test_b.py").write_text("from app.newmod import x\n")
    (tmp_path / "tests/broken.spec.js").write_text("test_ac1")
    return ["tests/broken.spec.js", "tests/test_a.py", "tests/test_b.py"]


def test_bare_name_becomes_exact_node_ids(tmp_path: Path) -> None:
    files = _files(tmp_path)
    assert target_for(PYTEST, (tmp_path, files), "test_ac1") == (
        "tests/test_a.py::test_ac1", "tests/test_a.py::TestCoupon::test_ac1")


def test_node_ids_files_other_runners_and_unknown_names_pass_through(tmp_path: Path) -> None:
    files = _files(tmp_path)
    for given in ("tests/test_a.py::test_ac1", "tests/test_a.py", "test_unknown"):
        assert target_for(PYTEST, (tmp_path, files), given) == given
    assert target_for(Regression(runner="node-test"), (tmp_path, files), "test_ac1") == "test_ac1"


def test_unparsable_file_defining_the_name_runs_that_file(tmp_path: Path) -> None:
    (tmp_path / "test_x.py").write_text("def test_ac1(:\n")
    assert target_for(PYTEST, (tmp_path, ["test_x.py"]), "test_ac1") == ("test_x.py",)
