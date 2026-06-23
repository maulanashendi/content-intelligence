import math
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from core.models import Article, ContentSource, SourceType
from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from api.deps import SessionDep
from api.types import UtcDateTime
from api.volume import VolumeBucket, VolumeTrendResponse, dense_bucket_starts

router = APIRouter(prefix="/articles", tags=["articles"])


class ArticleResponse(BaseModel):
    id: uuid.UUID
    title: str
    url: str
    first_paragraph: str | None
    published_at: UtcDateTime | None
    created_at: UtcDateTime
    source_name: str
    source_type: str


class PaginatedArticles(BaseModel):
    items: list[ArticleResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


@router.get("", response_model=PaginatedArticles)
async def list_articles(
    session: SessionDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedArticles:
    total: int = (await session.execute(select(func.count(Article.id)))).scalar_one()

    stmt = (
        select(
            Article.id,
            Article.title,
            Article.url,
            Article.first_paragraph,
            Article.published_at,
            Article.created_at,
            ContentSource.name.label("source_name"),
            ContentSource.source_type.label("source_type"),
        )
        .join(ContentSource, ContentSource.id == Article.source_id)
        .order_by(Article.created_at.desc(), Article.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await session.execute(stmt)).all()

    items = [
        ArticleResponse(
            id=r.id,
            title=r.title,
            url=r.url,
            first_paragraph=r.first_paragraph,
            published_at=r.published_at,
            created_at=r.created_at,
            source_name=r.source_name,
            source_type=r.source_type.value,
        )
        for r in rows
    ]

    return PaginatedArticles(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total else 1,
    )


@router.get(
    "/volume-trend",
    response_model=VolumeTrendResponse,
    status_code=200,
    summary="Article volume per WIB time bucket, split by source type",
)
async def volume_trend(
    session: SessionDep,
    bucket: Literal["hour", "day"] = Query("day"),
) -> VolumeTrendResponse:
    now_utc = datetime.now(UTC)
    starts_wib = dense_bucket_starts(bucket, now_utc)
    cutoff_utc = starts_wib[0] - timedelta(hours=7)  # naive UTC lower bound

    effective = func.coalesce(Article.published_at, Article.created_at)
    wib_local = func.timezone("Asia/Jakarta", func.timezone("UTC", effective))
    wib_bucket = func.date_trunc(bucket, wib_local)

    stmt = (
        select(
            wib_bucket.label("wib_bucket"),
            ContentSource.source_type.label("source_type"),
            func.count(Article.id).label("cnt"),
        )
        .join(ContentSource, ContentSource.id == Article.source_id)
        .where(effective >= cutoff_utc)
        .group_by(wib_bucket, ContentSource.source_type)
    )
    rows = (await session.execute(stmt)).all()
    counts: dict[tuple[datetime, SourceType], int] = {
        (r.wib_bucket, r.source_type): r.cnt for r in rows
    }

    buckets = [
        VolumeBucket(
            bucket_start=start - timedelta(hours=7),
            competitor_count=counts.get((start, SourceType.rss), 0),
            internal_count=counts.get((start, SourceType.internal), 0),
        )
        for start in starts_wib
    ]
    return VolumeTrendResponse(bucket=bucket, buckets=buckets, generated_at=now_utc)
