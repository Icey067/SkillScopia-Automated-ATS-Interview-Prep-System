from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.exceptions import NotFoundError, ConflictError
from app.models import InterviewQA, InterviewSession, Resume, Skill, User
from app.rate_limit import limiter
from app.schemas import InterviewQAOut, InterviewSessionCreate, InterviewSessionOut
from app.services.llm import generate_interview_question

router = APIRouter(prefix="/interviews", tags=["interviews"])
settings = get_settings()


@router.post("", response_model=InterviewSessionOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.chat_rate_limit)
def create_session(
    payload: InterviewSessionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    resume = db.get(Resume, payload.resume_id)
    if resume is None or resume.user_id != current.id:
        raise NotFoundError("Resume", payload.resume_id)
    if resume.parsed_status != "done":
        raise ConflictError("Resume is not ready for interview")

    skills = [s.skill_name for s in db.query(Skill).filter(Skill.resume_id == resume.id).all()]
    session = InterviewSession(user_id=current.id, resume_id=resume.id)
    db.add(session)
    db.commit()
    db.refresh(session)

    asked: list[str] = []
    generated = 0
    last_error = None
    for _ in range(payload.question_count):
        try:
            item = generate_interview_question(skills, asked)
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
        db.rollback()
        db.delete(session)
        db.commit()
        raise HTTPException(
            status_code=502,
            detail=f"Could not generate interview questions: {last_error}",
        )

    db.commit()
    db.refresh(session)
    return _session_out(db, session)


@router.get("", response_model=list[InterviewSessionOut])
def list_sessions(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    sessions = (
        db.query(InterviewSession)
        .filter(InterviewSession.user_id == current.id)
        .order_by(InterviewSession.started_at.desc())
        .all()
    )
    return [_session_out(db, session) for session in sessions]


@router.get("/{session_id}", response_model=InterviewSessionOut)
def get_session(session_id: int, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    session = db.get(InterviewSession, session_id)
    if session is None or session.user_id != current.id:
        raise NotFoundError("Interview session", session_id)
    return _session_out(db, session)


@router.post("/{session_id}/end", response_model=InterviewSessionOut)
def end_session(session_id: int, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    session = db.get(InterviewSession, session_id)
    if session is None or session.user_id != current.id:
        raise NotFoundError("Interview session", session_id)
    session.ended_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return _session_out(db, session)


def _session_out(db: Session, session: InterviewSession) -> InterviewSessionOut:
    qas = (
        db.query(InterviewQA)
        .filter(InterviewQA.session_id == session.id)
        .order_by(InterviewQA.id)
        .all()
    )
    return InterviewSessionOut(
        id=session.id,
        resume_id=session.resume_id,
        started_at=session.started_at,
        ended_at=session.ended_at,
        questions=[InterviewQAOut.model_validate(q) for q in qas],
    )
