"""Monday.com provider plugin — wraps the Monday GraphQL API."""

from __future__ import annotations

import logging
import os
from typing import Optional

import httpx
from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/provider/monday", tags=["monday"])

_provider: Optional["MondayProvider"] = None


class MondayProvider:
    name = "monday"
    API_URL = "https://api.monday.com/v2"

    def __init__(self):
        self.token = os.environ.get("MONDAY_TOKEN", "")
        self.board_id = os.environ.get("MONDAY_BOARD_ID", "")

    @property
    def configured(self) -> bool:
        return bool(self.token)

    async def get_tasks(self, limit: int = 50) -> list[dict]:
        if not self.configured:
            return []
        query = """query($boardId: [ID!], $limit: Int) {
          boards(ids: $boardId) {
            items(limit: $limit) {
              id name state
              column_values { id text }
              updated_at
            }
          }
        }"""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    self.API_URL,
                    headers={"Authorization": self.token,
                             "Content-Type": "application/json"},
                    json={"query": query, "variables": {
                        "boardId": self.board_id, "limit": min(limit, 100)}},
                )
                if resp.status_code != 200:
                    return []
                data = resp.json()
                items = data.get("data", {}).get("boards", [{}])[0].get("items", [])
                return [
                    {"id": f"monday-{i['id']}", "title": i.get("name", ""),
                     "status": "open", "source": "monday", "provider": "monday",
                     "url": f"https://protaige.monday.com/boards/{self.board_id}",
                     "updated_at": i.get("updated_at", ""),
                     "assignee": ""}
                    for i in items
                ]
        except Exception as e:
            logger.debug("Monday fetch failed: %s", e)
        return []


def register(bus, manifest):
    global _provider
    _provider = MondayProvider()
    logger.info("provider-monday: registered")


async def poll_inbox():
    if _provider:
        await _provider.get_tasks()


@router.get("/tasks")
async def list_tasks(request: Request, limit: int = 50):
    if not _provider:
        return {"tasks": [], "error": "not configured"}
    return {"tasks": await _provider.get_tasks(limit), "total": 0}


@router.get("/status")
async def status(request: Request):
    return {"configured": bool(_provider and _provider.configured),
            "board_id": _provider.board_id if _provider else ""}
