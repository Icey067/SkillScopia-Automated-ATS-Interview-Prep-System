from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from PyPDF2 import PdfReader
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Skill

logger = logging.getLogger(__name__)


def _extract_pdf_sync(file_path: str) -> str:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Resume file not found: {file_path}")

    reader = PdfReader(str(path))
    pages: list[str] = []
    for idx, page in enumerate(reader.pages):
        try:
            page_text = page.extract_text() or ""
            pages.append(page_text)
        except Exception as exc:
            logger.warning("Error extracting text from page %d in %s: %s", idx, path.name, exc)

    return "\n".join(pages).strip()


async def extract_pdf_text(file_path: str) -> str:
    """Extract text from a PDF file using PyPDF2 without blocking the asyncio loop."""
    return await asyncio.to_thread(_extract_pdf_sync, file_path)


def dummy_extract_text(file_path: str) -> str:
    path = Path(file_path)
    size = path.stat().st_size if path.exists() else 0
    return f"Demo resume extraction for {path.name} ({size} bytes). Key skills: Python, FastAPI, React, PostgreSQL, Docker."


async def persist_skills(
    db: AsyncSession,
    resume_id: int,
    mapped_skills: list[tuple[str, str, float]],
) -> None:
    """Persist extracted and semantic skills for a resume in an async transaction."""
    await db.execute(delete(Skill).where(Skill.resume_id == resume_id))
    for name, source, score in mapped_skills:
        db.add(
            Skill(
                resume_id=resume_id,
                skill_name=name,
                source=source,
                confidence_score=score,
            )
        )
    await db.flush()
