import math
import uuid
from datetime import datetime

from core.models import Article, ContentSource
from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from api.deps import SessionDep

router = APIRouter(prefix="/articles", tags=["articles"])


class ArticleResponse(BaseModel):
    id: uuid.UUID
    title: str
    url: str
    first_paragraph: str | None
    published_at: datetime | None
    created_at: datetime
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
