"""Generic test suite generator — auto-detects language and generates test scaffold.

Supports: Python (pytest), TypeScript/JavaScript (Vitest/Jest), React (Vitest + Testing Library).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class TestConfig:
    language: str  # python, typescript, javascript
    framework: str  # pytest, vitest, jest
    test_dir: str
    source_dir: str
    coverage_threshold: float = 0.8
    extra_deps: list[str] = field(default_factory=list)


def detect_project(project_dir: str) -> TestConfig | None:
    """Auto-detect the project type and return test configuration."""
    root = Path(project_dir).expanduser()
    if (root / "pyproject.toml").exists() or (root / "setup.py").exists():
        return TestConfig(
            language="python",
            framework="pytest",
            test_dir=str(root / "tests"),
            source_dir=str(root / "src") if (root / "src").exists() else str(root),
            extra_deps=["pytest", "pytest-cov", "pytest-asyncio"],
        )
    if (root / "package.json").exists():
        return TestConfig(
            language="typescript",
            framework="vitest",
            test_dir=str(root / "tests"),
            source_dir=str(root / "src") if (root / "src").exists() else str(root),
            extra_deps=["vitest", "@vitest/coverage-v8"],
        )
    return None


def generate_python_tests(config: TestConfig) -> list[dict]:
    """Generate pytest scaffold files."""
    files: list[dict] = []
    test_dir = Path(config.test_dir)
    # conftest.py
    files.append({
        "path": str(test_dir / "conftest.py"),
        "content": '''"""Shared test fixtures and configuration."""
import pytest


@pytest.fixture
def sample_data():
    """Provide standard test data."""
    return {"key": "value"}
''',
    })
    # __init__.py
    files.append({
        "path": str(test_dir / "__init__.py"),
        "content": "",
    })
    # Scan source files and generate test stubs
    src = Path(config.source_dir)
    py_files = list(src.rglob("*.py"))
    for pyf in py_files:
        if "__pycache__" in str(pyf) or "test" in pyf.name:
            continue
        rel = pyf.relative_to(src)
        test_name = f"test_{rel.stem}.py"
        test_path = test_dir / rel.parent / test_name
        test_path.parent.mkdir(parents=True, exist_ok=True)
        module = str(rel.with_suffix("")).replace("/", ".").replace("\\", ".")
        files.append({
            "path": str(test_path),
            "content": f'''"""Tests for {module}."""
import pytest
from {config.source_dir.split("/")[-1]}.{module.replace(".", ".")} import *  # noqa: F401, F403


def test_imports():
    """Verify the module imports cleanly."""
    pass
''',
        })
    # coverage config
    files.append({
        "path": str(Path(config.source_dir).parent / ".coveragerc"),
        "content": f"""[run]
source = src
omit = tests/*,__pycache__/*

[report]
fail_under = {int(config.coverage_threshold * 100)}
exclude_lines =
    pragma: no cover
    raise NotImplementedError
""",
    })
    return files


def generate_ts_tests(config: TestConfig) -> list[dict]:
    """Generate Vitest/Jest scaffold files."""
    root = Path(config.source_dir).parent
    files: list[dict] = []
    # vitest.config.ts
    files.append({
        "path": str(root / "vitest.config.ts"),
        "content": f'''import {{ defineConfig }} from 'vitest/config'

export default defineConfig({{
  test: {{
    globals: true,
    environment: 'node',
    coverage: {{
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      thresholds: {{
        statements: {int(config.coverage_threshold * 100)},
        branches: {int(config.coverage_threshold * 100)},
        functions: {int(config.coverage_threshold * 100)},
        lines: {int(config.coverage_threshold * 100)},
      }},
    }},
  }},
}})
''',
    })
    # Sample test
    test_dir = Path(config.test_dir)
    test_dir.mkdir(parents=True, exist_ok=True)
    files.append({
        "path": str(test_dir / "index.test.ts"),
        "content": '''import {{ describe, it, expect }} from 'vitest'

describe('project', () => {{
  it('should have valid config', () => {{
    expect(true).toBe(true)
  }})
}})
''',
    })
    return files


def generate(config: TestConfig) -> list[dict]:
    """Generate test scaffold files for the detected project."""
    if config.language == "python":
        return generate_python_tests(config)
    return generate_ts_tests(config)


def write_scaffold(project_dir: str) -> str:
    """Detect project type, generate test scaffold, and write files. Returns summary."""
    config = detect_project(project_dir)
    if not config:
        return f"No recognized project found at {project_dir}"
    files = generate(config)
    written = 0
    for f in files:
        p = Path(f["path"])
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(f["content"])
            written += 1
    parts = [
        f"Generated {written} test scaffold files",
        f"Language: {config.language}",
        f"Framework: {config.framework}",
        f"Test dir: {config.test_dir}",
        f"Coverage threshold: {config.coverage_threshold:.0%}",
    ]
    return "\n".join(parts)
