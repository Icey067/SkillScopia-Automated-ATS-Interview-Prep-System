from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Request, UploadFile, status
from sqlalchemy.orm import Session

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


@router.post("", response_model=ResumeUploadAccepted, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit(settings.upload_rate_limit)
def upload_resume(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise ValidationError("Only PDF resumes are accepted")
    if file.content_type not in {"application/pdf", "application/x-pdf"}:
        raise ValidationError("The uploaded file must have a PDF content type")

    upload_root = Path(settings.upload_dir)
    upload_root.mkdir(parents=True, exist_ok=True)
    stored_name = f"{current.id}_{uuid4().hex}.pdf"
    dest = upload_root / stored_name
    content = file.file.read(settings.max_upload_size_bytes + 1)
    if len(content) > settings.max_upload_size_bytes:
        raise ValidationError(f"PDF must be at most {settings.max_upload_size_mb} MB")
    if not content.startswith(b"%PDF-"):
        raise ValidationError("The uploaded file is not a valid PDF")
    dest.write_bytes(content)

    resume = Resume(user_id=current.id, file_ref=str(dest), parsed_status="pending")
    db.add(resume)
    db.commit()
    db.refresh(resume)

    background_tasks.add_task(process_resume_job, resume.id)
    return ResumeUploadAccepted(
        resume_id=resume.id,
        status=resume.parsed_status,
        message="Upload accepted. Parsing runs in the background.",
    )


@router.get("", response_model=list[ResumeOut])
def list_resumes(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    records = (
        db.query(Resume)
        .filter(Resume.user_id == current.id)
        .order_by(Resume.uploaded_at.desc())
        .all()
    )
    return [ResumeOut(id=r.id, filename=Path(r.file_ref).name, parsed_status=r.parsed_status, uploaded_at=r.uploaded_at) for r in records]


@router.get("/{resume_id}", response_model=ResumeDetail)
def get_resume(resume_id: int, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    resume = db.get(Resume, resume_id)
    if resume is None or resume.user_id != current.id:
        raise NotFoundError("Resume", resume_id)
    return ResumeDetail(
        id=resume.id,
        filename=Path(resume.file_ref).name,
        parsed_status=resume.parsed_status,
        uploaded_at=resume.uploaded_at,
        skills=[SkillOut.model_validate(s) for s in resume.skills],
    )


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(resume_id: int, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    resume = db.get(Resume, resume_id)
    if resume is None or resume.user_id != current.id:
        raise NotFoundError("Resume", resume_id)
    file_path = Path(resume.file_ref)
    db.delete(resume)
    db.commit()
    try:
        file_path.unlink(missing_ok=True)
    except OSError:
        pass
