from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketState

from app.auth import decode_token
from app.database import SessionLocal
from app.models import InterviewQA, InterviewSession, Skill, User
from app.services.llm import score_answer, stream_interviewer_reply
from app.services.ws_manager import manager

router = APIRouter(tags=["websocket"])
logger = logging.getLogger(__name__)


def _token_from_protocol(websocket: WebSocket) -> tuple[str | None, str | None]:
    protocol = websocket.headers.get("sec-websocket-protocol", "")
    for value in (part.strip() for part in protocol.split(",")):
        if value.startswith("access."):
            return value.removeprefix("access."), value
    return None, None


def _user_from_token(token: str | None, db: Session) -> User | None:
    if not token:
        return None
    try:
        user_id, _ = decode_token(token, "access")
    except ValueError:
        return None
    return db.get(User, user_id)


@router.websocket("/ws/notifications")
async def notifications_socket(websocket: WebSocket):
    token, subprotocol = _token_from_protocol(websocket)
    db = SessionLocal()
    try:
        user = _user_from_token(token, db)
    finally:
        db.close()
    if user is None:
        await websocket.close(code=4401)
        return
    await manager.connect(user.id, websocket, subprotocol)
    try:
        await websocket.send_text(json.dumps({"type": "connected", "channel": "notifications"}))
        while True:
            try:
                await websocket.receive_text()
            except WebSocketDisconnect:
                break
            except Exception:
                break
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("Notifications WebSocket error for user %d: %s", user.id, e)
    finally:
        await manager.disconnect(user.id, websocket)


@router.websocket("/ws/interview/{session_id}")
async def interview_socket(websocket: WebSocket, session_id: int):
    token, subprotocol = _token_from_protocol(websocket)
    db = SessionLocal()
    try:
        user = _user_from_token(token, db)
        session = db.get(InterviewSession, session_id) if user else None
        if user is None or session is None or session.user_id != user.id:
            await websocket.close(code=4401)
            return
        skills = [s.skill_name for s in db.query(Skill).filter(Skill.resume_id == session.resume_id).all()]
    finally:
        db.close()

    await websocket.accept(subprotocol=subprotocol)
    await websocket.send_text(json.dumps({"type": "connected", "channel": "interview", "session_id": session_id}))
    stream_task: asyncio.Task | None = None

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"type": "error", "error": "Invalid JSON"}))
                continue

            msg_type = message.get("type")
            if msg_type == "answer":
                if stream_task and not stream_task.done():
                    stream_task.cancel()
                    try:
                        await stream_task
                    except asyncio.CancelledError:
                        pass
                stream_task = asyncio.create_task(
                    _handle_answer(websocket, session_id, message, skills)
                )
                try:
                    await stream_task
                except asyncio.CancelledError:
                    break
            elif msg_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for session %d", session_id)
        if stream_task and not stream_task.done():
            stream_task.cancel()
            try:
                await stream_task
            except asyncio.CancelledError:
                pass
    except Exception as e:
        logger.exception("Interview WebSocket error for session %d: %s", session_id, e)
    finally:
        if stream_task and not stream_task.done():
            stream_task.cancel()


async def _handle_answer(websocket: WebSocket, session_id: int, message: dict, skills: list[str]) -> None:
    qa_id = message.get("qa_id")
    text = (message.get("text") or "").strip()
    if not qa_id or not text:
        await websocket.send_text(json.dumps({"type": "error", "error": "qa_id and text are required"}))
        return

    db = SessionLocal()
    try:
        session = db.get(InterviewSession, session_id)
        if session is None or session.ended_at is not None:
            await websocket.send_text(json.dumps({"type": "error", "error": "This interview is closed"}))
            return
        qa = db.get(InterviewQA, int(qa_id))
        if qa is None or qa.session_id != session_id:
            await websocket.send_text(json.dumps({"type": "error", "error": "Question not found"}))
            return
        if qa.user_answer is not None:
            await websocket.send_text(json.dumps({"type": "error", "error": "This question has already been answered"}))
            return
        question = qa.question
        concept = qa.ideal_answer_concept
        qa.user_answer = text
        db.commit()
    finally:
        db.close()

    await websocket.send_text(json.dumps({"type": "stream_start", "qa_id": qa_id}))
    collected: list[str] = []
    try:
        async for token in stream_interviewer_reply(question, concept, text, skills):
            if websocket.client_state != WebSocketState.CONNECTED:
                raise asyncio.CancelledError()
            collected.append(token)
            await websocket.send_text(json.dumps({"type": "token", "qa_id": qa_id, "content": token}))
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_text(json.dumps({"type": "error", "error": str(exc)}))
        return

    score = await asyncio.to_thread(score_answer, question, concept, text)
    db = SessionLocal()
    try:
        qa = db.get(InterviewQA, int(qa_id))
        if qa is not None:
            qa.score = score
            qa.interviewer_reply = "".join(collected)
            db.commit()
    finally:
        db.close()

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
