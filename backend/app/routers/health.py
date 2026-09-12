from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.services.embeddings import embedding_service

router = APIRouter(tags=["health"])
settings = get_settings()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/detailed")
async def health_detailed() -> dict[str, Any]:
    checks: dict[str, Any] = {}
    overall = "ok"

    # 1. Async Database Check
    db_start = time.perf_counter()
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        checks["database"] = {
            "status": "ok",
            "latency_ms": round((time.perf_counter() - db_start) * 1000, 2),
        }
    except Exception as e:
        checks["database"] = {"status": "error", "error": str(e)}
        overall = "degraded"

    # 2. Upload Storage Check
    try:
        upload_dir = Path(settings.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)
        test_file = upload_dir / ".health_check"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink(missing_ok=True)
        checks["storage"] = {"status": "ok"}
    except Exception as e:
        checks["storage"] = {"status": "error", "error": str(e)}
        overall = "degraded"

    # 3. Async Ollama Health Check
    ollama_start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            if resp.status_code == 200:
                checks["ollama"] = {
                    "status": "ok",
                    "latency_ms": round((time.perf_counter() - ollama_start) * 1000, 2),
                }
            else:
                checks["ollama"] = {"status": "error", "error": f"HTTP {resp.status_code}"}
                overall = "degraded"
    except Exception as e:
        checks["ollama"] = {"status": "error", "error": str(e)}
        overall = "degraded"

    # 4. Embeddings Singleton Check
    checks["embeddings"] = {
        "status": "ok" if embedding_service.is_loaded else "unloaded",
        "singleton_ready": embedding_service.is_loaded,
    }

    return {
        "status": overall,
        "checks": checks,
        "version": "1.0.0",
    }


@router.get("/health/ready")
async def readiness(response: Response) -> dict[str, bool]:
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        return {"ready": True}
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"ready": False}