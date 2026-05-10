"""Mesh P2P REST endpoints — data operations."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .auth import check_auth

router = APIRouter(prefix="/api/mesh", tags=["mesh"])


class AddPeerRequest(BaseModel):
    org: str
    peer_id: str
    name: str = ""
    address: str = ""
    port: int = Field(default=8080, ge=1, le=65535)


class PromoteRequest(BaseModel):
    org: str
    key: str


@router.get("/status")
async def mesh_status(
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict:
    """Return mesh status across all networks."""
    check_auth(request, x_api_key)
    mesh = request.app.state.mesh
    if not mesh:
        return {"enabled": False, "peers": 0}
    return {
        "enabled": True,
        "peers": mesh.total_peers,
        "networks": mesh.list_networks(),
    }


@router.get("/networks")
async def list_networks(
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict:
    """List all org-scoped mesh networks."""
    check_auth(request, x_api_key)
    mesh = request.app.state.mesh
    if not mesh:
        return {"networks": []}
    return {"networks": mesh.list_networks()}


@router.get("/peers")
async def list_peers(
    request: Request,
    org: str = "",
    x_api_key: str | None = Header(None),
) -> dict:
    """List peers, optionally filtered by org."""
    check_auth(request, x_api_key)
    mesh = request.app.state.mesh
    if not mesh:
        return JSONResponse(
            {"error": "mesh not enabled"}, status_code=503,
        )
    if org:
        net = mesh.get_network(org)
        if not net:
            return JSONResponse(
                {"error": f"unknown org: {org}"},
                status_code=404,
            )
        return {
            "peers": [asdict(p) for p in net.peers.list_peers()],
        }
    peers = []
    for status in mesh.list_networks():
        net = mesh.get_network(status["org"])
        if net:
            peers.extend(
                asdict(p) for p in net.peers.list_peers()
            )
    return {"peers": peers}


@router.post("/peers")
async def add_peer(
    request: Request,
    body: AddPeerRequest,
    x_api_key: str | None = Header(None),
) -> dict:
    """Manually add a peer to a network."""
    check_auth(request, x_api_key)
    mesh = request.app.state.mesh
    if not mesh:
        return JSONResponse(
            {"error": "mesh not enabled"}, status_code=503,
        )
    net = mesh.get_network(body.org)
    if not net:
        return JSONResponse(
            {"error": f"unknown org: {body.org}"},
            status_code=404,
        )
    from maggy.mesh.discovery import PeerInfo
    net.peers.register(PeerInfo(
        peer_id=body.peer_id,
        name=body.name,
        address=body.address,
        port=body.port,
        org=body.org,
        manual=True,
    ))
    return {"status": "added", "peer_id": body.peer_id}


@router.get("/quarantine")
async def quarantine_list(
    request: Request,
    org: str = "",
    x_api_key: str | None = Header(None),
) -> dict:
    """List quarantined items for an org."""
    check_auth(request, x_api_key)
    mesh = request.app.state.mesh
    if not mesh:
        return JSONResponse(
            {"error": "mesh not enabled"}, status_code=503,
        )
    if not org:
        return JSONResponse(
            {"error": "org parameter required"},
            status_code=422,
        )
    net = mesh.get_network(org)
    if not net:
        return JSONResponse(
            {"error": f"unknown org: {org}"},
            status_code=404,
        )
    items = [asdict(e) for e in net.quarantine.list_all()]
    return {"items": items}


@router.post("/promote")
async def promote(
    request: Request,
    body: PromoteRequest,
    x_api_key: str | None = Header(None),
) -> dict:
    """Promote a quarantined item into shared memories."""
    check_auth(request, x_api_key)
    mesh = request.app.state.mesh
    if not mesh:
        return JSONResponse(
            {"error": "mesh not enabled"}, status_code=503,
        )
    net = mesh.get_network(body.org)
    if not net:
        return JSONResponse(
            {"error": f"unknown org: {body.org}"},
            status_code=404,
        )
    ok = net.sync.promote_from_quarantine(body.key)
    return {"promoted": ok}
