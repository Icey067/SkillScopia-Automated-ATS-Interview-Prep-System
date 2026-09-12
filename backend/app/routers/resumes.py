from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.exceptions import NotFoundError, ValidationError
from app.models import Resume, User
from app.rate_limit import limiter
from app.schemas import ResumeDetail, ResumeOut, ResumeUploadAccepted, SkillOut
from app.workers.resume_tasks import process_resume_job

router = APIRouter(prefix="/resumes", tags=["resumes"])
settings = get_settings()

CHUNK_SIZE = 64 * 1024  # 64 KB chunks for non-blocking file streaming


@router.post("", response_model=ResumeUploadAccepted, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit(settings.upload_rate_limit)
async def upload_resume(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> ResumeUploadAccepted:
    # 1. Filename & Content-Type sanity checks
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise ValidationError("Only PDF resumes are accepted (.pdf extension required)")
    if file.content_type and file.content_type not in {"application/pdf", "application/x-pdf", "application/octet-stream"}:
        raise ValidationError("Uploaded file must be of type application/pdf")

    upload_root = Path(settings.upload_dir)
    upload_root.mkdir(parents=True, exist_ok=True)

    # 2. File storage using generated UUID - never exposing server local paths
    file_uuid = uuid4().hex
    stored_name = f"{file_uuid}.pdf"
    dest_path = upload_root / stored_name

    total_bytes = 0
    max_bytes = settings.max_upload_size_bytes
    header_checked = False

    try:
        with open(dest_path, "wb") as buffer:
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                total_bytes += len(chunk)

                # Validate magic bytes for authentic PDFs on first chunk
                if not header_checked:
                    if not chunk.startswith(b"%PDF-"):
                        raise ValidationError("Uploaded file is not a valid PDF (invalid magic bytes)")
                    header_checked = True

                # Enforce strict 10MB limit
                if total_bytes > max_bytes:
                    raise ValidationError(f"PDF exceeds the {settings.max_upload_size_mb} MB limit")

                buffer.write(chunk)

        if total_bytes == 0 or not header_checked:
            raise ValidationError("Uploaded PDF file is empty")

    except Exception:
        # Cleanup incomplete or rejected file
        if dest_path.exists():
            dest_path.unlink(missing_ok=True)
        raise

    # 3. Create database record
    resume = Resume(
        user_id=current.id,
        file_ref=str(dest_path),
        parsed_status="pending",
    )
    db.add(resume)
    await db.commit()
    await db.refresh(resume)

    # 4. Enqueue background parsing
    background_tasks.add_task(process_resume_job, resume.id)

    return ResumeUploadAccepted(
        resume_id=resume.id,
        status=resume.parsed_status,
        message="Upload accepted. Background parsing and ontology matching initiated.",
    )


@router.get("", response_model=list[ResumeOut])
async def list_resumes(
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> list[ResumeOut]:
    result = await db.execute(
        select(Resume)
        .where(Resume.user_id == current.id)
        .order_by(Resume.uploaded_at.desc())
    )
    records = result.scalars().all()
    # Mask server file paths: only return clean UUID filename
    return [
        ResumeOut(
            id=r.id,
            filename=Path(r.file_ref).name,
            parsed_status=r.parsed_status,
            uploaded_at=r.uploaded_at,
        )
        for r in records
    ]


@router.get("/{resume_id}", response_model=ResumeDetail)
async def get_resume(
    resume_id: int,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> ResumeDetail:
    resume = await db.get(Resume, resume_id)
    if resume is None or resume.user_id != current.id:
        raise NotFoundError("Resume", resume_id)

    # Mask server file paths: only return clean UUID filename
    return ResumeDetail(
        id=resume.id,
        filename=Path(resume.file_ref).name,
        parsed_status=resume.parsed_status,
        uploaded_at=resume.uploaded_at,
        skills=[SkillOut.model_validate(s) for s in resume.skills],
    )


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume(
    resume_id: int,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
) -> None:
    resume = await db.get(Resume, resume_id)
    if resume is None or resume.user_id != current.id:
        raise NotFoundError("Resume", resume_id)

    file_path = Path(resume.file_ref)
    await db.delete(resume)
    await db.commit()

    try:
        file_path.unlink(missing_ok=True)
    except OSError:
        pass
