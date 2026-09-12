from __future__ import annotations

import asyncio
import logging

from app.config import get_settings
from app.database import get_db_context
from app.models import Resume
from app.services.embeddings import embedding_service
from app.services.llm import extract_skills_from_text
from app.services.resume_processor import dummy_extract_text, extract_pdf_text, persist_skills
from app.services.ws_manager import manager

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 2


async def _update_status(resume_id: int, status: str) -> int | None:
    async with get_db_context() as db:
        resume = await db.get(Resume, resume_id)
        if resume is None:
            return None
        resume.parsed_status = status
        return resume.user_id


async def process_resume_job(resume_id: int) -> None:
    """Async background worker for parsing resume text, extracting skills, and ontology matching."""
    settings = get_settings()

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            logger.info("Processing resume %d (attempt %d/%d)", resume_id, attempt, MAX_ATTEMPTS)
            async with get_db_context() as db:
                resume = await db.get(Resume, resume_id)
                if resume is None:
                    logger.error("Resume %d not found in database", resume_id)
                    return
                resume.parsed_status = "processing"
                file_ref = resume.file_ref
                user_id = resume.user_id

            # 1. Text extraction
            if settings.parse_mode == "dummy":
                _ = dummy_extract_text(file_ref)
                extracted = ["Python", "FastAPI", "React", "PostgreSQL", "Docker", "SQL"]
            else:
                text = await extract_pdf_text(file_ref)
                if not text:
                    raise ValueError("Uploaded PDF contains no extractable text")
                extracted = await extract_skills_from_text(text)
                if not extracted:
                    raise ValueError("No technical skills could be extracted from resume")

            # 2. Semantic expansion against hardcoded ontology
            mapped = await embedding_service.expand_skills_async(extracted)

            # 3. Write skills and update status
            async with get_db_context() as db:
                resume = await db.get(Resume, resume_id)
                if resume is not None:
                    await persist_skills(db, resume.id, mapped)
                    resume.parsed_status = "done"

            # 4. Real-time notification over WebSockets
            await manager.send_to_user(
                user_id,
                {
                    "type": "resume_ready",
                    "resume_id": resume_id,
                    "status": "done",
                    "skill_count": len(mapped),
                },
            )
            logger.info("Resume %d successfully processed with %d skills", resume_id, len(mapped))
            return

        except Exception as exc:
            logger.exception("Error processing resume %d on attempt %d: %s", resume_id, attempt, exc)
            if attempt < MAX_ATTEMPTS:
                await asyncio.sleep(1.0 * attempt)
                continue

            # Mark as failed on exhaustion of attempts
            user_id = await _update_status(resume_id, "failed")
            if user_id is not None:
                await manager.send_to_user(
                    user_id,
                    {
                        "type": "resume_failed",
                        "resume_id": resume_id,
                        "status": "failed",
                        "error": str(exc),
                    },
                )
