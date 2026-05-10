"""Tests for WebSocket server and client."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from maggy.mesh.protocol import (
    MessageType,
    MeshMessage,
    create_hello,
    create_share,
)
from maggy.mesh.transport import sign_message
from maggy.mesh.ws_server import router


# ── WS Server ──────────────────────────────────────────


def _build_app_with_mesh(tmp_dir: Path | None = None):
    """Build a FastAPI app with mesh manager wired."""
    import tempfile
    from maggy.mesh.manager import MeshManager
    from maggy.mesh.store import MeshStore

    if tmp_dir is None:
        tmp_dir = Path(tempfile.mkdtemp())
    app = FastAPI()
    store = MeshStore(tmp_dir / "mesh.db")
    cfg = SimpleNamespace(
        peer_id="server-peer",
        org_key_secret="test-secret",
        port=8080,
        tunnel_url="",
        git_discovery=False,
    )
    mgr = MeshManager(cfg, store)
    mgr.add_network("test-org")
    app.state.mesh = mgr
    app.include_router(router)
    return app, mgr


class TestWsServerNoMesh:
    def test_no_mesh_closes_connection(self):
        app = FastAPI()
        app.state.mesh = None
        app.include_router(router)
        client = TestClient(app)
        with client.websocket_connect("/ws/mesh") as ws:
            # Server should close immediately with 1008
            try:
                ws.receive_text()
                assert False, "Should have disconnected"
            except Exception:
                pass  # expected disconnect


class TestWsServerAuth:
    def test_invalid_json_closes(self):
        app, mgr = _build_app_with_mesh()
        client = TestClient(app)
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/mesh") as ws:
                ws.send_text("not-valid-json")
                ws.receive_text()

    def test_wrong_org_closes(self):
        app, mgr = _build_app_with_mesh()
        net = mgr.get_network("test-org")
        hello = create_hello("client-1", "client")
        hello.payload["org"] = "wrong-org"
        signed = sign_message(hello, net.org_key)
        client = TestClient(app)
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/mesh") as ws:
                ws.send_text(signed)
                ws.receive_text()


class TestWsServerHello:
    def test_valid_hello_gets_reply(self):
        app, mgr = _build_app_with_mesh()
        net = mgr.get_network("test-org")
        hello = create_hello("client-1", "client")
        hello.payload["org"] = "test-org"
        signed = sign_message(hello, net.org_key)
        client = TestClient(app)
        with client.websocket_connect("/ws/mesh") as ws:
            ws.send_text(signed)
            reply_raw = ws.receive_text()
            envelope = json.loads(reply_raw)
            assert "payload" in envelope
            assert "sig" in envelope


# ── WS Client ──────────────────────────────────────────


class TestMeshClient:
    def test_init(self):
        from maggy.mesh.ws_client import MeshClient
        client = MeshClient("peer-1")
        assert client.connected_count == 0

    def test_is_connected_false(self):
        from maggy.mesh.ws_client import MeshClient
        client = MeshClient("peer-1")
        assert client.is_connected("nope") is False

    @pytest.mark.asyncio
    async def test_send_no_connection(self):
        from maggy.mesh.ws_client import MeshClient
        client = MeshClient("peer-1")
        msg = create_hello("peer-1", "test")
        result = await client.send("nope", msg, "key")
        assert result is False

    @pytest.mark.asyncio
    async def test_broadcast_empty(self):
        from maggy.mesh.ws_client import MeshClient
        client = MeshClient("peer-1")
        msg = create_hello("peer-1", "test")
        count = await client.broadcast([], msg, "key")
        assert count == 0

    @pytest.mark.asyncio
    async def test_close_all_empty(self):
        from maggy.mesh.ws_client import MeshClient
        client = MeshClient("peer-1")
        await client.close_all()
        assert client.connected_count == 0
