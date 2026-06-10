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
                cost = chunk.get("cost_usd", 0)
                in_t = chunk.get("input_tokens", 0)
                out_t = chunk.get("output_tokens", 0)
                if cost or in_t or out_t:
                    budget.record_spend("anthropic", "claude", cost, in_t, out_t)
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

    async def event_stream():
        pkey = getattr(s, "project_key", "")
        wd = getattr(s, "repo_dir", "") or s.working_dir

        proto = _match_protocol(body.message)
        if proto:
            async for ev in _run_protocol(proto, wd, body.message, request, s):
                yield f"data: {json.dumps(ev)}\n\n"
            _persist_pipeline_messages(
                request, session_id, s, body.message,
                f"[Protocol: {proto.name} completed]",
            )
            yield 'data: {"type": "done"}\n\n'
            return

        model, blast, task_type, reason = "claude", 0, "general", "default"
        routing = getattr(request.app.state, "routing", None)
        budget = getattr(request.app.state, "budget", None)
        blueprints = getattr(request.app.state, "blueprints", None)
        effective_msg = body.message
        if routing:
            from maggy.services.chat_router import RoutedChat
            rc = RoutedChat(routing, budget, blueprints, pkey)
            d = await rc.decide(body.message, body.blast_score, body.task_type)
            allowed = body.allowed_models
            if allowed and d.model not in allowed:
                d.model = allowed[0]
                d.reason = f"restricted to {','.join(allowed)}"
            if d.model in _NON_CHAT_MODELS:
                orig = d.model
                d.model = _CHAT_MIN_MODEL
                d.reason = f"chat floor: {orig} -> {_CHAT_MIN_MODEL}"
            model, blast, task_type, reason = d.model, d.blast, d.task_type, d.reason
            yield f"data: {json.dumps(_routing_meta(d))}\n\n"
            if getattr(d, "blueprint_context", None):
                effective_msg = f"[Blueprint]\n{d.blueprint_context}\n[/Blueprint]\n\n{body.message}"
        pipeline = getattr(request.app.state, "pipeline", None)
        if not pipeline:
            async for chunk in chat.send(session_id, effective_msg):
                yield f"data: {json.dumps(chunk)}\n\n"
            yield 'data: {"type": "done"}\n\n'
            return
        from maggy.pipeline.models import PipelineContext
        ctx = PipelineContext(
            session_id=session_id,
            message=effective_msg,
            project_key=pkey,
            working_dir=wd,
        )
        response_parts: list[str] = []
        async for chunk in pipeline.run(ctx, s, model=model, blast=blast, task_type=task_type, reason=reason):
            if chunk.get("type") == "text":
                response_parts.append(chunk.get("content", ""))
            yield f"data: {json.dumps(chunk)}\n\n"
        if not _is_claude_model(model):
            _persist_pipeline_messages(
                request, session_id, s, body.message,
                "".join(response_parts),
            )
        yield 'data: {"type": "done"}\n\n'

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _routing_meta(d) -> dict:
    return {"type": "routing", "model": d.model, "blast": d.blast, "task_type": d.task_type, "reason": d.reason}


def _persist_pipeline_messages(
    request, session_id: str, session, user_msg: str,
    assistant_msg: str,
) -> None:
    """Save user + assistant messages after pipeline execution."""
    from maggy.services.chat_models import ChatMessage
    store = getattr(request.app.state, "session_store", None)
    session.messages.append(ChatMessage(role="user", content=user_msg))
    if assistant_msg.strip():
        session.messages.append(
            ChatMessage(role="assistant", content=assistant_msg),
        )
    if store:
        store.append_message(session_id, "user", user_msg)
        if assistant_msg.strip():
            store.append_message(
                session_id, "assistant", assistant_msg,
            )


def _match_protocol(message: str):
    from maggy.skills.intent_matcher import match_protocol
    from maggy.skills.protocol_loader import load_protocols
    proto_dir = Path(__file__).parent.parent / "skills" / "protocols"
    protos = load_protocols(proto_dir)
    return match_protocol(message, protos)


async def _run_protocol(proto, working_dir, message, request, session):
    from maggy.skills.protocol_executor import ProtocolExecutor
    variables = await _build_protocol_vars(working_dir, message, request)
    executor = ProtocolExecutor()
    yield {"type": "text", "content": f"Running **{proto.name}** protocol...\n\n"}
    async for ev in executor.execute(proto, working_dir, variables):
        yield ev


async def _build_protocol_vars(wd, message, request):
    import subprocess
    branch = "main"
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, cwd=wd, timeout=5,
        )
        if r.returncode == 0:
            branch = r.stdout.strip()
    except Exception:
        pass
    commit_msg = await _generate_commit_msg(wd, message, request)
    return {"branch": branch, "message": commit_msg, "title": commit_msg}


async def _generate_commit_msg(wd, user_msg, request):
    import subprocess
    try:
        r = subprocess.run(
            ["git", "diff", "--stat", "--cached"],
            capture_output=True, text=True, cwd=wd, timeout=10,
        )
        diff_stat = r.stdout.strip() if r.returncode == 0 else ""
        if not diff_stat:
            r = subprocess.run(
                ["git", "diff", "--stat"],
                capture_output=True, text=True, cwd=wd, timeout=10,
            )
            diff_stat = r.stdout.strip()
    except Exception:
        diff_stat = ""
    prompt = (
        f"Generate a concise git commit message (one line, "
        f"max 72 chars) for these changes:\n{diff_stat}\n"
        f"User context: {user_msg[:200]}"
    )
    pi = getattr(request.app.state, "pi", None)
    if pi:
        try:
            result = await pi.send_prompt("deepseek-flash", prompt, wd)
            if result.success and result.output:
                msg = result.output.strip().strip('"').strip("'")
                return msg[:72]
        except Exception:
            pass
    return "chore: update project files"


def _is_claude_model(model: str) -> bool:
    from maggy.pipeline.backend_pi import _PI_MODELS
    return model.lower() not in _PI_MODELS


_NON_CHAT_MODELS = frozenset({"local", "qwen", "gemini-flash-lite"})
_CHAT_MIN_MODEL = "deepseek-flash"


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
