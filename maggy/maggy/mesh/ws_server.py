"""WebSocket server endpoint for mesh communication."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .protocol import MessageType, MeshMessage, create_hello
from .transport import sign_message, verify_message

logger = logging.getLogger(__name__)

router = APIRouter()

HELLO_TIMEOUT = 10.0
MSG_TIMEOUT = 300.0
MAX_INVALID = 5


@router.websocket("/ws/mesh")
async def mesh_ws(websocket: WebSocket) -> None:
    """Accept mesh peer connections."""
    await websocket.accept()
    manager = getattr(websocket.app.state, "mesh", None)
    if not manager:
        await websocket.close(code=1008, reason="Mesh not enabled")
        return
    try:
        await _handle_connection(websocket, manager)
    except WebSocketDisconnect:
        logger.debug("Mesh peer disconnected")
    except asyncio.TimeoutError:
        logger.debug("Mesh peer timed out")
    except Exception as exc:
        logger.warning("Mesh WS error: %s", exc)


async def _handle_connection(websocket, manager) -> None:
    """Authenticate and enter message loop."""
    raw = await asyncio.wait_for(
        websocket.receive_text(), timeout=HELLO_TIMEOUT,
    )
    org, msg = _authenticate(raw, manager)
    if not msg or not org:
        await websocket.close(code=1008, reason="Auth failed")
        return
    net = manager.get_network(org)
    if not net:
        await websocket.close(code=1008, reason="Unknown org")
        return
    peers = [
        {"peer_id": p.peer_id, "address": p.address, "port": p.port}
        for p in net.peers.list_peers()
    ]
    reply = create_hello(manager._cfg.peer_id, "server")
    reply.payload["peers"] = peers
    signed = sign_message(reply, net.org_key)
    await websocket.send_text(signed)
    await _message_loop(websocket, net)


async def _message_loop(websocket, net) -> None:
    """Rate-limited message receive loop."""
    invalid_count = 0
    while True:
        data = await asyncio.wait_for(
            websocket.receive_text(), timeout=MSG_TIMEOUT,
        )
        incoming = verify_message(data, net.org_key)
        if not incoming:
            invalid_count += 1
            if invalid_count >= MAX_INVALID:
                logger.warning("Too many invalid messages")
                break
            continue
        invalid_count = 0
        await _dispatch(incoming, net)


def _authenticate(
    raw: str, manager,
) -> tuple[str | None, MeshMessage | None]:
    """Try to authenticate a HELLO message."""
    try:
        envelope = json.loads(raw)
        payload_str = envelope.get("payload", "")
        msg = MeshMessage.deserialize(payload_str)
        org = msg.payload.get("org", "")
    except (json.JSONDecodeError, KeyError, TypeError):
        return None, None
    if msg.msg_type != MessageType.HELLO:
        return None, None
    net = manager.get_network(org)
    if not net:
        return None, None
    verified = verify_message(raw, net.org_key)
    if not verified:
        return None, None
    return org, verified


async def _dispatch(msg: MeshMessage, net) -> None:
    """Handle incoming message by type."""
    if msg.msg_type == MessageType.SHARE:
        from .memory import SharedMemory
        mem = SharedMemory(
            key=msg.payload.get("key", ""),
            memory_type=msg.payload.get("memory_type", ""),
            content=msg.payload.get("content", {}),
            source_peer=msg.sender_id,
            confidence=msg.payload.get("confidence", 1.0),
        )
        net.sync.sync_incoming([mem])
    elif msg.msg_type == MessageType.HEARTBEAT:
        net.peers.update_seen(msg.sender_id)
