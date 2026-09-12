from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.exceptions import ConflictError, NotFoundError
from app.models import InterviewQA, InterviewSession, Resume, User
from app.rate_limit import limiter
from app.schemas import InterviewQAOut, InterviewSessionCreate, InterviewSessionOut
from app.services.llm import generate_interview_question

router = APIRouter(prefix="/interviews", tags=["interviews"])
settings = get_settings()


def _format_session_out(session: InterviewSession) -> InterviewSessionOut:
    return InterviewSessionOut(
        id=session.id,
        resume_id=session.resume_id,
        started_at=session.started_at,
        ended_at=session.ended_at,
        questions=[InterviewQAOut.model_validate(q) for q in session.qa_items],
    )


@router.post("", response_model=InterviewSessionOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.chat_rate_limit)
async def create_session(
    payload: InterviewSessionCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> InterviewSessionOut:
    resume = await db.get(Resume, payload.resume_id)
    if resume is None or resume.user_id != current.id:
        raise NotFoundError("Resume", payload.resume_id)
    if resume.parsed_status != "done":
        raise ConflictError("Resume parsing is not complete yet. Please wait for status 'done'.")

    skills = [s.skill_name for s in resume.skills]
    session = InterviewSession(user_id=current.id, resume_id=resume.id)
    db.add(session)
    await db.commit()
    await db.refresh(session)

    asked: list[str] = []
    generated = 0
    last_error: str | None = None

    for _ in range(payload.question_count):
        try:
            item = await generate_interview_question(skills, asked)
            qa = InterviewQA(
                session_id=session.id,
                question=item.question,
                ideal_answer_concept=item.ideal_answer_concept,
            )
            db.add(qa)
            asked.append(item.question)
            generated += 1
        except Exception as exc:
            last_error = str(exc)
            break

    if generated == 0:
        await db.delete(session)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not generate interview questions: {last_error}",
        )

    await db.commit()
    # Re-fetch with eager loaded relationships
    refreshed = await db.get(InterviewSession, session.id)
    return _format_session_out(refreshed or session)


@router.get("", response_model=list[InterviewSessionOut])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> list[InterviewSessionOut]:
    result = await db.execute(
        select(InterviewSession)
        .where(InterviewSession.user_id == current.id)
        .order_by(InterviewSession.started_at.desc())
    )
    sessions = result.scalars().all()
    return [_format_session_out(s) for s in sessions]


@router.get("/{session_id}", response_model=InterviewSessionOut)
async def get_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> InterviewSessionOut:
    session = await db.get(InterviewSession, session_id)
    if session is None or session.user_id != current.id:
        raise NotFoundError("Interview session", session_id)
    return _format_session_out(session)


@router.post("/{session_id}/end", response_model=InterviewSessionOut)
async def end_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> InterviewSessionOut:
    session = await db.get(InterviewSession, session_id)
    if session is None or session.user_id != current.id:
        raise NotFoundError("Interview session", session_id)
    session.ended_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(session)
    return _format_session_out(session)
