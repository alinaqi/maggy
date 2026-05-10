"""Async WebSocket client for mesh peer connections."""

from __future__ import annotations

import asyncio
import logging

from .discovery import PeerInfo
from .protocol import MeshMessage, create_hello
from .transport import sign_message, verify_message

logger = logging.getLogger(__name__)

RECONNECT_DELAY = 10.0


class MeshClient:
    """Maintains WebSocket connections to known peers."""

    def __init__(self, peer_id: str) -> None:
        self._peer_id = peer_id
        self._connections: dict[str, object] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    async def connect(
        self, peer: PeerInfo, org: str, org_key: str,
    ) -> bool:
        """Connect to a peer and send HELLO."""
        try:
            import websockets
            url = f"{peer.address}/ws/mesh"
            ws = await websockets.connect(url)
            hello = create_hello(self._peer_id, "client")
            hello.payload["org"] = org
            signed = sign_message(hello, org_key)
            await ws.send(signed)
            reply_raw = await ws.recv()
            reply = verify_message(reply_raw, org_key)
            if not reply:
                await ws.close()
                return False
            self._connections[peer.peer_id] = ws
            logger.info("Connected to peer %s", peer.peer_id)
            return True
        except Exception as exc:
            logger.debug("Connect to %s failed: %s", peer.peer_id, exc)
            return False

    async def send(
        self, peer_id: str, msg: MeshMessage, org_key: str,
    ) -> bool:
        """Send message to a connected peer."""
        ws = self._connections.get(peer_id)
        if not ws:
            return False
        try:
            signed = sign_message(msg, org_key)
            await ws.send(signed)
            return True
        except Exception as exc:
            logger.debug("Send to %s failed: %s", peer_id, exc)
            self._connections.pop(peer_id, None)
            return False

    async def broadcast(
        self, peers: list[str], msg: MeshMessage, org_key: str,
    ) -> int:
        """Send to all specified peers. Returns success count."""
        sent = 0
        for pid in peers:
            if await self.send(pid, msg, org_key):
                sent += 1
        return sent

    async def close_all(self) -> None:
        """Close all connections."""
        for ws in self._connections.values():
            try:
                await ws.close()
            except Exception:
                pass
        self._connections.clear()
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()

    @property
    def connected_count(self) -> int:
        return len(self._connections)

    def is_connected(self, peer_id: str) -> bool:
        return peer_id in self._connections
