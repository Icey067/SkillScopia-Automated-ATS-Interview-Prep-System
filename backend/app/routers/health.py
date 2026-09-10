import time
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal, engine

router = APIRouter(tags=["health"])
settings = get_settings()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/health/detailed")
def health_detailed():
    checks = {}
    overall = "ok"

    # Database check
    db_start = time.perf_counter()
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        checks["database"] = {
            "status": "ok",
            "latency_ms": round((time.perf_counter() - db_start) * 1000, 2),
        }
    except Exception as e:
        checks["database"] = {"status": "error", "error": str(e)}
        overall = "degraded"

    # Upload directory check
    try:
        upload_dir = Path(settings.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)
        test_file = upload_dir / ".health_check"
        test_file.write_text("ok")
        test_file.unlink()
        checks["storage"] = {"status": "ok"}
    except Exception as e:
        checks["storage"] = {"status": "error", "error": str(e)}
        overall = "degraded"

    # Ollama check
    ollama_start = time.perf_counter()
    try:
        import urllib.request

        req = urllib.request.Request(f"{settings.ollama_base_url}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                checks["ollama"] = {
                    "status": "ok",
                    "latency_ms": round((time.perf_counter() - ollama_start) * 1000, 2),
                }
            else:
                checks["ollama"] = {"status": "error", "error": f"HTTP {resp.status}"}
                overall = "degraded"
    except Exception as e:
        checks["ollama"] = {"status": "error", "error": str(e)}
        overall = "degraded"

    # Embedding model check
    try:
        from app.services.embeddings import get_embedding_model

        model = get_embedding_model()
        _ = model.encode(["test"], normalize_embeddings=True)
        checks["embeddings"] = {"status": "ok"}
    except Exception as e:
        checks["embeddings"] = {"status": "error", "error": str(e)}
        overall = "degraded"

    return {"status": overall, "checks": checks, "version": "1.0.0"}


@router.get("/health/ready")
def readiness():
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return {"ready": True}
    except Exception:
        return {"ready": False}