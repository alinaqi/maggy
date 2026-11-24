"""Phase 3 exit rig: the REAL awg CLI in a temp AWG_HOME, a temp HOME, a local bare origin, a
fake `gh` (issues for `awg sync github`, draft PRs for the runner) and a fake agent CLI.

Nothing touches the network or the real HOME. The awg binary is MAGGY_TEST_AWG_BIN, else the
sibling AWG checkout's venv, else `awg` on PATH: the first one with every runner flag wins.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from runner_exit_gh import ExitGh
from worker_git_helpers import fake_adapter_data, git, init_repo, profile_data, write_script
from worker_helpers import write_adapter

NEEDED = {("next",): ["--capabilities", "--require-capabilities"], ("submit",): ["--attempt", "--fencing-token"],
          ("evidence",): ["--commit-sha", "--meta", "--validation", "--attempt"],
          ("annotate",): ["--key"], ("annotations",): ["--json"], ("proof",): ["--json"],
          ("sync", "github"): ["--label", "--capability", "--json"]}
SIBLING = Path(__file__).resolve().parents[3].parent / "AWG" / ".venv" / "bin" / "awg"
# Writes feature.txt plus the Phase 4 plan's regression tests (RED on base: no feature.txt).
FEATURE_TESTS = ("from pathlib import Path\n\n\ndef test_discount_over_100():\n"
                 "    assert Path('feature.txt').exists()\n\n\ndef test_rule_recorded():\n"
                 "    assert Path('feature.txt').exists()\n")
AGENT = ('import json, sys\nfrom pathlib import Path\nPath("feature.txt").write_text("done\\n")\n'
         f'Path("tests").mkdir(exist_ok=True)\nPath("tests/test_feature.py").write_text({FEATURE_TESTS!r})\n'
         'with (Path(__file__).parent / "build-prompts.jsonl").open("a") as log:\n'
         '    log.write(json.dumps(sys.argv[-1]) + "\\n")\n')
CHECK = "import pathlib, sys; sys.exit(0 if pathlib.Path('feature.txt').exists() else 1)"

def _missing(binary: Path) -> list[str]:
    gaps = []
    for command, flags in NEEDED.items():
        done = subprocess.run([str(binary), *command, "--help"], capture_output=True,
                              text=True, check=False, env={**os.environ, "COLUMNS": "200"})
        gaps += [f"{' '.join(command)} {flag}" for flag in flags if flag not in done.stdout]
    return gaps


@cache
def find_awg() -> tuple[Path | None, str]:
    """(awg binary with every runner flag, or None with the reason to skip)."""
    found = [os.environ.get("MAGGY_TEST_AWG_BIN"), str(SIBLING), shutil.which("awg")]
    reasons = []
    for candidate in [Path(c) for c in found if c and Path(c).is_file()]:
        gaps = _missing(candidate)
        if not gaps:
            return candidate, ""
        reasons.append(f"{candidate} lacks {', '.join(gaps)}")
    return None, "; ".join(reasons) or "no awg CLI found (set MAGGY_TEST_AWG_BIN)"


@dataclass
class ExitRig:
    root: Path
    awg_bin: Path
    repo: Path
    remote: Path
    gh: ExitGh

    @property
    def home(self) -> Path:
        return self.root / "home"

    def awg(self, *args: str, token: str | None = None) -> object:
        """Run the real awg (owner credential unless `token` names a runner token)."""
        creds = ["--token-file", str(self.token(token))] if token else []
        done = subprocess.run([str(self.awg_bin), *creds, *args], cwd=self.root,
                              capture_output=True, text=True, check=True)
        return json.loads(done.stdout)

    def token(self, name: str) -> Path:
        return self.home / ".maggy" / "tokens" / f"{name}.token"

    def maggy_argv(self, *args: str) -> list[str]:
        return [sys.executable, "-c", "from maggy.cli import app; app()", *args]

    def maggy(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(self.maggy_argv(*args), cwd=self.root, capture_output=True,
                              text=True, check=False, timeout=300)


def environ(root: Path, bin_dir: Path, gh: Path) -> dict[str, str]:
    path = os.pathsep.join([str(bin_dir), str(gh), os.environ.get("PATH", "")])
    return {"HOME": str(root / "home"), "AWG_HOME": str(root / "awg"), "PATH": path}


def _profile(home: Path, root: Path) -> None:
    data = profile_data({"test": shlex.join([sys.executable, "-c", CHECK])}, ["test"])
    data["worker"] = {"adapter": "fakeedit", "allow_host_execution": True}
    data["validation"]["regression"] = {"command": shlex.join([sys.executable, "-m", "pytest"])}
    (home / ".maggy").mkdir(parents=True, exist_ok=True)
    (home / ".maggy" / "harness.yaml").write_text(json.dumps(data))
    write_adapter(home / ".maggy" / "adapters", fake_adapter_data(write_script(root, "agent", AGENT)))


def make_exit_rig(root: Path, awg_bin: Path) -> tuple[ExitRig, dict[str, str]]:
    """The rig plus the env to set (HOME, AWG_HOME, PATH); AWG not yet initialised."""
    bin_dir, repo, remote = root / "bin", root / "repo", root / "origin.git"
    bin_dir.mkdir(parents=True)
    (bin_dir / "awg").symlink_to(awg_bin)
    gh = ExitGh(root / "ghbin")
    (root / "home").mkdir()
    _profile(root / "home", root)
    repo.mkdir()
    init_repo(repo)
    git(root, "init", "-q", "--bare", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-q", "origin", "main")
    rig = ExitRig(root, bin_dir / "awg", repo, remote, gh)
    return rig, environ(root, bin_dir, gh.root)
