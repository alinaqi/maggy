"""Transport layer — HMAC auth and org key derivation."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time

from .protocol import MeshMessage

logger = logging.getLogger(__name__)

MAX_AGE_SECONDS = 300  # 5-minute replay window


def derive_org_key(org: str, secret: str) -> str:
    """Derive per-org HMAC key from shared secret."""
    return hmac.new(
        secret.encode(), org.encode(), hashlib.sha256,
    ).hexdigest()


def compute_hmac(payload: str, key: str) -> str:
    """Compute HMAC-SHA256 for message authentication."""
    return hmac.new(
        key.encode(), payload.encode(), hashlib.sha256,
    ).hexdigest()


def verify_hmac(
    payload: str, key: str, signature: str,
) -> bool:
    """Verify HMAC signature."""
    expected = compute_hmac(payload, key)
    return hmac.compare_digest(expected, signature)


def sign_message(msg: MeshMessage, org_key: str) -> str:
    """Serialize and sign with timestamp for replay protection."""
    payload = msg.serialize()
    ts = time.time()
    sig = compute_hmac(f"{payload}:{ts}", org_key)
    return json.dumps({"payload": payload, "sig": sig, "ts": ts})


def verify_message(
    raw: str, org_key: str,
) -> MeshMessage | None:
    """Verify signature and timestamp, then deserialize."""
    try:
        envelope = json.loads(raw)
        payload = envelope["payload"]
        sig = envelope["sig"]
        ts = envelope.get("ts", 0)
    except (json.JSONDecodeError, KeyError):
        return None
    age = abs(time.time() - ts)
    if age > MAX_AGE_SECONDS:
        logger.debug("Rejected stale message (age=%.0fs)", age)
        return None
    if not verify_hmac(f"{payload}:{ts}", org_key, sig):
        return None
    return MeshMessage.deserialize(payload)
