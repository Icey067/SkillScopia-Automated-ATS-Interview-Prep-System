from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import JSONResponse

from app.config import get_settings
from app.database import close_db, init_db
from app.exceptions import register_exception_handlers
from app.rate_limit import limiter
from app.routers import auth, health, interviews, resumes, ws
from app.services.embeddings import embedding_service
from app.services.ws_manager import manager

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup lifecycle
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    await init_db()
    manager.bind_loop(asyncio.get_running_loop())

    # Preload SentenceTransformers singleton asynchronously to avoid latency on first request
    asyncio.create_task(embedding_service.initialize())

    yield

    # Shutdown lifecycle
    await close_db()


app = FastAPI(
    title="AI Mock Interview Platform",
    description="Production-grade asynchronous backend for AI-powered mock interviews, resume parsing, and real-time streaming feedback.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

register_exception_handlers(app)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: StarletteRequest, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"error": {"code": "RATE_LIMITED", "message": "Too many requests. Please try again later."}},
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
    response: Response = await call_next(request)
    process_time = time.perf_counter() - start_time

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{process_time:.4f}"

    return response


# Register Routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(resumes.router)
app.include_router(interviews.router)
app.include_router(ws.router)
