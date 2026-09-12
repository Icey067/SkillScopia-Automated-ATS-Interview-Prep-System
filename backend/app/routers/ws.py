from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from starlette.websockets import WebSocketState

from app.auth import decode_token
from app.database import AsyncSessionLocal
from app.models import InterviewQA, InterviewSession, Skill, User
from app.services.llm import score_answer, stream_interviewer_reply
from app.services.ws_manager import manager

router = APIRouter(tags=["websocket"])
logger = logging.getLogger(__name__)


def _extract_auth_from_protocols(websocket: WebSocket) -> tuple[str | None, str | None]:
    """Extract JWT token and negotiate response subprotocol according to Sec-WebSocket-Protocol.
    
    Supports both:
      - ['access_token', '<JWT>'] -> returns (<JWT>, 'access_token')
      - ['access.<JWT>'] -> returns (<JWT>, 'access.<JWT>')
    """
    raw = websocket.headers.get("sec-websocket-protocol", "")
    if not raw:
        return None, None

    tokens = [p.strip() for p in raw.split(",") if p.strip()]

    # Format 1: RFC-style subprotocol negotiation: ['access_token', '<JWT>']
    if "access_token" in tokens:
        for t in tokens:
            if t != "access_token":
                return t, "access_token"

    # Format 2: Prefix-based subprotocol: ['access.<JWT>']
    for t in tokens:
        if t.startswith("access."):
            return t.removeprefix("access."), t

    return None, None


async def _authenticate_ws(websocket: WebSocket) -> tuple[User | None, str | None]:
    token, subprotocol = _extract_auth_from_protocols(websocket)
    if not token:
        return None, None

    try:
        user_id, _ = decode_token(token, "access")
    except ValueError:
        return None, None

    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        return user, subprotocol


@router.websocket("/ws/notifications")
async def notifications_socket(websocket: WebSocket) -> None:
    user, subprotocol = await _authenticate_ws(websocket)
    if user is None:
        await websocket.close(code=4401)
        return

    await manager.connect(user.id, websocket, subprotocol=subprotocol)
    try:
        await websocket.send_text(json.dumps({"type": "connected", "channel": "notifications"}))
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.error("Notifications WebSocket error for user %d: %s", user.id, exc)
    finally:
        await manager.disconnect(user.id, websocket)


@router.websocket("/ws/interview/{session_id}")
async def interview_socket(websocket: WebSocket, session_id: int) -> None:
    user, subprotocol = await _authenticate_ws(websocket)
    if user is None:
        await websocket.close(code=4401)
        return

    # Verify session ownership and collect resume skills
    async with AsyncSessionLocal() as db:
        session = await db.get(InterviewSession, session_id)
        if session is None or session.user_id != user.id:
            await websocket.close(code=4401)
            return
        skills_res = await db.execute(select(Skill.skill_name).where(Skill.resume_id == session.resume_id))
        skills = [r[0] for r in skills_res.all()]

    await websocket.accept(subprotocol=subprotocol)
    await websocket.send_text(
        json.dumps({"type": "connected", "channel": "interview", "session_id": session_id})
    )

    in_flight_generation_task: asyncio.Task[None] | None = None

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"type": "error", "error": "Invalid JSON format"}))
                continue

            msg_type = message.get("type")
            if msg_type == "answer":
                # Cancel any previous in-flight generation task before starting a new one
                if in_flight_generation_task and not in_flight_generation_task.done():
                    in_flight_generation_task.cancel()
                    try:
                        await in_flight_generation_task
                    except asyncio.CancelledError:
                        pass

                in_flight_generation_task = asyncio.create_task(
                    _handle_answer_stream(websocket, session_id, message, skills)
                )

            elif msg_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

    except WebSocketDisconnect:
        logger.info("Interview WebSocket disconnected for session %d", session_id)
    except Exception as exc:
        logger.exception("Interview WebSocket error for session %d: %s", session_id, exc)
    finally:
        # STRICT REQUIREMENT: Disconnects must trigger asyncio.Task.cancel() on in-flight Ollama generation
        if in_flight_generation_task and not in_flight_generation_task.done():
            logger.info("Disconnect detected: cancelling in-flight Ollama generation task for session %d", session_id)
            in_flight_generation_task.cancel()
            try:
                await in_flight_generation_task
            except asyncio.CancelledError:
                pass


async def _handle_answer_stream(
    websocket: WebSocket,
    session_id: int,
    message: dict[str, Any],
    skills: list[str],
) -> None:
    qa_id = message.get("qa_id")
    text = (message.get("text") or "").strip()
    if not qa_id or not text:
        await websocket.send_text(json.dumps({"type": "error", "error": "qa_id and text are required"}))
        return

    async with AsyncSessionLocal() as db:
        session = await db.get(InterviewSession, session_id)
        if session is None or session.ended_at is not None:
            await websocket.send_text(json.dumps({"type": "error", "error": "This interview session is closed"}))
            return

        qa = await db.get(InterviewQA, int(qa_id))
        if qa is None or qa.session_id != session_id:
            await websocket.send_text(json.dumps({"type": "error", "error": "Question not found"}))
            return

        if qa.user_answer is not None:
            await websocket.send_text(json.dumps({"type": "error", "error": "This question has already been answered"}))
            return

        question = qa.question
        concept = qa.ideal_answer_concept
        qa.user_answer = text
        await db.commit()

    await websocket.send_text(json.dumps({"type": "stream_start", "qa_id": qa_id}))
    collected: list[str] = []

    try:
        async for token in stream_interviewer_reply(question, concept, text, skills):
            if websocket.client_state != WebSocketState.CONNECTED:
                raise asyncio.CancelledError("Client disconnected during reply stream")
            collected.append(token)
            await websocket.send_text(json.dumps({"type": "token", "qa_id": qa_id, "content": token}))
    except asyncio.CancelledError:
        logger.info("Ollama streaming generation cancelled for qa_id %s", qa_id)
        raise
    except Exception as exc:
        logger.error("Error during streaming reply: %s", exc)
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_text(json.dumps({"type": "error", "error": str(exc)}))
        return

    # Calculate answer score
    score = await score_answer(question, concept, text)

    # Persist score and interviewer reply
    async with AsyncSessionLocal() as db:
        qa = await db.get(InterviewQA, int(qa_id))
        if qa is not None:
            qa.score = score
            qa.interviewer_reply = "".join(collected)
            await db.commit()

    if websocket.client_state == WebSocketState.CONNECTED:
        await websocket.send_text(
            json.dumps(
                {
                    "type": "stream_end",
                    "qa_id": qa_id,
                    "score": score,
                    "reply": "".join(collected),
                }
            )
        )
