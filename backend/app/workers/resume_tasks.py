from __future__ import annotations

import logging
import time

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db_context
from app.models import Resume
from app.services.embeddings import expand_skills
from app.services.llm import extract_skills_from_text
from app.services.resume_processor import dummy_extract_text, extract_pdf_text, persist_skills
from app.services.ws_manager import manager

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3  # initial try + 2 retries


def _set_status(resume_id: int, status: str) -> int | None:
    with get_db_context() as db:
        resume = db.get(Resume, resume_id)
        if resume is None:
            return None
        resume.parsed_status = status
        return resume.user_id


def process_resume_job(resume_id: int) -> None:
    settings = get_settings()
    last_error = "Unknown error"

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with get_db_context() as db:
                resume = db.get(Resume, resume_id)
                if resume is None:
                    logger.error("Resume %s not found", resume_id)
                    return
                resume.parsed_status = "processing"

                if settings.parse_mode == "dummy":
                    text = dummy_extract_text(resume.file_ref)
                    extracted = ["Python", "FastAPI", "React"]
                else:
                    text = extract_pdf_text(resume.file_ref)
                    if not text:
                        raise ValueError("PDF contained no extractable text")
                    extracted = extract_skills_from_text(text)
                    if not extracted:
                        raise ValueError("LLM returned no skills after structured parse + retry")

                mapped = expand_skills(extracted)
                persist_skills(db, resume, mapped)
                resume.parsed_status = "done"
                user_id = resume.user_id
            manager.notify_from_thread(
                user_id,
                {"type": "resume_ready", "resume_id": resume_id, "status": "done", "skill_count": len(mapped)},
            )
            logger.info("Resume %s processed successfully with %d skills", resume_id, len(mapped))
            return
        except Exception as exc:
            last_error = str(exc)
            logger.exception("Resume %s attempt %s failed: %s", resume_id, attempt, exc)
            if attempt < MAX_ATTEMPTS:
                time.sleep(1.5 * attempt)
                continue
            user_id = _set_status(resume_id, "failed")
            if user_id is not None:
                manager.notify_from_thread(
                    user_id,
                    {"type": "resume_failed", "resume_id": resume_id, "status": "failed", "error": "Resume processing failed"},
                )
