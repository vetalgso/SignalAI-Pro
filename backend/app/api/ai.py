from fastapi import APIRouter

router = APIRouter(prefix="/ai", tags=["AI"])


@router.get("/status")
def ai_status() -> dict[str, str | bool]:
    return {
        "configured": False,
        "status": "not_configured",
        "message": "AI analysis will be added after the market-data pipeline",
    }
