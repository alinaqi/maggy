"""Git-based peer discovery via GitHub Contents API."""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass

import httpx

from .discovery import PeerInfo

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
REPO_NAME = "maggy-mesh"
TIMEOUT = 15


@dataclass
class Announcement:
    """Peer data for git-based discovery."""

    peer_id: str
    name: str
    address: str
    port: int = 8080
    org: str = ""


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def ensure_mesh_repo(
    org: str, token: str, private: bool = True,
) -> bool:
    """Create {org}/maggy-mesh repo if it doesn't exist."""
    async with httpx.AsyncClient(
        timeout=TIMEOUT, headers=_headers(token),
    ) as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{org}/{REPO_NAME}",
        )
        if resp.status_code == 200:
            return True
        resp = await client.post(
            f"{GITHUB_API}/orgs/{org}/repos",
            json={
                "name": REPO_NAME,
                "private": private,
                "description": "Maggy mesh peer discovery",
                "auto_init": True,
            },
        )
        if resp.status_code in (200, 201):
            logger.info("Created %s/%s", org, REPO_NAME)
            return True
        logger.warning(
            "Failed to create %s/%s: %s",
            org, REPO_NAME, resp.status_code,
        )
        return False


async def announce(
    org: str, ann: Announcement, token: str,
) -> bool:
    """Write peer announcement to {org}/maggy-mesh."""
    content = json.dumps({
        "peer_id": ann.peer_id,
        "name": ann.name,
        "address": ann.address,
        "port": ann.port,
        "org": org,
    }, indent=2)
    encoded = base64.b64encode(content.encode()).decode()
    path = f"peers/{ann.peer_id}.json"

    async with httpx.AsyncClient(
        timeout=TIMEOUT, headers=_headers(token),
    ) as client:
        existing = await client.get(
            f"{GITHUB_API}/repos/{org}/{REPO_NAME}"
            f"/contents/{path}",
        )
        sha = ""
        if existing.status_code == 200:
            sha = existing.json().get("sha", "")
        body: dict = {
            "message": f"announce {ann.peer_id}",
            "content": encoded,
        }
        if sha:
            body["sha"] = sha
        resp = await client.put(
            f"{GITHUB_API}/repos/{org}/{REPO_NAME}"
            f"/contents/{path}",
            json=body,
        )
        if resp.status_code not in (200, 201):
            logger.warning(
                "Announce %s to %s failed: %s",
                ann.peer_id, org, resp.status_code,
            )
        return resp.status_code in (200, 201)


async def read_peers(
    org: str, token: str,
) -> list[dict]:
    """Read all peer announcements from {org}/maggy-mesh."""
    async with httpx.AsyncClient(
        timeout=TIMEOUT, headers=_headers(token),
    ) as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{org}/{REPO_NAME}"
            "/contents/peers",
        )
        if resp.status_code != 200:
            return []
        items = resp.json()
        if not isinstance(items, list):
            return []
        peers: list[dict] = []
        for item in items:
            name = item.get("name", "")
            if not name.endswith(".json"):
                continue
            peer = _decode_peer(item)
            if peer:
                peers.append(peer)
        return peers


def _decode_peer(item: dict) -> dict | None:
    """Decode peer from directory listing content."""
    raw_content = item.get("content")
    if not raw_content:
        return None
    try:
        return json.loads(base64.b64decode(raw_content))
    except (json.JSONDecodeError, Exception):
        return None


async def remove_announcement(
    org: str, peer_id: str, token: str,
) -> bool:
    """Remove peer file on shutdown (best-effort)."""
    path = f"peers/{peer_id}.json"
    async with httpx.AsyncClient(
        timeout=TIMEOUT, headers=_headers(token),
    ) as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{org}/{REPO_NAME}"
            f"/contents/{path}",
        )
        if resp.status_code != 200:
            return False
        sha = resp.json().get("sha", "")
        resp = await client.delete(
            f"{GITHUB_API}/repos/{org}/{REPO_NAME}"
            f"/contents/{path}",
            json={
                "message": f"remove {peer_id}",
                "sha": sha,
            },
        )
        return resp.status_code == 200
