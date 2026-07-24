from fastapi import APIRouter, HTTPException, status
from redis import Redis
from sqlalchemy import text

from app.core.config import settings
from app.database.session import SessionLocal

router = APIRouter(tags=["System"])


@router.get("/")
def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs",
    }


@router.get("/health")
def health() -> dict[str, str]:
    checks: dict[str, str] = {"api": "ok"}

    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database unavailable: {exc}",
        ) from exc

    client = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        client.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Redis unavailable: {exc}",
        ) from exc
    finally:
        client.close()

    return checks
