"""Resolve a bare pytest test name to exact node ids in the checkout's test files.

`pytest -k name` over the whole tree is wrong twice for a RED/GREEN proof: an unrelated
changed test file that cannot import on base turns every run into a collection error
(setup_error), and -k matches substrings (test_ac1 also selects test_ac10). So the name is
looked up (by AST) in the test files (the RED overlay first, then the tracked ones) and run as `file::name` / `file::Class::name`.
A file defining it that does not parse runs as a whole (its error is this test's error); a
name found nowhere, a node id, a file path or another runner pass through unchanged.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from maggy.harness.schema_sections import Regression
from maggy.runner.regression.invocation import Target

FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)


def target_for(config: Regression, where: tuple[Path, list[str]], test: str) -> Target:
    """`where`: (checkout, test files relative to it)."""
    if config.runner != "pytest" or "::" in test or test.endswith(".py"):
        return test
    checkout, files = where
    ids = [node for name in files if name.endswith(".py")
           for node in _node_ids(_source(checkout / name), name, test)]
    return tuple(ids) or test


def _node_ids(source: str, path: str, test: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [path] if re.search(rf"\bdef\s+{re.escape(test)}\b", source) else []
    ids = [f"{path}::{test}" for node in tree.body if _defines(node, test)]
    return ids + [f"{path}::{node.name}::{test}" for node in tree.body
                  if isinstance(node, ast.ClassDef) and any(_defines(n, test) for n in node.body)]


def _source(path: Path) -> str:
    try:
        return path.read_text(errors="replace") if path.is_file() else ""
    except OSError:
        return ""


def _defines(node: ast.stmt, test: str) -> bool:
    return isinstance(node, FUNCTIONS) and node.name == test
