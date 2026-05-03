import uuid

from core.models import TrendSignal, TrendSignalArticle
from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from api.deps import SessionDep
from api.types import UtcDateTime

router = APIRouter(prefix="/trend-signals", tags=["trend-signals"])


class TrendSignalOut(BaseModel):
    id: uuid.UUID
    keyword: str
    interest_score: float | None
    captured_at: UtcDateTime
    article_count: int


@router.get("/latest", response_model=list[TrendSignalOut])
async def latest_trend_signals(
    session: SessionDep,
    limit: int = Query(default=10, ge=1, le=50),
) -> list[TrendSignalOut]:
    latest_captured_at = (
        await session.execute(select(func.max(TrendSignal.captured_at)))
    ).scalar_one_or_none()

    if latest_captured_at is None:
        return []

    stmt = (
        select(
            TrendSignal.id,
            TrendSignal.keyword,
            TrendSignal.interest_score,
            TrendSignal.captured_at,
            func.count(TrendSignalArticle.article_id).label("article_count"),
        )
        .outerjoin(TrendSignalArticle, TrendSignalArticle.trend_signal_id == TrendSignal.id)
        .where(TrendSignal.captured_at == latest_captured_at)
        .group_by(TrendSignal.id)
        .order_by(TrendSignal.interest_score.desc().nullslast())
        .limit(limit)
    )

    rows = (await session.execute(stmt)).all()

    return [
        TrendSignalOut(
            id=r.id,
            keyword=r.keyword,
            interest_score=r.interest_score,
            captured_at=r.captured_at,
            article_count=r.article_count,
        )
        for r in rows
    ]
