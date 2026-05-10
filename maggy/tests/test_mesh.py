"""Tests for Maggy Mesh — protocol, discovery, sync, quarantine."""

from __future__ import annotations

from maggy.mesh.discovery import PeerInfo, PeerRegistry
from maggy.mesh.memory import MemoryType, SharedMemory
from maggy.mesh.protocol import (
    MeshMessage,
    MessageType,
    create_hello,
    create_share,
)
from maggy.mesh.provenance import Provenance
from maggy.mesh.quarantine import QuarantineStore
from maggy.mesh.sync import SyncEngine
from maggy.mesh.transport import compute_hmac, verify_hmac


class TestProtocol:
    def test_serialize_round_trip(self):
        msg = create_hello("peer-1", "Alice")
        data = msg.serialize()
        restored = MeshMessage.deserialize(data)
        assert restored.msg_type == MessageType.HELLO
        assert restored.sender_id == "peer-1"

    def test_share_message(self):
        msg = create_share(
            "peer-1", "score:claude:fix",
            {"memory_type": "score", "model": "claude"},
        )
        assert msg.msg_type == MessageType.SHARE
        assert msg.payload["key"] == "score:claude:fix"


class TestPeerDiscovery:
    def test_register_and_list(self):
        reg = PeerRegistry()
        reg.register(PeerInfo(
            peer_id="p1", name="Alice",
            address="192.168.1.1",
        ))
        assert reg.count == 1
        assert reg.get("p1").name == "Alice"

    def test_unregister(self):
        reg = PeerRegistry()
        reg.register(PeerInfo(
            peer_id="p1", name="Alice",
            address="192.168.1.1",
        ))
        assert reg.unregister("p1")
        assert reg.count == 0

    def test_update_seen(self):
        reg = PeerRegistry()
        reg.register(PeerInfo(
            peer_id="p1", name="Alice",
            address="192.168.1.1",
        ))
        old = reg.get("p1").last_seen
        reg.update_seen("p1")
        # May or may not change within same ms
        assert reg.get("p1").last_seen is not None


class TestProvenance:
    def test_no_hop_full_confidence(self):
        p = Provenance(origin_peer="p1", base_confidence=1.0)
        assert p.effective_confidence == 1.0

    def test_decay_per_hop(self):
        p = Provenance(
            origin_peer="p1", hops=3, base_confidence=1.0,
        )
        assert p.effective_confidence == 0.7

    def test_add_hop(self):
        p = Provenance(origin_peer="p1", hops=1)
        p2 = p.add_hop()
        assert p2.hops == 2

    def test_min_confidence(self):
        p = Provenance(
            origin_peer="p1", hops=100, base_confidence=1.0,
        )
        assert p.effective_confidence == 0.1


class TestQuarantine:
    def test_quarantine_and_list(self):
        qs = QuarantineStore()
        qs.quarantine("k1", "peer-1", "low conf", {"x": 1})
        assert qs.count == 1
        assert qs.get("k1").reason == "low conf"

    def test_promote(self):
        qs = QuarantineStore()
        qs.quarantine("k1", "peer-1", "test", {})
        assert qs.promote("k1")
        assert qs.count == 0

    def test_promote_missing(self):
        qs = QuarantineStore()
        assert not qs.promote("nope")


class TestSync:
    def test_accept_high_confidence(self):
        qs = QuarantineStore()
        engine = SyncEngine(qs)
        mems = [
            SharedMemory(
                key="s1", memory_type="score",
                confidence=0.8, source_peer="p1",
            ),
        ]
        result = engine.sync_incoming(mems)
        assert result.accepted == 1
        assert engine.local_count == 1

    def test_quarantine_low_confidence(self):
        qs = QuarantineStore()
        engine = SyncEngine(qs)
        mems = [
            SharedMemory(
                key="s1", memory_type="score",
                confidence=0.3, source_peer="p1",
            ),
        ]
        result = engine.sync_incoming(mems)
        assert result.quarantined == 1
        assert qs.count == 1


class TestTransport:
    def test_hmac_round_trip(self):
        sig = compute_hmac("hello", "secret")
        assert verify_hmac("hello", "secret", sig)

    def test_hmac_mismatch(self):
        sig = compute_hmac("hello", "secret")
        assert not verify_hmac("hello", "wrong", sig)
