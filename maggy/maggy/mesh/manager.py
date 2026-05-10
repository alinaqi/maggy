"""MeshManager — orchestrates multiple org networks."""

from __future__ import annotations

import logging
import platform

from .discovery import PeerInfo
from .git_discovery import (
    Announcement,
    announce,
    ensure_mesh_repo,
    read_peers,
)
from .network import Network, build_network
from .store import MeshStore

logger = logging.getLogger(__name__)


class MeshManager:
    """Manages all org-scoped mesh networks."""

    def __init__(self, cfg, store: MeshStore) -> None:
        self._cfg = cfg
        self._store = store
        self._networks: dict[str, Network] = {}

    def add_network(self, org: str) -> Network:
        net = build_network(
            org, self._cfg.org_key_secret, self._store,
        )
        self._networks[org] = net
        return net

    def get_network(self, org: str) -> Network | None:
        return self._networks.get(org)

    def list_networks(self) -> list[dict]:
        return [n.status() for n in self._networks.values()]

    @property
    def total_peers(self) -> int:
        return sum(
            n.peers.count for n in self._networks.values()
        )

    async def discover(self, token: str) -> dict:
        """Read peers from git for all networks."""
        result: dict[str, int] = {}
        for org, net in self._networks.items():
            if not self._cfg.git_discovery:
                continue
            peers = await read_peers(org, token)
            for p in peers:
                pid = p.get("peer_id", "")
                if pid == self._cfg.peer_id:
                    continue
                net.peers.register(PeerInfo(
                    peer_id=pid,
                    name=p.get("name", ""),
                    address=p.get("address", ""),
                    port=p.get("port", 8080),
                    org=org,
                ))
            result[org] = len(peers)
        return result

    async def announce_all(self, token: str) -> dict:
        """Announce self to all org mesh repos."""
        address = self._resolve_address()
        result: dict[str, bool] = {}
        for org in self._networks:
            ann = Announcement(
                peer_id=self._cfg.peer_id,
                name=platform.node(),
                address=address,
                port=self._cfg.port,
                org=org,
            )
            ok = await announce(org, ann, token)
            result[org] = ok
        return result

    async def setup_repos(self, token: str) -> dict:
        """Create mesh repos for all networks."""
        result: dict[str, bool] = {}
        for org in self._networks:
            ok = await ensure_mesh_repo(org, token)
            result[org] = ok
        return result

    def _resolve_address(self) -> str:
        if self._cfg.tunnel_url:
            return self._cfg.tunnel_url
        return f"ws://127.0.0.1:{self._cfg.port}"
