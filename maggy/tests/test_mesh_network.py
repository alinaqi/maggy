"""Tests for mesh network layer: org scanner, git discovery, transport, network, manager, publisher."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from maggy.mesh.discovery import PeerInfo


# ── Org Scanner ─────────────────────────────────────────


class TestEffectiveOrgs:
    def test_merge_scanned_and_manual(self):
        from maggy.mesh.org_scanner import effective_orgs
        result = effective_orgs(
            ["protaige", "edubites"], ["alinaqi"], [],
        )
        assert result == ["alinaqi", "edubites", "protaige"]

    def test_excludes_orgs(self):
        from maggy.mesh.org_scanner import effective_orgs
        result = effective_orgs(
            ["protaige", "edubites", "alinaqi"],
            [], ["edubites"],
        )
        assert "edubites" not in result
        assert len(result) == 2

    def test_deduplicates(self):
        from maggy.mesh.org_scanner import effective_orgs
        result = effective_orgs(
            ["protaige"], ["protaige"], [],
        )
        assert result == ["protaige"]

    def test_empty_inputs(self):
        from maggy.mesh.org_scanner import effective_orgs
        assert effective_orgs([], [], []) == []


# ── Transport ───────────────────────────────────────────


class TestDeriveOrgKey:
    def test_different_orgs_produce_different_keys(self):
        from maggy.mesh.transport import derive_org_key
        k1 = derive_org_key("protaige", "secret")
        k2 = derive_org_key("edubites", "secret")
        assert k1 != k2

    def test_deterministic(self):
        from maggy.mesh.transport import derive_org_key
        k1 = derive_org_key("protaige", "secret")
        k2 = derive_org_key("protaige", "secret")
        assert k1 == k2

    def test_returns_hex_string(self):
        from maggy.mesh.transport import derive_org_key
        key = derive_org_key("org", "secret")
        assert len(key) == 64  # SHA-256 hex


class TestSignVerify:
    def test_roundtrip(self):
        from maggy.mesh.transport import sign_message, verify_message
        from maggy.mesh.protocol import create_hello
        msg = create_hello("peer-1", "tester")
        signed = sign_message(msg, "test-key")
        result = verify_message(signed, "test-key")
        assert result is not None
        assert result.sender_id == "peer-1"

    def test_wrong_key_fails(self):
        from maggy.mesh.transport import sign_message, verify_message
        from maggy.mesh.protocol import create_hello
        msg = create_hello("peer-1", "tester")
        signed = sign_message(msg, "correct-key")
        result = verify_message(signed, "wrong-key")
        assert result is None

    def test_invalid_json_fails(self):
        from maggy.mesh.transport import verify_message
        result = verify_message("not-json", "key")
        assert result is None


# ── Network ─────────────────────────────────────────────


class TestBuildNetwork:
    def test_creates_network(self, tmp_path: Path):
        from maggy.mesh.network import build_network
        from maggy.mesh.store import MeshStore
        store = MeshStore(tmp_path / "mesh.db")
        net = build_network("protaige", "secret", store)
        assert net.org == "protaige"
        assert net.org_key != ""

    def test_isolated_org_keys(self, tmp_path: Path):
        from maggy.mesh.network import build_network
        from maggy.mesh.store import MeshStore
        store = MeshStore(tmp_path / "mesh.db")
        n1 = build_network("protaige", "secret", store)
        n2 = build_network("edubites", "secret", store)
        assert n1.org_key != n2.org_key

    def test_status_returns_counts(self, tmp_path: Path):
        from maggy.mesh.network import build_network
        from maggy.mesh.store import MeshStore
        store = MeshStore(tmp_path / "mesh.db")
        net = build_network("test-org", "secret", store)
        status = net.status()
        assert status["org"] == "test-org"
        assert status["peers"] == 0
        assert status["memories"] == 0
        assert status["quarantined"] == 0


# ── Manager ─────────────────────────────────────────────


def _make_cfg(**overrides):
    """Build a minimal MeshConfig-like SimpleNamespace."""
    defaults = {
        "peer_id": "test-peer",
        "org_key_secret": "secret",
        "port": 8080,
        "tunnel_url": "",
        "git_discovery": True,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestMeshManager:
    def test_add_and_get_network(self, tmp_path: Path):
        from maggy.mesh.manager import MeshManager
        from maggy.mesh.store import MeshStore
        store = MeshStore(tmp_path / "mesh.db")
        mgr = MeshManager(_make_cfg(), store)
        net = mgr.add_network("protaige")
        assert net.org == "protaige"
        assert mgr.get_network("protaige") is net

    def test_missing_network_returns_none(self, tmp_path: Path):
        from maggy.mesh.manager import MeshManager
        from maggy.mesh.store import MeshStore
        store = MeshStore(tmp_path / "mesh.db")
        mgr = MeshManager(_make_cfg(), store)
        assert mgr.get_network("nope") is None

    def test_list_networks(self, tmp_path: Path):
        from maggy.mesh.manager import MeshManager
        from maggy.mesh.store import MeshStore
        store = MeshStore(tmp_path / "mesh.db")
        mgr = MeshManager(_make_cfg(), store)
        mgr.add_network("org-a")
        mgr.add_network("org-b")
        nets = mgr.list_networks()
        assert len(nets) == 2

    def test_total_peers_across_networks(self, tmp_path: Path):
        from maggy.mesh.manager import MeshManager
        from maggy.mesh.store import MeshStore
        store = MeshStore(tmp_path / "mesh.db")
        mgr = MeshManager(_make_cfg(), store)
        net = mgr.add_network("org-a")
        net.peers.register(PeerInfo(
            peer_id="p1", name="peer1",
            address="ws://1", org="org-a",
        ))
        assert mgr.total_peers == 1

    def test_resolve_address_tunnel(self, tmp_path: Path):
        from maggy.mesh.manager import MeshManager
        from maggy.mesh.store import MeshStore
        store = MeshStore(tmp_path / "mesh.db")
        cfg = _make_cfg(tunnel_url="wss://bore.pub/xyz")
        mgr = MeshManager(cfg, store)
        assert mgr._resolve_address() == "wss://bore.pub/xyz"

    def test_resolve_address_local(self, tmp_path: Path):
        from maggy.mesh.manager import MeshManager
        from maggy.mesh.store import MeshStore
        store = MeshStore(tmp_path / "mesh.db")
        mgr = MeshManager(_make_cfg(), store)
        assert "127.0.0.1:8080" in mgr._resolve_address()


# ── Publisher ───────────────────────────────────────────


class TestPublisher:
    def test_collect_scores_skips_low_count(self):
        from maggy.mesh.publisher import collect_scores
        routing = SimpleNamespace(
            get_heatmap=lambda: [
                {"model": "m1", "task_type": "fix", "count": 2},
            ],
        )
        result = collect_scores(routing, "peer-1")
        assert len(result) == 0

    def test_collect_scores_includes_high_count(self):
        from maggy.mesh.publisher import collect_scores
        routing = SimpleNamespace(
            get_heatmap=lambda: [
                {"model": "m1", "task_type": "fix", "count": 10},
            ],
        )
        result = collect_scores(routing, "peer-1")
        assert len(result) == 1
        assert result[0].memory_type == "score"

    def test_collect_gaps(self):
        from maggy.mesh.publisher import collect_gaps
        forge = SimpleNamespace(
            get_gaps=lambda: [{"name": "slack-notify"}],
        )
        result = collect_gaps(forge, "peer-1")
        assert len(result) == 1
        assert result[0].key == "gap:slack-notify"

    def test_collect_policies_filters_severity(self):
        from maggy.mesh.publisher import collect_policies
        rec = SimpleNamespace(
            severity="action",
            category="routing",
            message="Fix it",
            suggestion="Do this",
        )
        rec_info = SimpleNamespace(
            severity="info",
            category="mem",
            message="FYI",
            suggestion="N/A",
        )
        report = SimpleNamespace(
            recommendations=[rec, rec_info],
        )
        introspector = SimpleNamespace(get_report=lambda: report)
        result = collect_policies(introspector, "peer-1")
        assert len(result) == 1  # only action severity

    def test_collect_all_none_services(self):
        from maggy.mesh.publisher import collect_all_shares
        state = SimpleNamespace()
        result = collect_all_shares(state, "peer-1")
        assert result == []


# ── Git Discovery (mocked HTTP) ─────────────────────────


class TestGitDiscovery:
    @pytest.mark.asyncio
    async def test_ensure_repo_exists(self):
        from maggy.mesh.git_discovery import ensure_mesh_repo
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(
            return_value=mock_client,
        )
        mock_client.__aexit__ = AsyncMock()
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await ensure_mesh_repo("org", "token")
        assert result is True

    @pytest.mark.asyncio
    async def test_ensure_repo_creates_new(self):
        from maggy.mesh.git_discovery import ensure_mesh_repo
        not_found = AsyncMock()
        not_found.status_code = 404
        created = AsyncMock()
        created.status_code = 201
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=not_found)
        mock_client.post = AsyncMock(return_value=created)
        mock_client.__aenter__ = AsyncMock(
            return_value=mock_client,
        )
        mock_client.__aexit__ = AsyncMock()
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await ensure_mesh_repo("org", "token")
        assert result is True

    @pytest.mark.asyncio
    async def test_read_peers_empty(self):
        from maggy.mesh.git_discovery import read_peers
        not_found = AsyncMock()
        not_found.status_code = 404
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=not_found)
        mock_client.__aenter__ = AsyncMock(
            return_value=mock_client,
        )
        mock_client.__aexit__ = AsyncMock()
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await read_peers("org", "token")
        assert result == []

    @pytest.mark.asyncio
    async def test_announce_success(self):
        from maggy.mesh.git_discovery import Announcement, announce
        not_found = AsyncMock()
        not_found.status_code = 404
        success = AsyncMock()
        success.status_code = 201
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=not_found)
        mock_client.put = AsyncMock(return_value=success)
        mock_client.__aenter__ = AsyncMock(
            return_value=mock_client,
        )
        mock_client.__aexit__ = AsyncMock()
        ann = Announcement(
            peer_id="peer-1", name="node",
            address="ws://x",
        )
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await announce("org", ann, "tok")
        assert result is True

    @pytest.mark.asyncio
    async def test_remove_announcement(self):
        from maggy.mesh.git_discovery import remove_announcement
        found = AsyncMock()
        found.status_code = 200
        found.json = lambda: {"sha": "abc123"}
        deleted = AsyncMock()
        deleted.status_code = 200
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=found)
        mock_client.delete = AsyncMock(return_value=deleted)
        mock_client.__aenter__ = AsyncMock(
            return_value=mock_client,
        )
        mock_client.__aexit__ = AsyncMock()
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await remove_announcement(
                "org", "peer-1", "tok",
            )
        assert result is True


# ── Promote Flow ────────────────────────────────────────


class TestPromoteFlow:
    def test_promote_accepts_into_sync(self, tmp_path: Path):
        from maggy.mesh.network import build_network
        from maggy.mesh.store import MeshStore
        store = MeshStore(tmp_path / "mesh.db")
        net = build_network("org-a", "secret", store)
        net.quarantine.quarantine(
            key="score:m1:fix",
            source="peer-2",
            reason="low confidence",
            content={"model": "m1"},
            memory_type="score",
        )
        assert net.quarantine.count == 1
        assert net.sync.local_count == 0
        ok = net.sync.promote_from_quarantine("score:m1:fix")
        assert ok is True
        assert net.quarantine.count == 0
        assert net.sync.local_count == 1
        mem = net.sync.get_local("score:m1:fix")
        assert mem is not None
        assert mem.content == {"model": "m1"}

    def test_promote_nonexistent_returns_false(
        self, tmp_path: Path,
    ):
        from maggy.mesh.network import build_network
        from maggy.mesh.store import MeshStore
        store = MeshStore(tmp_path / "mesh.db")
        net = build_network("org-a", "secret", store)
        ok = net.sync.promote_from_quarantine("nope")
        assert ok is False


# ── Replay Protection ──────────────────────────────────


class TestReplayProtection:
    def test_stale_message_rejected(self):
        import time
        from maggy.mesh.transport import (
            sign_message,
            verify_message,
        )
        from maggy.mesh.protocol import create_hello
        msg = create_hello("peer-1", "tester")
        signed = sign_message(msg, "key")
        # Tamper timestamp to make it old
        import json
        envelope = json.loads(signed)
        envelope["ts"] = time.time() - 600
        sig_field = envelope["sig"]
        tampered = json.dumps(envelope)
        result = verify_message(tampered, "key")
        assert result is None


# ── SQLite Reload on Init ──────────────────────────────


class TestSqliteReload:
    def test_peers_reload_from_store(self, tmp_path: Path):
        from maggy.mesh.discovery import PeerInfo, PeerRegistry
        from maggy.mesh.store import MeshStore
        store = MeshStore(tmp_path / "mesh.db")
        reg1 = PeerRegistry(store, "org-a")
        reg1.register(PeerInfo(
            peer_id="p1", name="Alice",
            address="ws://a", org="org-a",
        ))
        # Create new registry from same store — should reload
        reg2 = PeerRegistry(store, "org-a")
        assert reg2.count == 1
        assert reg2.get("p1") is not None

    def test_sync_reload_from_store(self, tmp_path: Path):
        from maggy.mesh.memory import SharedMemory
        from maggy.mesh.quarantine import QuarantineStore
        from maggy.mesh.store import MeshStore
        from maggy.mesh.sync import SyncEngine
        store = MeshStore(tmp_path / "mesh.db")
        q1 = QuarantineStore(store, "org-a")
        s1 = SyncEngine(q1, store, "org-a")
        s1.sync_incoming([SharedMemory(
            key="k1", memory_type="score",
            content={"x": 1}, source_peer="p1",
        )])
        # New engine from same store — should reload
        q2 = QuarantineStore(store, "org-a")
        s2 = SyncEngine(q2, store, "org-a")
        assert s2.local_count == 1
