"""Config loader for Maggy — reads ~/.maggy/config.yaml with env overrides."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path(os.environ.get("MAGGY_HOME", "~/.maggy")).expanduser()
CONFIG_PATH = CONFIG_DIR / "config.yaml"


@dataclass
class GitHubConfig:
    org: str = ""
    repos: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    token: str = ""


@dataclass
class AsanaConfig:
    workspace_id: str = ""
    boards: dict[str, str] = field(default_factory=dict)
    token: str = ""


@dataclass
class LinearConfig:
    workspace: str = ""
    token: str = ""


@dataclass
class IssueTrackerConfig:
    provider: str = "github"
    github: GitHubConfig = field(default_factory=GitHubConfig)
    asana: AsanaConfig = field(default_factory=AsanaConfig)
    linear: LinearConfig = field(default_factory=LinearConfig)


@dataclass
class CodebaseConfig:
    path: str
    key: str


@dataclass
class OKRItem:
    id: str
    title: str
    keywords: list[str] = field(default_factory=list)


@dataclass
class OKRConfig:
    source: str = "skip"
    items: list[OKRItem] = field(default_factory=list)


@dataclass
class CompetitorsConfig:
    categories: list[str] = field(default_factory=list)
    seed: list[str] = field(default_factory=list)


@dataclass
class AIConfig:
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-5-20250929"
    api_key: str = ""
    max_budget_usd_per_execute: float = 5.0


@dataclass
class StorageConfig:
    backend: str = "sqlite"
    path: str = "~/.maggy/maggy.db"


@dataclass
class DashboardConfig:
    host: str = "127.0.0.1"
    port: int = 8080
    auth_mode: str = "local"
    api_key: str = ""


@dataclass
class OrgConfig:
    name: str = "Your Org"
    domain: str = ""


@dataclass
class BootstrapConfig:
    path: str = ""


@dataclass
class ModelTierConfig:
    name: str = ""
    provider: str = ""
    model: str = ""
    complexity_range: list[int] = field(default_factory=lambda: [0, 10])
    strengths: list[str] = field(default_factory=list)
    cost_per_1k: float = 0.0


@dataclass
class BudgetConfig:
    daily_limit_usd: float = 10.0
    warning_threshold: float = 0.8


@dataclass
class RoutingConfig:
    mode: str = "dynamic"
    tiers: list[ModelTierConfig] = field(default_factory=list)


@dataclass
class MeshConfig:
    enabled: bool = False
    peer_id: str = ""
    port: int = 8080
    org_key_secret: str = ""
    orgs: list[str] = field(default_factory=list)
    exclude_orgs: list[str] = field(default_factory=list)
    manual_peers: list[str] = field(default_factory=list)
    tunnel_url: str = ""
    git_discovery: bool = True
    share_interval: int = 600


@dataclass
class HeartbeatConfig:
    enabled: bool = True
    history_interval: int = 1800
    engram_interval: int = 3600
    improve_interval: int = 3600
    mesh_interval: int = 300


@dataclass
class MaggyConfig:
    org: OrgConfig = field(default_factory=OrgConfig)
    issue_tracker: IssueTrackerConfig = field(default_factory=IssueTrackerConfig)
    codebases: list[CodebaseConfig] = field(default_factory=list)
    competitors: CompetitorsConfig = field(default_factory=CompetitorsConfig)
    okrs: OKRConfig = field(default_factory=OKRConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    dashboard: DashboardConfig = field(default_factory=DashboardConfig)
    bootstrap: BootstrapConfig = field(default_factory=BootstrapConfig)
    budget: BudgetConfig = field(default_factory=BudgetConfig)
    routing: RoutingConfig = field(default_factory=RoutingConfig)
    mesh: MeshConfig = field(default_factory=MeshConfig)
    heartbeat: HeartbeatConfig = field(default_factory=HeartbeatConfig)

    def codebase_paths(self) -> dict[str, Path]:
        """Return {key: expanded_path} for all configured codebases."""
        return {c.key: Path(c.path).expanduser() for c in self.codebases}

    def resolve_bootstrap_path(self) -> Path | None:
        """Find Maggy install. Checks config, then ~/.claude/.bootstrap-dir."""
        if self.bootstrap.path:
            return Path(self.bootstrap.path).expanduser()
        marker = Path.home() / ".claude" / ".bootstrap-dir"
        if marker.exists():
            return Path(marker.read_text().strip()).expanduser()
        return None


def _merge_env(cfg: MaggyConfig) -> MaggyConfig:
    """Override config with env vars where defined. Env wins over file."""
    cfg.issue_tracker.github.token = os.environ.get("GITHUB_TOKEN", cfg.issue_tracker.github.token)
    # Fall back to git credential helper if no env var
    if not cfg.issue_tracker.github.token:
        cfg.issue_tracker.github.token = _git_credential_token()
    cfg.issue_tracker.asana.token = os.environ.get("ASANA_API_KEY", cfg.issue_tracker.asana.token)
    cfg.issue_tracker.linear.token = os.environ.get("LINEAR_API_KEY", cfg.issue_tracker.linear.token)
    cfg.ai.api_key = os.environ.get("ANTHROPIC_API_KEY", cfg.ai.api_key)
    cfg.dashboard.api_key = os.environ.get("MAGGY_API_KEY", cfg.dashboard.api_key)
    cfg.mesh.org_key_secret = os.environ.get("MAGGY_MESH_SECRET", cfg.mesh.org_key_secret)
    return cfg


def _git_credential_token() -> str:
    """Read GitHub token from git credential helper."""
    from maggy.discovery import discover_git_token
    return discover_git_token()


def _from_dict(data: dict[str, Any]) -> MaggyConfig:
    """Build MaggyConfig from loaded YAML dict. Tolerates missing sections."""
    it_raw = data.get("issue_tracker") or {}
    tracker = IssueTrackerConfig(
        provider=it_raw.get("provider", "github"),
        github=GitHubConfig(**(it_raw.get("github") or {})),
        asana=AsanaConfig(**(it_raw.get("asana") or {})),
        linear=LinearConfig(**(it_raw.get("linear") or {})),
    )

    okr_raw = data.get("okrs") or {}
    okrs = OKRConfig(
        source=okr_raw.get("source", "skip"),
        items=[OKRItem(**item) for item in (okr_raw.get("items") or [])],
    )

    routing_raw = data.get("routing") or {}
    routing = RoutingConfig(
        mode=routing_raw.get("mode", "dynamic"),
        tiers=[
            ModelTierConfig(**t)
            for t in (routing_raw.get("tiers") or [])
        ],
    )

    return MaggyConfig(
        org=OrgConfig(**(data.get("org") or {})),
        issue_tracker=tracker,
        codebases=[CodebaseConfig(**c) for c in (data.get("codebases") or [])],
        competitors=CompetitorsConfig(**(data.get("competitors") or {})),
        okrs=okrs,
        ai=AIConfig(**(data.get("ai") or {})),
        storage=StorageConfig(**(data.get("storage") or {})),
        dashboard=DashboardConfig(**(data.get("dashboard") or {})),
        bootstrap=BootstrapConfig(**(data.get("bootstrap") or {})),
        budget=BudgetConfig(**(data.get("budget") or {})),
        routing=routing,
        mesh=MeshConfig(**(data.get("mesh") or {})),
        heartbeat=HeartbeatConfig(**(data.get("heartbeat") or {})),
    )


_CACHED: MaggyConfig | None = None


def _has_provider_credentials(cfg: MaggyConfig) -> bool:
    """Check if config has full provider credentials."""
    if cfg.issue_tracker.provider == "github":
        gh = cfg.issue_tracker.github
        return bool(gh.org and gh.repos and gh.token)
    if cfg.issue_tracker.provider == "asana":
        az = cfg.issue_tracker.asana
        return bool(az.workspace_id and az.token)
    return False


def _has_cli_history(
    home: Path | None = None,
) -> bool:
    """Check if any CLI data directories exist."""
    root = home or Path.home()
    for d in (".claude", ".codex", ".kimi"):
        if (root / d).exists():
            return True
    return False


def auto_configure(
    home: Path | None = None,
    persist: bool = True,
) -> MaggyConfig:
    """Build config from auto-discovery."""
    from maggy.discovery import full_discovery, infer_github_org
    result = full_discovery(home)
    cfg = MaggyConfig(
        codebases=[
            CodebaseConfig(path=r["path"], key=r["key"])
            for r in result.repos
        ],
    )
    if result.github_org:
        cfg.issue_tracker.github.org = result.github_org
    # Auto-populate repos matching the primary org
    if result.github_org:
        cfg.issue_tracker.github.repos = _repos_for_org(
            result.repos, result.github_org,
        )
    if persist:
        save(cfg)
    return _merge_env(cfg)


def _repos_for_org(
    repos: list[dict], org: str,
) -> list[str]:
    """Filter repo names belonging to a GitHub org."""
    from maggy.discovery import infer_github_org
    matched: list[str] = []
    for repo in repos:
        repo_org = infer_github_org(Path(repo["path"]))
        if repo_org == org:
            matched.append(repo["key"])
    return matched


def load(refresh: bool = False) -> MaggyConfig:
    """Load config from ~/.maggy/config.yaml, with env var overrides. Cached."""
    global _CACHED
    if _CACHED is not None and not refresh:
        return _CACHED

    if not CONFIG_PATH.exists():
        _CACHED = _merge_env(MaggyConfig())
        return _CACHED

    with open(CONFIG_PATH) as f:
        data = yaml.safe_load(f) or {}
    _CACHED = _merge_env(_from_dict(data))
    return _CACHED


def save(cfg: MaggyConfig) -> None:
    """Write config back to ~/.maggy/config.yaml."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    # Convert dataclass → dict, strip empty tokens (they come from env)
    from dataclasses import asdict
    d = asdict(cfg)
    # Don't persist tokens — those come from env
    for section in ("github", "asana", "linear"):
        d.get("issue_tracker", {}).get(section, {}).pop("token", None)
    d.get("ai", {}).pop("api_key", None)
    d.get("dashboard", {}).pop("api_key", None)
    with open(CONFIG_PATH, "w") as f:
        yaml.safe_dump(d, f, sort_keys=False)
    global _CACHED
    _CACHED = None  # force reload on next load()


def is_configured() -> bool:
    """Check if Maggy has enough to be useful.

    Full mode: provider credentials present.
    Local mode: CLI history dirs exist (zero-config).
    """
    if CONFIG_PATH.exists():
        cfg = load(refresh=True)
        if _has_provider_credentials(cfg):
            return True
    if _has_cli_history():
        return True
    return False
