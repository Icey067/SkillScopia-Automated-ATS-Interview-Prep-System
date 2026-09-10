from __future__ import annotations

from pathlib import Path

from PyPDF2 import PdfReader
from sqlalchemy.orm import Session

from app.models import Resume, Skill
from app.services.embeddings import expand_skills
from app.services.llm import extract_skills_from_text
from app.services.ws_manager import manager


def extract_pdf_text(file_path: str) -> str:
    reader = PdfReader(file_path)
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n".join(pages).strip()


def dummy_extract_text(file_path: str) -> str:
    path = Path(file_path)
    size = path.stat().st_size if path.exists() else 0
    return f"Dummy extraction for {path.name} ({size} bytes). Python, FastAPI, React."


def persist_skills(db: Session, resume: Resume, mapped: list[tuple[str, str, float]]) -> None:
    db.query(Skill).filter(Skill.resume_id == resume.id).delete()
    for name, source, score in mapped:
        db.add(
            Skill(
                resume_id=resume.id,
                skill_name=name,
                source=source,
                confidence_score=score,
            )
        )


async def notify_resume(user_id: int, payload: dict) -> None:
    await manager.send_to_user(user_id, payload)
