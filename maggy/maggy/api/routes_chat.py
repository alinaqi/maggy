"""Chat send routes — message streaming via SSE."""
from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from maggy.api.auth import check_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _require_chat(request: Request):
    chat = getattr(request.app.state, "chat", None)
    if chat is None:
        raise HTTPException(status_code=503, detail="Chat service not available.")
    return chat


class SendMessageRequest(BaseModel):
    message: str


class RoutedMessageRequest(BaseModel):
    message: str
    blast_score: int | None = None
    task_type: str | None = None
    allowed_models: list[str] | None = None


@router.post("/sessions/{session_id}/send")
async def send_message(
    request: Request, session_id: str,
    body: SendMessageRequest, x_api_key: str | None = Header(None),
):
    """Send a message and stream response via SSE."""
    check_auth(request, x_api_key)
    chat = _require_chat(request)
    s = chat.get_session(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message required")
    budget = getattr(request.app.state, "budget", None)

    async def event_stream():
        async for chunk in chat.send(session_id, body.message):
            if budget and chunk.get("type") == "result":
                _record_spend(budget, chunk)
            yield f"data: {json.dumps(chunk)}\n\n"
        yield 'data: {"type": "done"}\n\n'

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/sessions/{session_id}/send-routed")
async def send_routed(
    request: Request, session_id: str,
    body: RoutedMessageRequest, x_api_key: str | None = Header(None),
):
    """Send a message routed through blast-score engine."""
    check_auth(request, x_api_key)
    chat = _require_chat(request)
    s = chat.get_session(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message required")
    routing = getattr(request.app.state, "routing", None)
    budget = getattr(request.app.state, "budget", None)

    async def event_stream():
        from maggy.services.chat_router import RoutedChat
        decision = None
        blueprints = getattr(request.app.state, "blueprints", None)
        pkey = getattr(s, "project_key", "")
        if routing:
            rc = RoutedChat(routing, budget, blueprints, pkey)
            decision = await rc.decide(body.message, body.blast_score, body.task_type)
            allowed = body.allowed_models
            if allowed and decision.model not in allowed:
                decision.model = allowed[0]
                decision.reason = f"restricted to {','.join(allowed)}"
            yield f"data: {json.dumps(_routing_meta(decision))}\n\n"
        # Try executor for actionable messages; fall back to chat on error
        executor = getattr(request.app.state, "executor", None)
        executor_failed = False
        if decision and executor:
            from maggy.services.chat_executor_bridge import executor_stream, should_route_to_executor
            if should_route_to_executor(decision):
                exec_wd = getattr(s, "repo_dir", "") or s.working_dir
                async for chunk in executor_stream(executor, decision, body.message, exec_wd):
                    yield f"data: {json.dumps(chunk)}\n\n"
                    if chunk.get("type") == "error":
                        executor_failed = True
                if not executor_failed:
                    yield 'data: {"type": "done"}\n\n'
                    return
                fb = {"type": "agent_status", "status": "Falling back to claude..."}
                yield f"data: {json.dumps(fb)}\n\n"
        # Chat path (primary or fallback)
        had_error, review_content, tool_events = False, "", []
        effective_msg = body.message
        if decision and decision.blueprint_context:
            effective_msg = f"[Blueprint]\n{decision.blueprint_context}\n[/Blueprint]\n\n{body.message}"
        async for chunk in chat.send(session_id, effective_msg):
            if budget and chunk.get("type") == "result":
                _record_spend(budget, chunk)
            ct = chunk.get("type", "")
            if ct == "error":
                had_error = True
            if ct == "tool_use":
                tool_events.append(chunk.get("tool", "unknown"))
            if ct in ("text", "result"):
                review_content += chunk.get("content", "")
            yield f"data: {json.dumps(chunk)}\n\n"
        _record_outcome(routing, decision, had_error)
        _record_review(request, decision, review_content)
        _capture_bp(request, body.message, decision, tool_events, had_error, pkey)
        yield 'data: {"type": "done"}\n\n'

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _routing_meta(d) -> dict:
    return {"type": "routing", "model": d.model, "blast": d.blast, "task_type": d.task_type, "reason": d.reason}


def _record_spend(budget, chunk: dict) -> None:
    cost, in_t, out_t = chunk.get("cost_usd", 0), chunk.get("input_tokens", 0), chunk.get("output_tokens", 0)
    if cost or in_t or out_t:
        budget.record_spend("anthropic", "claude", cost, in_t, out_t)


def _record_outcome(routing, decision, had_error: bool) -> None:
    if not routing or not decision:
        return
    routing.record_outcome(decision.model, decision.task_type, decision.blast, 0.0 if had_error else 1.0)


def _record_review(request: Request, decision, content: str) -> None:
    if not decision or not content or getattr(decision, "task_type", "") != "review":
        return
    scores = getattr(request.app.state, "reviewer_scores", None)
    if not scores:
        return
    from maggy.services.reviewer_eval import evaluate_review
    evaluate_review(getattr(decision, "model", "unknown"), content, "review", scores)


def _capture_bp(request, message, decision, tool_events, had_error, pkey) -> None:
    if had_error or not decision or not tool_events:
        return
    bp_store = getattr(request.app.state, "blueprints", None)
    if not bp_store:
        return
    from maggy.blueprint_extract import capture_blueprint
    capture_blueprint(message, decision.task_type, tool_events, decision.model, bp_store, pkey)


_UPLOAD_DIR = Path(tempfile.gettempdir()) / "maggy-uploads"
_MAX_UPLOAD = 10 * 1024 * 1024  # 10 MB


@router.post("/upload")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    x_api_key: str | None = Header(None),
) -> dict:
    """Upload a file for use in chat messages."""
    check_auth(request, x_api_key)
    data = await file.read(_MAX_UPLOAD + 1)
    if len(data) > _MAX_UPLOAD:
        raise HTTPException(status_code=413, detail="File too large (10 MB max)")
    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = _UPLOAD_DIR / (file.filename or "upload")
    dest.write_bytes(data)
    return {"path": str(dest), "name": file.filename, "size": len(data)}
