from fastapi import APIRouter

router = APIRouter(prefix="/exchange", tags=["Exchange"])


@router.get("/status")
def exchange_status() -> dict[str, str | bool]:
    return {
        "exchange": "Binance",
        "connected": False,
        "mode": "testnet",
        "message": "Exchange integration is not configured yet",
    }
