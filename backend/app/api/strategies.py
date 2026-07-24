from fastapi import APIRouter

router = APIRouter(prefix="/strategies", tags=["Strategies"])


@router.get("")
def list_strategies() -> list[dict[str, str | bool]]:
    return [
        {"name": "ema_cross", "status": "planned", "enabled": False},
        {"name": "breakout", "status": "planned", "enabled": False},
    ]
