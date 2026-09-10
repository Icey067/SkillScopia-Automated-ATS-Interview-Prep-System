import asyncio
import time
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import JSONResponse

from app.config import get_settings
from app.database import Base, engine
from app.exceptions import register_exception_handlers
from app.rate_limit import limiter
from app.routers import auth, health, interviews, resumes, ws
from app.services.ws_manager import manager

settings = get_settings()

app = FastAPI(
    title="AI Mock Interview Platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

register_exception_handlers(app)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: StarletteRequest, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"error": {"code": "RATE_LIMITED", "message": "Rate limit exceeded"}},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = str(uuid4())[:8]
    request.state.request_id = request_id

    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = time.perf_counter() - start_time

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{process_time:.4f}"

    return response


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(resumes.router)
app.include_router(interviews.router)
app.include_router(ws.router)


@app.on_event("startup")
async def on_startup():
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    # Lightweight compatibility migration for installations created before v1.1.
    with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            connection.exec_driver_sql("ALTER TABLE interview_qa ADD COLUMN IF NOT EXISTS interviewer_reply TEXT")
            connection.exec_driver_sql(
                "CREATE TABLE IF NOT EXISTS refresh_tokens (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, token_id VARCHAR(64) UNIQUE NOT NULL, expires_at TIMESTAMPTZ NOT NULL, revoked_at TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"
            )
        elif engine.dialect.name == "sqlite":
            columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(interview_qa)")}
            if "interviewer_reply" not in columns:
                connection.exec_driver_sql("ALTER TABLE interview_qa ADD COLUMN interviewer_reply TEXT")
    manager.bind_loop(asyncio.get_running_loop())
