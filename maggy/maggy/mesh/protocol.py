"""Message types and serialization for Mesh protocol."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum


class MessageType(str, Enum):
    HELLO = "hello"
    SHARE = "share"
    REQUEST = "request"
    RESPONSE = "response"
    QUARANTINE = "quarantine"
    PROMOTE = "promote"
    HEARTBEAT = "heartbeat"


@dataclass
class MeshMessage:
    """A message in the Mesh protocol."""

    msg_type: str
    sender_id: str
    payload: dict = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )

    def serialize(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def deserialize(cls, data: str) -> MeshMessage:
        d = json.loads(data)
        return cls(**d)


def create_hello(peer_id: str, name: str) -> MeshMessage:
    return MeshMessage(
        msg_type=MessageType.HELLO,
        sender_id=peer_id,
        payload={"name": name},
    )


def create_share(
    peer_id: str, key: str, content: dict,
) -> MeshMessage:
    return MeshMessage(
        msg_type=MessageType.SHARE,
        sender_id=peer_id,
        payload={
            "key": key,
            "memory_type": content.get("memory_type", ""),
            "content": content,
        },
    )
