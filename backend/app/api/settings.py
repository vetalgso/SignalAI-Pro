from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("")
def public_settings() -> dict[str, str | bool]:
    return {
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "environment": settings.environment,
        "binance_testnet": settings.binance_testnet,
    }
