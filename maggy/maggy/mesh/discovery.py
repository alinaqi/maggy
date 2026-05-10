"""Peer discovery — registry with optional SQLite backing."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class PeerInfo:
    """Known mesh peer."""

    peer_id: str
    name: str
    address: str
    port: int = 8080
    org: str = ""
    last_seen: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )
    manual: bool = False


class PeerRegistry:
    """Registry of known mesh peers."""

    def __init__(self, store=None, org: str = ""):
        self._store = store
        self._org = org
        self._peers: dict[str, PeerInfo] = {}
        if store and org:
            self._load_from_store()

    def _load_from_store(self) -> None:
        for row in self._store.list_peers(self._org):
            self._peers[row["peer_id"]] = PeerInfo(
                peer_id=row["peer_id"],
                name=row["name"],
                address=row["address"],
                port=row["port"],
                org=row.get("org", self._org),
                last_seen=row.get("last_seen", ""),
                manual=bool(row.get("manual", 0)),
            )

    def register(self, peer: PeerInfo) -> None:
        if self._store and self._org:
            self._store.upsert_peer(
                peer.peer_id, peer.name,
                peer.address, peer.port, self._org,
            )
        self._peers[peer.peer_id] = peer

    def unregister(self, peer_id: str) -> bool:
        if self._store and self._org:
            self._store.remove_peer(peer_id, self._org)
        if peer_id in self._peers:
            del self._peers[peer_id]
            return True
        return False

    def get(self, peer_id: str) -> PeerInfo | None:
        return self._peers.get(peer_id)

    def list_peers(self) -> list[PeerInfo]:
        return list(self._peers.values())

    def update_seen(self, peer_id: str) -> None:
        peer = self._peers.get(peer_id)
        if peer:
            peer.last_seen = datetime.now(
                timezone.utc
            ).isoformat()
            if self._store and self._org:
                self._store.upsert_peer(
                    peer.peer_id, peer.name,
                    peer.address, peer.port, self._org,
                )

    @property
    def count(self) -> int:
        return len(self._peers)
