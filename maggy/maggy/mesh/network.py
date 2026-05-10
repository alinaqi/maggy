"""Network — one isolated mesh per GitHub org."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .discovery import PeerInfo, PeerRegistry
from .quarantine import QuarantineStore
from .store import MeshStore
from .sync import SyncEngine
from .transport import derive_org_key

logger = logging.getLogger(__name__)


@dataclass
class Network:
    """A single org-scoped mesh network."""

    org: str
    org_key: str
    peers: PeerRegistry
    sync: SyncEngine
    quarantine: QuarantineStore

    def status(self) -> dict:
        return {
            "org": self.org,
            "peers": self.peers.count,
            "memories": self.sync.local_count,
            "quarantined": self.quarantine.count,
        }


def build_network(
    org: str, secret: str, store: MeshStore,
) -> Network:
    """Create an org-scoped network with shared store."""
    org_key = derive_org_key(org, secret)
    quarantine = QuarantineStore(store, org)
    return Network(
        org=org,
        org_key=org_key,
        peers=PeerRegistry(store, org),
        sync=SyncEngine(quarantine, store, org),
        quarantine=quarantine,
    )
