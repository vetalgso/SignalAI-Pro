from typing import Annotated
from fastapi import APIRouter, Query
from app.news import NewsService
router = APIRouter(prefix="/news", tags=["News Intelligence"])

@router.get("")
async def news(limit: Annotated[int, Query(ge=1, le=100)] = 50, asset: str | None = None):
    return await NewsService().latest(limit, asset)
