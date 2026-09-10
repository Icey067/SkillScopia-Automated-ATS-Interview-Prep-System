from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    created_at: datetime

    model_config = {"from_attributes": True}


class ResumeOut(BaseModel):
    id: int
    filename: str
    parsed_status: str
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class ResumeUploadAccepted(BaseModel):
    resume_id: int
    status: str
    message: str


class SkillOut(BaseModel):
    id: int
    skill_name: str
    source: str
    confidence_score: float

    model_config = {"from_attributes": True}


class ResumeDetail(ResumeOut):
    skills: list[SkillOut] = []


class InterviewSessionCreate(BaseModel):
    resume_id: int
    question_count: int = Field(default=5, ge=1, le=10)


class InterviewQAOut(BaseModel):
    id: int
    question: str
    ideal_answer_concept: str
    user_answer: str | None
    interviewer_reply: str | None
    score: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


class InterviewSessionOut(BaseModel):
    id: int
    resume_id: int
    started_at: datetime
    ended_at: datetime | None
    questions: list[InterviewQAOut] = []

    model_config = {"from_attributes": True}


class GeneratedQuestion(BaseModel):
    question: str
    ideal_answer_concept: str
