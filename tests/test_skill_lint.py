"""Unit tests for skill-lint."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

# Add scripts/ to path so we can import skill_lint
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from skill_lint import Finding, Severity
from skill_lint.frontmatter import check as fm_check, parse_frontmatter
from skill_lint.spec import check as sp_check
from skill_lint.content import check as cq_check
from skill_lint.references import check as ri_check
from skill_lint.report import format_json, format_text
from skill_lint.__main__ import main


@pytest.fixture
def skills_dir(tmp_path: Path) -> Path:
    """Create a temporary skills directory."""
    skills = tmp_path / 'skills'
    skills.mkdir()
    return skills


def _make_skill(skills_dir: Path, name: str, content: str) -> tuple[Path, Path]:
    """Create a skill directory with SKILL.md content. Returns (skill_dir, skill_path)."""
    skill_dir = skills_dir / name
    skill_dir.mkdir()
    skill_path = skill_dir / 'SKILL.md'
    skill_path.write_text(content, encoding='utf-8')
    return skill_dir, skill_path


# --- parse_frontmatter ---

class TestParseFrontmatter:
    def test_valid_frontmatter(self):
        content = '---\nname: test-skill\ndescription: A test\n---\n# Content'
        fields, end_line = parse_frontmatter(content)
        assert fields['name'] == 'test-skill'
        assert fields['description'] == 'A test'
        assert end_line == 4

    def test_no_frontmatter(self):
        content = '# Just content\nNo frontmatter here'
        fields, end_line = parse_frontmatter(content)
        assert fields == {}
        assert end_line == 0

    def test_unclosed_frontmatter(self):
        content = '---\nname: broken\n'
        fields, end_line = parse_frontmatter(content)
        assert end_line == 0

    def test_quoted_values(self):
        content = '---\nname: "quoted-name"\ndescription: \'single\'\n---\n'
        fields, _ = parse_frontmatter(content)
        assert fields['name'] == 'quoted-name'
        assert fields['description'] == 'single'


# --- FM checks ---

class TestFrontmatter:
    def test_no_frontmatter(self, skills_dir):
        _, path = _make_skill(skills_dir, 'bad-skill', '# No frontmatter\n')
        findings = fm_check(path, skills_dir / 'bad-skill', skills_dir)
        assert any(f.rule_id == 'FM001' for f in findings)

    def test_missing_name(self, skills_dir):
        _, path = _make_skill(skills_dir, 'test', '---\ndescription: hello\n---\n')
        findings = fm_check(path, skills_dir / 'test', skills_dir)
        assert any(f.rule_id == 'FM002' for f in findings)

    def test_missing_description(self, skills_dir):
        _, path = _make_skill(skills_dir, 'test', '---\nname: test\n---\n')
        findings = fm_check(path, skills_dir / 'test', skills_dir)
        assert any(f.rule_id == 'FM003' for f in findings)

    def test_name_mismatch(self, skills_dir):
        _, path = _make_skill(skills_dir, 'real-name', '---\nname: wrong-name\ndescription: x\n---\n')
        findings = fm_check(path, skills_dir / 'real-name', skills_dir)
        assert any(f.rule_id == 'FM004' for f in findings)

    def test_invalid_name_format(self, skills_dir):
        _, path = _make_skill(skills_dir, 'Test_Bad', '---\nname: Test_Bad\ndescription: x\n---\n')
        findings = fm_check(path, skills_dir / 'Test_Bad', skills_dir)
        assert any(f.rule_id == 'FM005' for f in findings)

    def test_clean_skill(self, skills_dir):
        content = (
            '---\n'
            'name: good-skill\n'
            'description: A well-formed skill\n'
            'when-to-use: When testing\n'
            'user-invocable: true\n'
            'effort: low\n'
            '---\n'
            '# Good Skill\n'
        )
        _, path = _make_skill(skills_dir, 'good-skill', content)
        findings = fm_check(path, skills_dir / 'good-skill', skills_dir)
        assert len(findings) == 0


# --- SP checks ---

class TestSpec:
    def test_missing_skill_md(self, skills_dir):
        skill_dir = skills_dir / 'empty-skill'
        skill_dir.mkdir()
        findings = sp_check(skill_dir / 'SKILL.md', skill_dir, skills_dir)
        assert any(f.rule_id == 'SP001' for f in findings)

    def test_over_500_lines(self, skills_dir):
        content = '---\nname: big\n---\n' + '\n'.join(f'line {i}' for i in range(550))
        _, path = _make_skill(skills_dir, 'big', content)
        findings = sp_check(path, skills_dir / 'big', skills_dir)
        assert any(f.rule_id == 'SP002' for f in findings)

    def test_between_300_500(self, skills_dir):
        content = '---\nname: medium\n---\n' + '\n'.join(f'line {i}' for i in range(350))
        _, path = _make_skill(skills_dir, 'medium', content)
        findings = sp_check(path, skills_dir / 'medium', skills_dir)
        assert any(f.rule_id == 'SP003' for f in findings)

    def test_inline_suppression(self, skills_dir):
        content = (
            '---\n'
            '<!-- skill-lint: disable=SP002 -->\n'
            'name: big\n'
            '---\n'
            + '\n'.join(f'line {i}' for i in range(550))
        )
        _, path = _make_skill(skills_dir, 'big', content)
        findings = sp_check(path, skills_dir / 'big', skills_dir)
        assert not any(f.rule_id == 'SP002' for f in findings)


# --- CQ checks ---

class TestContent:
    def test_ascii_art_detected(self, skills_dir):
        content = '---\nname: arty\ndescription: x\n---\n# Arty\n╔══════╗\n║ box  ║\n╚══════╝\n'
        _, path = _make_skill(skills_dir, 'arty', content)
        findings = cq_check(path, skills_dir / 'arty', skills_dir)
        assert any(f.rule_id == 'CQ001' for f in findings)

    def test_ascii_art_in_code_block_ok(self, skills_dir):
        content = '---\nname: code-art\ndescription: x\n---\n# Code\n```\n╔══════╗\n║ ok   ║\n╚══════╝\n```\n'
        _, path = _make_skill(skills_dir, 'code-art', content)
        findings = cq_check(path, skills_dir / 'code-art', skills_dir)
        assert not any(f.rule_id == 'CQ001' for f in findings)

    def test_vague_phrases(self, skills_dir):
        content = '---\nname: vague\ndescription: x\n---\n# Vague\nYou should follow best practices.\n'
        _, path = _make_skill(skills_dir, 'vague', content)
        findings = cq_check(path, skills_dir / 'vague', skills_dir)
        assert any(f.rule_id == 'CQ002' for f in findings)

    def test_filler_intensity(self, skills_dir):
        # 10 filler words in 20 lines = 50 per 100 lines (way over 2)
        filler_lines = '\n'.join(
            'This is MANDATORY and NON-NEGOTIABLE' for _ in range(10)
        )
        content = f'---\nname: filler\ndescription: x\n---\n# Filler\n{filler_lines}\n'
        _, path = _make_skill(skills_dir, 'filler', content)
        findings = cq_check(path, skills_dir / 'filler', skills_dir)
        assert any(f.rule_id == 'CQ003' for f in findings)

    def test_stale_load_ref(self, skills_dir):
        content = '---\nname: stale\ndescription: x\n---\n# Stale\n*Load with: base.md*\n'
        _, path = _make_skill(skills_dir, 'stale', content)
        findings = cq_check(path, skills_dir / 'stale', skills_dir)
        assert any(f.rule_id == 'CQ005' for f in findings)

    def test_no_h1_heading(self, skills_dir):
        content = '---\nname: headless\ndescription: x\n---\nNo heading here.\n'
        _, path = _make_skill(skills_dir, 'headless', content)
        findings = cq_check(path, skills_dir / 'headless', skills_dir)
        assert any(f.rule_id == 'CQ006' for f in findings)


# --- RI checks ---

class TestReferences:
    def test_broken_skill_ref(self, skills_dir):
        content = '---\nname: linker\ndescription: x\n---\n# Linker\nSee skills/nonexistent-skill for details.\n'
        _, path = _make_skill(skills_dir, 'linker', content)
        findings = ri_check(path, skills_dir / 'linker', skills_dir)
        assert any(f.rule_id == 'RI001' for f in findings)

    def test_valid_skill_ref(self, skills_dir):
        _make_skill(skills_dir, 'target', '---\nname: target\n---\n')
        content = '---\nname: linker\ndescription: x\n---\n# Linker\nSee skills/target for details.\n'
        _, path = _make_skill(skills_dir, 'linker', content)
        findings = ri_check(path, skills_dir / 'linker', skills_dir)
        assert not any(f.rule_id == 'RI001' for f in findings)


# --- Report ---

class TestReport:
    def test_text_format(self, skills_dir):
        findings = [
            Finding('FM001', Severity.ERROR, 'Missing frontmatter'),
            Finding('SP002', Severity.WARNING, 'Too long'),
        ]
        results = {'test-skill': findings}
        text = format_text(results)
        assert 'ERROR' in text
        assert 'WARNING' in text
        assert 'test-skill' in text

    def test_json_format(self, skills_dir):
        findings = [
            Finding('FM001', Severity.ERROR, 'Missing frontmatter'),
        ]
        results = {'test-skill': findings}
        output = format_json(results)
        data = json.loads(output)
        assert data['summary']['errors'] == 1
        assert 'test-skill' in data['skills']


# --- CLI ---

class TestCLI:
    def test_version(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main(['--version'])
        assert exc.value.code == 0

    def test_missing_dir(self):
        ret = main(['/nonexistent/path'])
        assert ret == 2

    def test_single_skill(self, skills_dir):
        content = (
            '---\n'
            'name: clean\n'
            'description: A clean skill\n'
            'when-to-use: Always\n'
            'user-invocable: true\n'
            'effort: low\n'
            '---\n'
            '# Clean Skill\n'
            '\n```python\nprint("hello")\n```\n'
        )
        _make_skill(skills_dir, 'clean', content)
        ret = main(['--skill', 'clean', str(skills_dir)])
        assert ret == 0

    def test_fail_on_warning(self, skills_dir):
        content = '---\nname: big\ndescription: x\n---\n' + '\n'.join(f'line {i}' for i in range(550))
        _make_skill(skills_dir, 'big', content)
        ret = main(['--fail-on', 'warning', '--skill', 'big', str(skills_dir)])
        assert ret == 1
