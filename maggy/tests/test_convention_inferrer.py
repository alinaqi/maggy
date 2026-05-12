"""Tests for LLM-based dynamic convention inference."""

from __future__ import annotations

from pathlib import Path

import pytest

from maggy.adapters.pi import PiAdapter, RunResult
from maggy.routing_rules import Convention, RoutingRules
from maggy.services.convention_inferrer import (
    collect_fingerprint,
    ensure_inferred,
    infer_conventions,
    parse_conventions,
)


def test_collect_fingerprint_includes_files(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')")
    (tmp_path / "README.md").write_text("# Hello")
    fp = collect_fingerprint(str(tmp_path))
    assert "src" in fp
    assert "README.md" in fp


def test_collect_fingerprint_excludes_noise(tmp_path: Path):
    (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
    (tmp_path / ".git" / "objects").mkdir(parents=True)
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "src").mkdir()
    fp = collect_fingerprint(str(tmp_path))
    assert "node_modules" not in fp
    assert ".git" not in fp
    assert "__pycache__" not in fp
    assert "src" in fp


def test_collect_fingerprint_includes_config(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 88\n")
    fp = collect_fingerprint(str(tmp_path))
    assert "tool.ruff" in fp


def test_collect_fingerprint_includes_git_log(tmp_path: Path):
    import subprocess
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=tmp_path, capture_output=True)
    (tmp_path / "f.txt").write_text("x")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: run prisma migrate"], cwd=tmp_path, capture_output=True)
    fp = collect_fingerprint(str(tmp_path))
    assert "prisma" in fp


def test_parse_conventions_from_llm_output():
    text = "Here are the conventions:\n- Use prisma migrate\n- Use turbo build\n"
    convs = parse_conventions(text)
    assert len(convs) == 2
    assert "prisma" in convs[0].text.lower()
    assert "turbo" in convs[1].text.lower()


def test_parse_ignores_non_convention_lines():
    text = "Analysis:\nThe project uses X.\n- Use X for builds\nEnd."
    convs = parse_conventions(text)
    assert len(convs) == 1
    assert "Use X" in convs[0].text


def test_parse_caps_at_10():
    lines = "\n".join(f"- Convention {i}" for i in range(15))
    assert len(parse_conventions(lines)) == 10


def test_parse_empty_response():
    assert parse_conventions("") == []
    assert parse_conventions("No conventions found.") == []


def _seed_project(tmp_path: Path) -> None:
    """Add a config file so fingerprint exceeds the 20-char minimum."""
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length=88\n")


@pytest.mark.asyncio
async def test_infer_calls_local_model(tmp_path: Path):
    _seed_project(tmp_path)
    pi, models_called = PiAdapter(), []

    async def fake_send(model, prompt, wd, **kw):
        models_called.append(model)
        return RunResult(model=model, success=True, output="- Use custom deploy\n")

    pi.send_prompt = fake_send
    convs = await infer_conventions(pi, str(tmp_path))
    assert models_called[0] == "local"
    assert len(convs) >= 1
    assert "custom deploy" in convs[0].text.lower()


@pytest.mark.asyncio
async def test_infer_falls_back_on_local_failure(tmp_path: Path):
    _seed_project(tmp_path)
    pi, models_called = PiAdapter(), []

    async def fake_send(model, prompt, wd, **kw):
        models_called.append(model)
        if model == "local":
            return RunResult(model=model, success=False, error="offline")
        return RunResult(model=model, success=True, output="- Use yarn\n")

    pi.send_prompt = fake_send
    convs = await infer_conventions(pi, str(tmp_path))
    assert "local" in models_called
    assert "kimi" in models_called
    assert len(convs) >= 1


@pytest.mark.asyncio
async def test_infer_returns_empty_on_all_failures(tmp_path: Path):
    _seed_project(tmp_path)
    pi = PiAdapter()

    async def fail_send(model, prompt, wd, **kw):
        return RunResult(model=model, success=False, error="down")

    pi.send_prompt = fail_send
    assert await infer_conventions(pi, str(tmp_path)) == []


@pytest.mark.asyncio
async def test_ensure_inferred_caches(tmp_path: Path):
    _seed_project(tmp_path)
    pi, call_count = PiAdapter(), [0]

    async def counting_send(model, prompt, wd, **kw):
        call_count[0] += 1
        return RunResult(model=model, success=True, output="- Use X\n")

    pi.send_prompt = counting_send
    rules = RoutingRules()
    await ensure_inferred(rules, "proj", str(tmp_path), pi)
    first_count = call_count[0]
    await ensure_inferred(rules, "proj", str(tmp_path), pi)
    assert call_count[0] == first_count


@pytest.mark.asyncio
async def test_ensure_inferred_deduplicates(tmp_path: Path):
    _seed_project(tmp_path)
    pi = PiAdapter()

    async def fake_send(model, prompt, wd, **kw):
        return RunResult(model=model, success=True, output="- Use npm install\n- Use custom script\n")

    pi.send_prompt = fake_send
    rules = RoutingRules(project_conventions={
        "proj": [Convention("Use npm install", ["all"], "auto-detected")],
    })
    await ensure_inferred(rules, "proj", str(tmp_path), pi)
    texts = [c.text for c in rules.project_conventions["proj"]]
    assert texts.count("Use npm install") == 1
    assert "Use custom script" in texts


@pytest.mark.asyncio
async def test_all_inferred_have_llm_source(tmp_path: Path):
    _seed_project(tmp_path)
    pi = PiAdapter()

    async def fake_send(model, prompt, wd, **kw):
        return RunResult(model=model, success=True, output="- Use X\n")

    pi.send_prompt = fake_send
    rules = RoutingRules()
    await ensure_inferred(rules, "proj", str(tmp_path), pi)
    llm_convs = [c for c in rules.project_conventions.get("proj", []) if c.source == "llm-inferred"]
    assert len(llm_convs) >= 1
